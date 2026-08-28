"""Round 6 — photo captions in post-event reports, public gallery, staff report viewer."""
import io

import pytest
import requests
from PIL import Image, ImageDraw

EVENT_ID = "evtc"  # Approved/Completed public event owned by tok_amb
CAP_A = "TEST_ambassador caption A"
STATE = {}


def _img_bytes(color=(200, 30, 120)):
    im = Image.new("RGB", (600, 400), (20, 40, 90))
    ImageDraw.Draw(im).rectangle([50, 50, 550, 350], fill=color)
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    return buf.getvalue()


def _upload(api, token, name="TEST_photo.jpg"):
    """Multipart upload with its own session (no JSON content-type header)."""
    r = requests.post(f"{api}/upload", headers={"Authorization": f"Bearer {token}"},
                      files={"file": (name, _img_bytes(), "image/jpeg")},
                      data={"category": "event-photo"}, timeout=60)
    assert r.status_code == 200, f"upload failed {r.status_code}: {r.text[:300]}"
    fid = r.json()["id"]
    assert isinstance(fid, str) and fid
    return fid


class TestCaptionFlow:
    """Submit report with/without captions -> reports endpoint -> public gallery -> public file."""

    def test_01_submit_report_with_and_without_caption(self, member, api):
        fid_cap = _upload(api, "tok_amb", "TEST_with_caption.jpg")
        fid_nocap = _upload(api, "tok_amb", "TEST_no_caption.jpg")
        r = member.post(f"{api}/events/{EVENT_ID}/report", json={
            "actual_attendance": 42,
            "outcomes": "TEST_outcomes round6",
            "highlights": "TEST_highlights round6",
            "photo_file_ids": [fid_cap, fid_nocap],
            "photo_captions": {fid_cap: CAP_A},
            "file_ids": [],
        })
        assert r.status_code == 200, r.text[:400]
        rep = r.json()
        assert rep["photo_captions"] == {fid_cap: CAP_A}
        assert rep["photo_file_ids"] == [fid_cap, fid_nocap]
        STATE["cap"], STATE["nocap"] = fid_cap, fid_nocap

    def test_02_owner_reports_endpoint_attaches_caption(self, member, api):
        r = member.get(f"{api}/events/{EVENT_ID}/reports")
        assert r.status_code == 200, r.text[:300]
        reports = r.json()
        assert isinstance(reports, list) and reports
        photos = {p["id"]: p for rep in reports for p in rep.get("photos", [])}
        assert STATE["cap"] in photos, "uploaded photo missing from reports"
        assert photos[STATE["cap"]]["caption"] == CAP_A
        assert photos[STATE["nocap"]]["caption"] is None
        assert all("caption" in p for p in photos.values())
        # pre-seeded caption still intact
        assert any(p.get("caption") == "Students exploring a big rig cab" for p in photos.values())

    def test_03_staff_reports_endpoint_shows_caption(self, admin, api):
        r = admin.get(f"{api}/events/{EVENT_ID}/reports")
        assert r.status_code == 200, r.text[:300]
        photos = {p["id"]: p.get("caption") for rep in r.json() for p in rep.get("photos", [])}
        assert photos.get(STATE["cap"]) == CAP_A
        assert photos.get(STATE["nocap"]) is None

    def test_04_public_gallery_has_caption_field(self, anon, api):
        r = anon.get(f"{api}/public/gallery")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and items
        assert all("caption" in it for it in items), "some gallery items missing 'caption'"
        by_pid = {it["photo_id"]: it for it in items}
        assert by_pid.get(STATE["cap"], {}).get("caption") == CAP_A
        assert STATE["nocap"] in by_pid
        assert by_pid[STATE["nocap"]]["caption"] is None
        assert by_pid[STATE["cap"]]["event_id"] == EVENT_ID
        assert by_pid[STATE["cap"]]["event_name"] == "Career Day"

    def test_05_public_file_served_for_public_event_photo(self, anon, api):
        for key in ("cap", "nocap"):
            r = anon.get(f"{api}/public/files/{STATE[key]}")
            assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"
            assert r.headers["content-type"].startswith("image/")
            assert len(r.content) > 1000

    def test_06_non_string_caption_does_not_500(self, member, api):
        fid = _upload(api, "tok_amb", "TEST_badtype.jpg")
        r = member.post(f"{api}/events/{EVENT_ID}/report", json={
            "outcomes": "TEST_bad type captions", "photo_file_ids": [fid],
            "photo_captions": {fid: 123},
        })
        assert r.status_code in (200, 422), f"unexpected {r.status_code}: {r.text[:200]}"


class TestPrivateEventPhotoRegression:
    def test_private_event_photo_404_on_public_files(self, admin, anon, api):
        ev = admin.post(f"{api}/events", json={"name": "TEST_private event r6", "date": "2026-05-01",
                                               "state": "Georgia", "public": False})
        assert ev.status_code == 200, ev.text[:300]
        eid = ev.json()["id"]
        fid = _upload(api, "tok_admin", "TEST_private_photo.jpg")
        rp = admin.post(f"{api}/events/{eid}/report", json={
            "outcomes": "TEST_private outcomes", "photo_file_ids": [fid],
            "photo_captions": {fid: "TEST_private caption"},
        })
        assert rp.status_code == 200, rp.text[:300]

        pub = anon.get(f"{api}/public/files/{fid}")
        assert pub.status_code == 404, f"private event photo publicly served ({pub.status_code})"

        gal = anon.get(f"{api}/public/gallery")
        assert all(it["photo_id"] != fid for it in gal.json()), "private photo leaked into gallery"

    def test_anon_cannot_read_private_event_reports(self, anon, api):
        r = anon.get(f"{api}/events/{EVENT_ID}/reports")
        assert r.status_code in (401, 403), f"unexpected {r.status_code}"
