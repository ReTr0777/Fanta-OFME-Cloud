"""
Storage & API Key Manager for Fanta-OFME-Cloud
Handles:
- Save archive storage per bucket (default bucket or per-API-key isolated bucket)
- Rolling backup history (automatically keeps previous N zip versions when a new save is uploaded)
- Sidecar metadata.json with accurate client mtime preservation
- API Key creation, revocation, and authentication resolution
"""

import os
import re
import json
import time
import shutil
import secrets
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple


class SaveStorageManager:
    def __init__(self, data_dir: Optional[str] = None, max_history: int = 5):
        self.data_dir = os.path.abspath(data_dir or os.environ.get("FANTA_DATA_DIR", "./data"))
        self.saves_root = os.path.join(self.data_dir, "saves")
        self.config_path = os.path.join(self.data_dir, "server_config.json")
        self.max_history = int(os.environ.get("FANTA_MAX_HISTORY", max_history))

        os.makedirs(self.saves_root, exist_ok=True)
        os.makedirs(os.path.join(self.saves_root, "default"), exist_ok=True)
        self.config: Dict[str, Any] = self._load_config()

    # ──────────────────────────────────────────────────────────────────────────
    # Configuration & API Keys
    # ──────────────────────────────────────────────────────────────────────────

    def _load_config(self) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "server_name": os.environ.get("FANTA_SERVER_NAME", "Fanta-OFME-Cloud"),
            "require_auth": os.environ.get("FANTA_REQUIRE_AUTH", "").lower() in ("1", "true", "yes"),
            "api_keys": {}
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        defaults.update(loaded)
            except Exception as e:
                print(f"[Storage] Error loading config: {e}", flush=True)

        # Ensure env FANTA_API_KEY is always registered if set
        env_key = (os.environ.get("FANTA_API_KEY") or "").strip()
        if env_key and env_key not in defaults.get("api_keys", {}):
            defaults.setdefault("api_keys", {})[env_key] = {
                "name": "Master Env Key",
                "bucket": "default",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_env": True
            }
        return defaults

    def save_config(self) -> None:
        try:
            temp_cfg = self.config_path + ".tmp"
            with open(temp_cfg, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            os.replace(temp_cfg, self.config_path)
        except Exception as e:
            print(f"[Storage] Error saving config: {e}", flush=True)

    def _sync_config(self) -> None:
        """Reloads server_config.json from disk so multiple Gunicorn workers stay in sync."""
        self.config = self._load_config()

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitizes game title or bucket name to prevent path traversal."""
        cleaned = re.sub(r'[^a-zA-Z0-9_\-\s]', '', (name or "")).strip()
        return cleaned or "unnamed"

    @staticmethod
    def sanitize_bucket(bucket: str) -> str:
        cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', (bucket or "")).strip().lower()
        return cleaned or "default"

    def is_auth_required(self) -> bool:
        """
        Auth is required if:
        1. FANTA_REQUIRE_AUTH is true / enabled in config, OR
        2. At least one API key has been configured (via FANTA_API_KEY env or dashboard).
        """
        self._sync_config()
        if self.config.get("require_auth"):
            return True
        return len(self.config.get("api_keys", {})) > 0

    def resolve_auth(self, provided_key: Optional[str]) -> Tuple[bool, str, Optional[str]]:
        """
        Validates an API key and returns (is_authorized, bucket_name, key_label).
        If no keys are configured and require_auth is False, allows access to 'default' bucket.
        """
        self._sync_config()
        key = (provided_key or "").strip()
        api_keys = self.config.get("api_keys", {})

        if not self.is_auth_required():
            if key and key in api_keys:
                info = api_keys[key]
                return True, self.sanitize_bucket(info.get("bucket", "default")), info.get("name", "API Key")
            return True, "default", "Open Access (LAN)"

        if not key:
            return False, "default", None

        if key in api_keys:
            info = api_keys[key]
            return True, self.sanitize_bucket(info.get("bucket", "default")), info.get("name", "API Key")

        return False, "default", None

    def create_api_key(self, name: str, bucket: str = "default", custom_key: Optional[str] = None) -> Dict[str, Any]:
        self._sync_config()
        clean_name = (name or "New Client").strip()
        clean_bucket = self.sanitize_bucket(bucket)
        token = (custom_key or "").strip() or f"fanta_{secrets.token_urlsafe(24)}"

        key_obj = {
            "name": clean_name,
            "bucket": clean_bucket,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_env": False
        }
        self.config.setdefault("api_keys", {})[token] = key_obj
        self.save_config()

        os.makedirs(os.path.join(self.saves_root, clean_bucket), exist_ok=True)
        return {"key": token, **key_obj}

    def delete_api_key(self, token: str) -> bool:
        self._sync_config()
        keys = self.config.get("api_keys", {})
        if token in keys:
            del keys[token]
            self.save_config()
            return True
        return False

    def list_api_keys(self) -> List[Dict[str, Any]]:
        self._sync_config()
        result = []
        for k, v in self.config.get("api_keys", {}).items():
            masked = k[:9] + "..." + k[-4:] if len(k) > 14 else "***"
            result.append({
                "key": k,
                "masked_key": masked,
                "name": v.get("name", "Key"),
                "bucket": v.get("bucket", "default"),
                "created_at": v.get("created_at", ""),
                "is_env": bool(v.get("is_env", False))
            })
        return result

    def list_buckets(self) -> List[str]:
        self._sync_config()
        buckets = {"default"}
        if os.path.isdir(self.saves_root):
            for entry in os.listdir(self.saves_root):
                if os.path.isdir(os.path.join(self.saves_root, entry)):
                    buckets.add(entry)
        for v in self.config.get("api_keys", {}).values():
            b = v.get("bucket")
            if b:
                buckets.add(self.sanitize_bucket(b))
        return sorted(list(buckets))

    # ──────────────────────────────────────────────────────────────────────────
    # Save Archive Operations
    # ──────────────────────────────────────────────────────────────────────────

    def _get_game_dir(self, bucket: str, safe_name: str) -> str:
        clean_bucket = self.sanitize_bucket(bucket)
        clean_game = self.sanitize_name(safe_name)
        return os.path.join(self.saves_root, clean_bucket, clean_game)

    def list_saves(self, bucket: str = "default") -> List[Dict[str, Any]]:
        clean_bucket = self.sanitize_bucket(bucket)
        bucket_dir = os.path.join(self.saves_root, clean_bucket)
        if not os.path.isdir(bucket_dir):
            return []

        saves = []
        for folder in sorted(os.listdir(bucket_dir)):
            game_dir = os.path.join(bucket_dir, folder)
            if not os.path.isdir(game_dir):
                continue
            info = self.get_save_info(folder, bucket=clean_bucket)
            if info.get("exists"):
                saves.append(info)
        return saves

    def get_save_info(self, safe_name: str, bucket: str = "default") -> Dict[str, Any]:
        clean_bucket = self.sanitize_bucket(bucket)
        clean_name = self.sanitize_name(safe_name)
        game_dir = self._get_game_dir(clean_bucket, clean_name)
        zip_path = os.path.join(game_dir, f"{clean_name}_save.zip")
        meta_path = os.path.join(game_dir, "metadata.json")

        if not os.path.exists(zip_path):
            return {
                "exists": False,
                "safe_name": clean_name,
                "bucket": clean_bucket,
                "size_bytes": 0,
                "mtime": None
            }

        st = os.stat(zip_path)
        mtime = st.st_mtime
        title = clean_name
        updated_at = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()

        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = json.load(mf)
                    mtime = float(meta.get("mtime", mtime))
                    title = meta.get("title") or clean_name
                    updated_at = meta.get("updated_at") or updated_at
            except Exception:
                pass

        # Inspect rolling history
        history_dir = os.path.join(game_dir, "history")
        history_list = []
        if os.path.isdir(history_dir):
            for hf in sorted(os.listdir(history_dir), reverse=True):
                if hf.endswith(".zip"):
                    hp = os.path.join(history_dir, hf)
                    hst = os.stat(hp)
                    history_list.append({
                        "filename": hf,
                        "size_bytes": hst.st_size,
                        "mtime": hst.st_mtime,
                        "mtime_str": datetime.fromtimestamp(hst.st_mtime).strftime("%b %d, %Y • %I:%M %p")
                    })

        return {
            "exists": True,
            "safe_name": clean_name,
            "title": title,
            "bucket": clean_bucket,
            "size_bytes": st.st_size,
            "mtime": mtime,
            "mtime_str": datetime.fromtimestamp(mtime).strftime("%b %d, %Y • %I:%M %p"),
            "updated_at": updated_at,
            "history_count": len(history_list),
            "history": history_list,
            "zip_path": zip_path
        }

    def store_save(
        self,
        safe_name: str,
        file_stream: Any,
        title: Optional[str] = None,
        mtime: Optional[float] = None,
        bucket: str = "default"
    ) -> Dict[str, Any]:
        clean_bucket = self.sanitize_bucket(bucket)
        clean_name = self.sanitize_name(safe_name)
        clean_title = (title or clean_name).strip()
        game_dir = self._get_game_dir(clean_bucket, clean_name)
        os.makedirs(game_dir, exist_ok=True)

        zip_path = os.path.join(game_dir, f"{clean_name}_save.zip")
        temp_path = os.path.join(game_dir, f".{clean_name}_uploading.tmp")

        # 1. Save uploaded stream to temporary file first (atomic replacement)
        if hasattr(file_stream, "save"):
            file_stream.save(temp_path)
        elif hasattr(file_stream, "read"):
            with open(temp_path, "wb") as f:
                shutil.copyfileobj(file_stream, f)
        elif isinstance(file_stream, (bytes, bytearray)):
            with open(temp_path, "wb") as f:
                f.write(file_stream)
        else:
            raise ValueError("Unsupported file_stream object")

        # 2. If a previous save exists and max_history > 0, rotate it into history/
        if os.path.exists(zip_path) and self.max_history > 0:
            history_dir = os.path.join(game_dir, "history")
            os.makedirs(history_dir, exist_ok=True)
            prev_info = self.get_save_info(clean_name, bucket=clean_bucket)
            prev_mtime = int(prev_info.get("mtime") or time.time())
            hist_name = f"{clean_name}_{prev_mtime}_{int(time.time())}.zip"
            hist_target = os.path.join(history_dir, hist_name)
            try:
                shutil.copy2(zip_path, hist_target)
                # Prune older history beyond max_history
                all_hist = sorted(
                    [f for f in os.listdir(history_dir) if f.endswith(".zip")],
                    key=lambda x: os.path.getmtime(os.path.join(history_dir, x)),
                    reverse=True
                )
                for old_f in all_hist[self.max_history:]:
                    try:
                        os.remove(os.path.join(history_dir, old_f))
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Storage] History rotation notice: {e}", flush=True)

        # 3. Move temp file to active zip_path
        shutil.move(temp_path, zip_path)

        effective_mtime = float(mtime) if mtime is not None else time.time()
        size_bytes = os.path.getsize(zip_path)
        now_iso = datetime.now(timezone.utc).isoformat()

        meta_path = os.path.join(game_dir, "metadata.json")
        meta_data = {
            "safe_name": clean_name,
            "title": clean_title,
            "bucket": clean_bucket,
            "mtime": effective_mtime,
            "size_bytes": size_bytes,
            "updated_at": now_iso
        }
        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta_data, mf, indent=2)

        return {
            "success": True,
            "safe_name": clean_name,
            "title": clean_title,
            "bucket": clean_bucket,
            "size_bytes": size_bytes,
            "mtime": effective_mtime,
            "updated_at": now_iso
        }

    def promote_history_version(self, safe_name: str, history_filename: str, bucket: str = "default") -> Dict[str, Any]:
        """Promotes a historical backup .zip to be the active save."""
        clean_bucket = self.sanitize_bucket(bucket)
        clean_name = self.sanitize_name(safe_name)
        game_dir = self._get_game_dir(clean_bucket, clean_name)
        safe_hist_file = os.path.basename(history_filename)
        hist_path = os.path.join(game_dir, "history", safe_hist_file)

        if not os.path.exists(hist_path):
            return {"success": False, "error": "Historical version not found."}

        zip_path = os.path.join(game_dir, f"{clean_name}_save.zip")
        shutil.copy2(hist_path, zip_path)

        new_mtime = time.time()
        meta_path = os.path.join(game_dir, "metadata.json")
        title = clean_name
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    title = json.load(mf).get("title", clean_name)
            except Exception:
                pass

        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump({
                "safe_name": clean_name,
                "title": title,
                "bucket": clean_bucket,
                "mtime": new_mtime,
                "size_bytes": os.path.getsize(zip_path),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }, mf, indent=2)

        return {"success": True, "message": f"Promoted {safe_hist_file} to active save for {title}.", "mtime": new_mtime}

    def delete_save(self, safe_name: str, bucket: str = "default") -> bool:
        clean_bucket = self.sanitize_bucket(bucket)
        clean_name = self.sanitize_name(safe_name)
        game_dir = self._get_game_dir(clean_bucket, clean_name)
        if os.path.exists(game_dir):
            shutil.rmtree(game_dir, ignore_errors=True)
            return not os.path.exists(game_dir)
        return False

    def get_total_stats(self) -> Dict[str, Any]:
        buckets = self.list_buckets()
        total_games = 0
        total_bytes = 0
        total_history_files = 0

        for b in buckets:
            saves = self.list_saves(bucket=b)
            total_games += len(saves)
            for s in saves:
                total_bytes += int(s.get("size_bytes", 0))
                for h in s.get("history", []):
                    total_bytes += int(h.get("size_bytes", 0))
                    total_history_files += 1

        return {
            "total_games": total_games,
            "total_bytes": total_bytes,
            "total_history_files": total_history_files,
            "buckets_count": len(buckets),
            "buckets": buckets,
            "api_keys_count": len(self.config.get("api_keys", {}))
        }
