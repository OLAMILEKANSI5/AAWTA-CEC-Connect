"""Phase D tests: Check-In Center + Badge Center (get_event, lookup, badges pdf/zip, manual badge, badge-config)."""
import io
import os
import zipfile

import pytest
import requests
from dotenv import dotenv_values

fe = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or fe.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE}/api"
ADMIN = {"Authorization": "Bearer tok_admtest"}
MEMBER = {"Authorization": "Bearer tok_memba"}
EVT = "evt_246d20a66b31"


def _items(data):
    if isinstance(data, dict):
        return data.get("registrations") or data.get("items") or []
    return data


def _fetch(url):
    return _items(requests.get(url, headers=ADMIN, timeout=60).json())


@pytest.fixture(scope="module")
def regs():
    r = requests.get(f"{API}/events/{EVT}/registrations", headers=ADMIN, timeout=60)
    assert r.status_code == 200, r.text
    items = _items(r.json())
    assert items, "no registrations seeded"
    return items


# ---------- GET /api/events/{id} ----------
class TestGetEvent:
    def test_get_event_staff(self):
        r = requests.get(f"{API}/events/{EVT}", headers=ADMIN, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["id"] == EVT
        assert "_id" not in d
        assert isinstance(d.get("registered_count"), int) and d["registered_count"] >= 1

    def test_get_event_unknown_404(self):
        r = requests.get(f"{API}/events/evt_doesnotexist", headers=ADMIN, timeout=60)
        assert r.status_code == 404, r.text

    def test_get_event_anonymous_401(self):
        r = requests.get(f"{API}/events/{EVT}", timeout=60)
        assert r.status_code == 401, f"{r.status_code} {r.text[:200]}"

    def test_get_event_non_owner_member(self):
        r = requests.get(f"{API}/events/{EVT}", headers=MEMBER, timeout=60)
        # documents actual behavior (approved/public events readable by members)
        assert r.status_code in (200, 403), r.text


# ---------- lookup ----------
class TestLookup:
    def test_lookup_found(self, regs):
        tok = next((x["checkin_token"] for x in regs if x.get("checkin_token")), None)
        assert tok, "no reg with checkin_token"
        r = requests.get(f"{API}/registrations/lookup", params={"token": tok}, headers=ADMIN, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["registration"]["checkin_token"] == tok
        assert "already_checked_in" in d and "checked_in_at" in d and "checked_in_by" in d
        assert "_id" not in d["registration"]

    def test_lookup_unknown_404(self):
        r = requests.get(f"{API}/registrations/lookup", params={"token": "nope_zzz"}, headers=ADMIN, timeout=60)
        assert r.status_code == 404, r.text

    def test_lookup_anonymous_401(self, regs):
        tok = next(x["checkin_token"] for x in regs if x.get("checkin_token"))
        r = requests.get(f"{API}/registrations/lookup", params={"token": tok}, timeout=60)
        assert r.status_code == 401, r.text

    def test_lookup_non_owner_403(self, regs):
        tok = next(x["checkin_token"] for x in regs if x.get("checkin_token"))
        r = requests.get(f"{API}/registrations/lookup", params={"token": tok}, headers=MEMBER, timeout=60)
        assert r.status_code == 403, r.text


# ---------- checkin + duplicate guard ----------
class TestCheckinFlow:
    def test_qr_checkin_and_already_flag(self, regs):
        target = next(x for x in regs if x.get("checkin_token"))
        rid, tok = target["id"], target["checkin_token"]
        r = requests.put(f"{API}/registrations/{rid}/checkin", json={"checked_in": True, "method": "qr"},
                         headers=ADMIN, timeout=60)
        assert r.status_code == 200, r.text
        lk = requests.get(f"{API}/registrations/lookup", params={"token": tok}, headers=ADMIN, timeout=60).json()
        assert lk["already_checked_in"] is True
        assert lk["checked_in_at"]
        assert lk["checked_in_by"]
        assert lk["registration"]["checkin_method"] == "qr"
        assert lk["registration"]["status"] == "checked_in"


# ---------- badge config ----------
class TestBadgeConfig:
    def test_save_and_persist(self):
        payload = {"default_w": 4, "default_h": 6, "address": "TEST_123 Peachtree St",
                   "website": "aawta.org", "contact_email": "info@aawta.org",
                   "contact_phone": "404-555-1212", "show_phone": True,
                   "category_colors": {"VIP": "#123456", "Walk-In": "#abcdef"}}
        r = requests.put(f"{API}/events/{EVT}/badge-config", json=payload, headers=ADMIN, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["category_colors"]["VIP"] == "#123456"
        assert d["show_phone"] is True
        ev = requests.get(f"{API}/events/{EVT}", headers=ADMIN, timeout=60).json()
        assert ev["badge_config"]["address"] == "TEST_123 Peachtree St"
        assert ev["badge_config"]["category_colors"]["Walk-In"] == "#abcdef"

    def test_badge_config_non_owner_403(self):
        r = requests.put(f"{API}/events/{EVT}/badge-config", json={"show_phone": False}, headers=MEMBER, timeout=60)
        assert r.status_code == 403, r.text

    def test_badge_config_anon_401(self):
        r = requests.put(f"{API}/events/{EVT}/badge-config", json={"show_phone": False}, timeout=60)
        assert r.status_code == 401, r.text


# ---------- badges pdf / zip ----------
def _pdf_pages(b):
    return b.count(b"/Type /Page") or b.count(b"/Type/Page")


class TestBadgesPdf:
    def test_combined_pdf_one_page_per_reg(self, regs):
        ids = [x["id"] for x in regs[:3]]
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": ids, "w": 4, "h": 6, "combined": True},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF-")
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(r.content))
        assert len(rd.pages) == len(ids)
        box = rd.pages[0].mediabox
        assert round(float(box.width) / 72, 2) == 4.0
        assert round(float(box.height) / 72, 2) == 6.0

    def test_zip_one_pdf_per_reg(self, regs):
        ids = [x["id"] for x in regs[:3]]
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": ids, "w": 4, "h": 3, "combined": False},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/zip")
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        assert len(names) == len(ids), names
        for n in names:
            assert z.read(n).startswith(b"%PDF-")

    @pytest.mark.parametrize("w,h", [(4, 6), (4, 3), (3.5, 2), (2.25, 3.5), (5.5, 4.25)])
    def test_sizes(self, regs, w, h):
        ids = [regs[0]["id"]]
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": ids, "w": w, "h": h, "combined": True},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.content.startswith(b"%PDF-")
        from pypdf import PdfReader
        box = PdfReader(io.BytesIO(r.content)).pages[0].mediabox
        assert round(float(box.width) / 72, 2) == round(w, 2)
        assert round(float(box.height) / 72, 2) == round(h, 2)

    def test_marks_printed_and_increments_count(self, regs):
        rid = regs[0]["id"]
        before_items = _fetch(f"{API}/events/{EVT}/registrations")
        b = next(x for x in before_items if x["id"] == rid)
        prev_count = b.get("badge_print_count") or 0
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": [rid], "combined": True},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200
        after_items = _fetch(f"{API}/events/{EVT}/registrations")
        a = next(x for x in after_items if x["id"] == rid)
        assert a["badge_status"] == "printed"
        assert (a.get("badge_print_count") or 0) == prev_count + 1
        assert a.get("badge_printed_at")

    def test_only_unprinted_excludes_printed(self, regs):
        # everything printed by now for this event -> expect 400
        requests.post(f"{API}/events/{EVT}/badges/pdf", json={"combined": True}, headers=ADMIN, timeout=120)
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"only_unprinted": True, "combined": True},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 400, f"expected 400 empty-set, got {r.status_code}"

    def test_checked_in_only(self, regs):
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"checked_in_only": True, "combined": False},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200, r.text[:300]
        z = zipfile.ZipFile(io.BytesIO(r.content))
        checked = _fetch(f"{API}/events/{EVT}/registrations?checkin=in")
        assert len(z.namelist()) == len(checked), (z.namelist(), len(checked))

    def test_empty_selection_400(self):
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": ["reg_nope"], "combined": True},
                          headers=ADMIN, timeout=60)
        assert r.status_code == 400, r.text[:200]

    def test_pdf_non_owner_403(self, regs):
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": [regs[0]["id"]]}, headers=MEMBER, timeout=60)
        assert r.status_code == 403, r.text[:200]

    def test_pdf_anon_401(self, regs):
        r = requests.post(f"{API}/events/{EVT}/badges/pdf", json={"ids": [regs[0]["id"]]}, timeout=60)
        assert r.status_code == 401, r.text[:200]


class TestManualBadge:
    def test_manual_pdf(self):
        r = requests.post(f"{API}/events/{EVT}/badges/manual-pdf",
                          json={"first_name": "TEST", "last_name": "Walkin", "business_name": "TEST Biz",
                                "business_website": "testbiz.com", "badge_category": "VIP", "w": 3.5, "h": 2},
                          headers=ADMIN, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF-")
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(r.content))
        assert len(rd.pages) == 1
        assert round(float(rd.pages[0].mediabox.width) / 72, 2) == 3.5

    def test_manual_pdf_no_db_write(self):
        before_items = _fetch(f"{API}/events/{EVT}/registrations")
        requests.post(f"{API}/events/{EVT}/badges/manual-pdf", json={"first_name": "TEST", "last_name": "NoWrite"},
                      headers=ADMIN, timeout=120)
        after_items = _fetch(f"{API}/events/{EVT}/registrations")
        assert len(after_items) == len(before_items)

    def test_manual_missing_first_name_422(self):
        r = requests.post(f"{API}/events/{EVT}/badges/manual-pdf", json={"last_name": "X"}, headers=ADMIN, timeout=60)
        assert r.status_code == 422, r.status_code

    def test_manual_non_owner_403(self):
        r = requests.post(f"{API}/events/{EVT}/badges/manual-pdf", json={"first_name": "X"}, headers=MEMBER, timeout=60)
        assert r.status_code == 403, r.text[:200]

    def test_manual_anon_401(self):
        r = requests.post(f"{API}/events/{EVT}/badges/manual-pdf", json={"first_name": "X"}, timeout=60)
        assert r.status_code == 401, r.text[:200]
