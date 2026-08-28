"""Round 5 — Public Community Impact Event Photo Gallery
Covers: GET /api/public/gallery aggregation, GET /api/public/files/{id} public gate,
and negative case (non-public event report photo must be excluded + 404)."""
import io
import os

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

backend_env = dotenv_values("/app/backend/.env")
MONGO_URL = backend_env.get("MONGO_URL")
DB_NAME = backend_env.get("DB_NAME")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


# ---------- private event + photo seeded directly in DB for the negative test ----------
@pytest.fixture(scope="module")
def private_photo(client, mongo):
    # upload a real file so a files record exists (public upload endpoint is unauthenticated)
    tiny_jpeg = bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300ffffffffffffffffffffffffffffffff"
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        "ffc9000b080001000101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
    )
    r = client.post(f"{API}/public/upload",
                    files={"file": ("TEST_private.jpg", io.BytesIO(tiny_jpeg), "image/jpeg")})
    assert r.status_code == 200, f"public upload failed: {r.status_code} {r.text[:300]}"
    fid = r.json()["id"]
    mongo.events.insert_one({
        "id": "TEST_evt_private_gal",
        "name": "TEST_Private Internal Retreat",
        "state": "Georgia",
        "date": "2026-05-01",
        "location": "Private venue",
        "public": False,
        "status": "approved",
        "reports": [{"id": "TEST_rep_priv", "highlights": "TEST private highlights",
                     "photo_file_ids": [fid]}],
    })
    yield fid
    mongo.events.delete_one({"id": "TEST_evt_private_gal"})
    mongo.files.delete_one({"id": fid})


class TestPublicGallery:
    def test_gallery_no_auth(self, client):
        r = client.get(f"{API}/public/gallery")
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "expected at least the seeded public event photo"
        for it in data:
            for k in ["photo_id", "event_id", "event_name", "state", "date", "location", "highlights"]:
                assert k in it, f"missing key {k} in {it}"
            assert "_id" not in it

    def test_seeded_public_event_present(self, client):
        data = client.get(f"{API}/public/gallery").json()
        seeded = [i for i in data if i["event_id"] == "evt_gal1"]
        assert seeded, "seeded event evt_gal1 not in gallery"
        assert seeded[0]["event_name"] == "CEC Community Career Day"
        assert seeded[0]["state"] == "Georgia"
        assert seeded[0]["photo_id"]

    def test_public_photo_served(self, client):
        data = client.get(f"{API}/public/gallery").json()
        for it in data:
            r = client.get(f"{API}/public/files/{it['photo_id']}")
            assert r.status_code == 200, f"{it['photo_id']} -> {r.status_code}"
            assert r.headers.get("content-type", "").startswith("image/"), r.headers.get("content-type")
            assert len(r.content) > 0

    def test_private_event_photo_not_listed(self, client, private_photo):
        data = client.get(f"{API}/public/gallery").json()
        ids = [i["photo_id"] for i in data]
        events = [i["event_id"] for i in data]
        assert private_photo not in ids, "private event photo leaked into public gallery"
        assert "TEST_evt_private_gal" not in events

    def test_private_event_photo_not_downloadable(self, client, private_photo):
        r = client.get(f"{API}/public/files/{private_photo}")
        assert r.status_code == 404, f"private photo served publicly! status={r.status_code}"

    def test_unknown_photo_id_404(self, client):
        r = client.get(f"{API}/public/files/file_does_not_exist_xyz")
        assert r.status_code == 404
