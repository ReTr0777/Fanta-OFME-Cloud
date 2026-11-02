"""
Unit Tests for Fanta-OFME-Cloud Server
Verifies:
- Health & status check (/api/status)
- Save upload, listing, single metadata inspection, download, and deletion
- Automatic rolling history preservation and version promotion
- API Key authentication & multi-bucket isolation
"""

import io
import os
import sys
import shutil
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app


class TestFantaCloudServer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="fanta_cloud_test_")
        self.app = create_app(data_dir=self.temp_dir)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _make_zip(filename: str, content: str) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename, content)
        return buf.getvalue()

    def test_open_mode_save_lifecycle_and_rolling_history(self):
        # 1. Check /api/status in open mode
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["bucket"], "default")

        # 2. Upload v1 save for Schedule I
        zip_v1 = self._make_zip("save.json", '{"level": 1}')
        up1 = self.client.post(
            "/api/saves/Schedule%20I",
            data={
                "file": (io.BytesIO(zip_v1), "Schedule I_save.zip"),
                "title": "Schedule I",
                "mtime": "1730540000.0"
            },
            content_type="multipart/form-data"
        )
        self.assertEqual(up1.status_code, 200)
        self.assertAlmostEqual(up1.get_json()["mtime"], 1730540000.0)

        # 3. Upload v2 save for Schedule I (should rotate v1 into rolling history)
        zip_v2 = self._make_zip("save.json", '{"level": 99}')
        up2 = self.client.post(
            "/api/saves/Schedule%20I",
            data={
                "file": (io.BytesIO(zip_v2), "Schedule I_save.zip"),
                "title": "Schedule I",
                "mtime": "1730550000.0"
            },
            content_type="multipart/form-data"
        )
        self.assertEqual(up2.status_code, 200)

        # 4. List saves & check history count
        list_res = self.client.get("/api/saves")
        self.assertEqual(list_res.status_code, 200)
        saves = list_res.get_json()["saves"]
        self.assertEqual(len(saves), 1)
        self.assertEqual(saves[0]["safe_name"], "Schedule I")
        self.assertEqual(saves[0]["history_count"], 1)

        # 5. Download active save and verify it is v2
        dl_res = self.client.get("/api/saves/Schedule%20I/download")
        self.assertEqual(dl_res.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(dl_res.data), "r") as zf:
            self.assertEqual(zf.read("save.json").decode("utf-8"), '{"level": 99}')
        dl_res.close()

        # 6. Promote historical v1 back to active
        hist_filename = saves[0]["history"][0]["filename"]
        prom_res = self.client.post(
            "/api/admin/promote",
            json={"safe_name": "Schedule I", "filename": hist_filename, "bucket": "default"}
        )
        self.assertEqual(prom_res.status_code, 200)

        dl_res2 = self.client.get("/api/saves/Schedule%20I/download")
        with zipfile.ZipFile(io.BytesIO(dl_res2.data), "r") as zf:
            self.assertEqual(zf.read("save.json").decode("utf-8"), '{"level": 1}')
        dl_res2.close()

        # 7. Delete save
        del_res = self.client.delete("/api/saves/Schedule%20I")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(self.client.get("/api/saves/Schedule%20I").status_code, 404)

    def test_api_key_auth_and_bucket_isolation(self):
        # Create two API keys assigned to different buckets
        k1 = self.client.post(
            "/api/admin/keys",
            json={"name": "Irwan PC", "bucket": "irwan", "custom_key": "key_irwan_123"}
        ).get_json()["api_key"]["key"]

        k2 = self.client.post(
            "/api/admin/keys",
            json={"name": "Friend PC", "bucket": "friend", "custom_key": "key_friend_456"}
        ).get_json()["api_key"]["key"]

        # Unauthenticated request must now fail with 401
        unauth = self.client.get("/api/saves")
        self.assertEqual(unauth.status_code, 401)

        # Upload save under Irwan's key
        zip_data = self._make_zip("slot1.dat", "irwan_save")
        up = self.client.post(
            "/api/saves/PEAK",
            headers={"Authorization": f"Bearer {k1}"},
            data={"file": (io.BytesIO(zip_data), "PEAK_save.zip"), "title": "PEAK"},
            content_type="multipart/form-data"
        )
        self.assertEqual(up.status_code, 200)

        # Irwan sees 1 save
        s1 = self.client.get("/api/saves", headers={"Authorization": f"Bearer {k1}"}).get_json()["saves"]
        self.assertEqual(len(s1), 1)

        # Friend sees 0 saves (isolated bucket)
        s2 = self.client.get("/api/saves", headers={"X-API-Key": k2}).get_json()["saves"]
        self.assertEqual(len(s2), 0)


if __name__ == "__main__":
    unittest.main()
