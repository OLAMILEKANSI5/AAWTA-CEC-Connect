import os
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL is missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_TOKEN = os.environ.get("TEST_ADMIN_TOKEN", "tok_admin")
MEMBER_TOKEN = os.environ.get("TEST_MEMBER_TOKEN", "tok_amb")


def _session(token=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def anon():
    return _session()


@pytest.fixture(scope="session")
def admin():
    return _session(ADMIN_TOKEN)


@pytest.fixture(scope="session")
def member():
    return _session(MEMBER_TOKEN)


@pytest.fixture(scope="session")
def api():
    return API
