"""
Fanta-OFME-Cloud — Self-Hosted Save Sync Server & Web Dashboard
Companion server for Fanta OFME Downloader
Repository: https://github.com/ReTr0777/Fanta-OFME-Cloud
"""

import os
import time
import urllib.parse
from functools import wraps
from typing import Optional

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template,
    session
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from storage import SaveStorageManager

APP_VERSION = "1.0.0"
START_TIME = time.time()


def extract_api_key() -> Optional[str]:
    """Extracts API key from Authorization: Bearer <token>, X-API-Key header, or ?api_key= query."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    x_key = request.headers.get("X-API-Key", "").strip()
    if x_key:
        return x_key
    q_key = request.args.get("api_key", "").strip()
    if q_key:
        return q_key
    return None


def create_app(data_dir: Optional[str] = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("FANTA_SECRET_KEY", "fanta-ofme-cloud-secret-key-2026")
    app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("FANTA_MAX_UPLOAD_MB", "512")) * 1024 * 1024

    storage = SaveStorageManager(data_dir=data_dir)
    app.config["STORAGE"] = storage

    # ──────────────────────────────────────────────────────────────────────────
    # Auth Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def is_admin_authenticated() -> bool:
        admin_pw = (os.environ.get("FANTA_ADMIN_PASSWORD") or storage.config.get("admin_password") or "").strip()
        if not admin_pw:
            return True
        if session.get("admin_logged_in"):
            return True
        header_pw = request.headers.get("X-Admin-Password", "").strip()
        if header_pw and header_pw == admin_pw:
            return True
        return False

    def require_admin(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not is_admin_authenticated():
                return jsonify({"success": False, "error": "Admin authentication required"}), 401
            return f(*args, **kwargs)
        return decorated

    def require_client_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            key = extract_api_key()
            authorized, bucket, key_label = storage.resolve_auth(key)
            if not authorized:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized: Valid API Key required."
                }), 401
            # Allow explicit ?bucket= override if admin or open mode
            req_bucket = request.args.get("bucket")
            if req_bucket and is_admin_authenticated():
                bucket = storage.sanitize_bucket(req_bucket)
            request.fanta_bucket = bucket
            request.fanta_key_label = key_label
            return f(*args, **kwargs)
        return decorated

    # ──────────────────────────────────────────────────────────────────────────
    # Web Dashboard Route
    # ──────────────────────────────────────────────────────────────────────────

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html", version=APP_VERSION)

    # ──────────────────────────────────────────────────────────────────────────
    # Client Sync REST API (Used by Fanta OFME Downloader)
    # ──────────────────────────────────────────────────────────────────────────

    @app.route("/api/status", methods=["GET"])
    @require_client_auth
    def api_status():
        return jsonify({
            "success": True,
            "status": "ok",
            "server_name": storage.config.get("server_name", "Fanta-OFME-Cloud"),
            "version": APP_VERSION,
            "authenticated": True,
            "bucket": getattr(request, "fanta_bucket", "default"),
            "key_name": getattr(request, "fanta_key_label", "Open Access"),
            "uptime_seconds": int(time.time() - START_TIME)
        })

    @app.route("/api/saves", methods=["GET"])
    @require_client_auth
    def api_list_saves():
        bucket = getattr(request, "fanta_bucket", "default")
        saves = storage.list_saves(bucket=bucket)
        # Strip internal zip_path before returning over API
        cleaned = [{k: v for k, v in s.items() if k != "zip_path"} for s in saves]
        return jsonify({
            "success": True,
            "bucket": bucket,
            "saves": cleaned,
            "total": len(cleaned)
        })

    @app.route("/api/saves/<path:safe_name>", methods=["GET"])
    @require_client_auth
    def api_get_save(safe_name: str):
        decoded = urllib.parse.unquote(safe_name)
        bucket = getattr(request, "fanta_bucket", "default")
        info = storage.get_save_info(decoded, bucket=bucket)
        if not info.get("exists"):
            return jsonify({"exists": False, "safe_name": decoded, "bucket": bucket}), 404
        cleaned = {k: v for k, v in info.items() if k != "zip_path"}
        return jsonify(cleaned)

    @app.route("/api/saves/<path:safe_name>", methods=["POST"])
    @require_client_auth
    def api_upload_save(safe_name: str):
        decoded = urllib.parse.unquote(safe_name)
        bucket = getattr(request, "fanta_bucket", "default")

        if "file" not in request.files:
            return jsonify({"success": False, "error": "Missing 'file' in multipart upload"}), 400

        file_obj = request.files["file"]
        title = request.form.get("title") or decoded
        raw_mtime = request.form.get("mtime")
        mtime: Optional[float] = None
        if raw_mtime is not None:
            try:
                mtime = float(raw_mtime)
            except ValueError:
                mtime = None

        try:
            res = storage.store_save(
                safe_name=decoded,
                file_stream=file_obj,
                title=title,
                mtime=mtime,
                bucket=bucket
            )
            return jsonify(res), 200
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/saves/<path:safe_name>/download", methods=["GET"])
    @require_client_auth
    def api_download_save(safe_name: str):
        decoded = urllib.parse.unquote(safe_name)
        bucket = getattr(request, "fanta_bucket", "default")
        version_file = request.args.get("version")

        info = storage.get_save_info(decoded, bucket=bucket)
        if not info.get("exists"):
            return jsonify({"success": False, "error": f"No save found for '{decoded}'"}), 404

        if version_file:
            game_dir = os.path.dirname(info["zip_path"])
            hist_path = os.path.join(game_dir, "history", os.path.basename(version_file))
            if not os.path.exists(hist_path):
                return jsonify({"success": False, "error": "Requested history version not found"}), 404
            return send_file(
                hist_path,
                mimetype="application/zip",
                as_attachment=True,
                download_name=os.path.basename(version_file)
            )

        return send_file(
            info["zip_path"],
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{info['safe_name']}_save.zip"
        )

    @app.route("/api/saves/<path:safe_name>", methods=["DELETE"])
    @require_client_auth
    def api_delete_save(safe_name: str):
        decoded = urllib.parse.unquote(safe_name)
        bucket = getattr(request, "fanta_bucket", "default")
        deleted = storage.delete_save(decoded, bucket=bucket)
        if deleted:
            return jsonify({"success": True, "message": f"Deleted save backup for '{decoded}'."})
        return jsonify({"success": False, "error": f"No save backup found for '{decoded}'."}), 404

    # ──────────────────────────────────────────────────────────────────────────
    # Web Dashboard Admin Endpoints
    # ──────────────────────────────────────────────────────────────────────────

    @app.route("/api/admin/login", methods=["POST"])
    def admin_login():
        data = request.get_json() or {}
        pw = (data.get("password") or "").strip()
        admin_pw = (os.environ.get("FANTA_ADMIN_PASSWORD") or storage.config.get("admin_password") or "").strip()
        if not admin_pw or pw == admin_pw:
            session["admin_logged_in"] = True
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Invalid admin password"}), 401

    @app.route("/api/admin/logout", methods=["POST"])
    def admin_logout():
        session.pop("admin_logged_in", None)
        return jsonify({"success": True})

    @app.route("/api/admin/overview", methods=["GET"])
    def admin_overview():
        admin_pw = (os.environ.get("FANTA_ADMIN_PASSWORD") or storage.config.get("admin_password") or "").strip()
        if admin_pw and not is_admin_authenticated():
            return jsonify({
                "success": True,
                "locked": True,
                "server_name": storage.config.get("server_name", "Fanta-OFME-Cloud"),
                "version": APP_VERSION
            })

        selected_bucket = storage.sanitize_bucket(request.args.get("bucket", "default"))
        stats = storage.get_total_stats()
        saves = storage.list_saves(bucket=selected_bucket)
        cleaned_saves = [{k: v for k, v in s.items() if k != "zip_path"} for s in saves]

        return jsonify({
            "success": True,
            "locked": False,
            "server_name": storage.config.get("server_name", "Fanta-OFME-Cloud"),
            "version": APP_VERSION,
            "uptime_seconds": int(time.time() - START_TIME),
            "require_auth": storage.is_auth_required(),
            "has_admin_password": bool(admin_pw),
            "selected_bucket": selected_bucket,
            "stats": stats,
            "saves": cleaned_saves,
            "api_keys": storage.list_api_keys()
        })

    @app.route("/api/admin/keys", methods=["POST"])
    @require_admin
    def admin_create_key():
        data = request.get_json() or {}
        name = data.get("name", "Client PC")
        bucket = data.get("bucket", "default")
        custom_key = data.get("custom_key")
        created = storage.create_api_key(name=name, bucket=bucket, custom_key=custom_key)
        return jsonify({"success": True, "api_key": created})

    @app.route("/api/admin/keys", methods=["DELETE"])
    @require_admin
    def admin_delete_key():
        data = request.get_json() or {}
        key = data.get("key", "")
        if storage.delete_api_key(key):
            return jsonify({"success": True})
        return jsonify({"success": False, "error": "Key not found"}), 404

    @app.route("/api/admin/settings", methods=["POST"])
    @require_admin
    def admin_save_settings():
        data = request.get_json() or {}
        if "server_name" in data and data["server_name"].strip():
            storage.config["server_name"] = data["server_name"].strip()
        if "require_auth" in data:
            storage.config["require_auth"] = bool(data["require_auth"])
        if "admin_password" in data:
            storage.config["admin_password"] = data["admin_password"].strip()
            if storage.config["admin_password"]:
                session["admin_logged_in"] = True
        storage.save_config()
        return jsonify({"success": True})

    @app.route("/api/admin/promote", methods=["POST"])
    @require_admin
    def admin_promote_history():
        data = request.get_json() or {}
        safe_name = data.get("safe_name", "")
        filename = data.get("filename", "")
        bucket = data.get("bucket", "default")
        res = storage.promote_history_version(safe_name, filename, bucket=bucket)
        return jsonify(res), (200 if res.get("success") else 404)

    return app


app = create_app()

if __name__ == "__main__":
    host = os.environ.get("FANTA_HOST", "0.0.0.0")
    port = int(os.environ.get("FANTA_PORT", "27845"))
    debug = os.environ.get("FANTA_DEBUG", "false").lower() in ("1", "true", "yes")
    print(f"============================================================")
    print(f"  Fanta-OFME-Cloud v{APP_VERSION} running on http://{host}:{port}")
    print(f"============================================================")
    app.run(host=host, port=port, debug=debug)

