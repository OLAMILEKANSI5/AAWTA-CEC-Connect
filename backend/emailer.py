import os
import re
import ipaddress
import logging
import asyncio
import httpx
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "AAWTA CEC Connect")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


def _wrap(title: str, inner: str) -> str:
    return (
        '<table role="presentation" width="100%" style="background:#f4f4f7;padding:24px 0;'
        'font-family:Arial,Helvetica,sans-serif"><tr><td align="center">'
        '<table role="presentation" width="600" style="background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb">'
        '<tr><td style="background:#2E3192;padding:20px 28px">'
        '<span style="color:#ffffff;font-size:20px;font-weight:bold">AAWTA</span> '
        '<span style="color:#E0189C;font-size:20px;font-weight:bold">CEC Connect</span>'
        '</td></tr>'
        f'<tr><td style="padding:28px"><h2 style="color:#2E3192;margin:0 0 16px">{escape(title)}</h2>'
        f'{inner}</td></tr>'
        '<tr><td style="padding:18px 28px;background:#faf5fb;border-top:1px solid #eee;font-size:12px;color:#888">'
        'Sent by AAWTA CEC Connect. We never ask for your password or payment details by email.<br>'
        'AAWTA Power Lab, 5269 Buford Highway Suite 213, Doraville GA 30340 &middot; 770 756 6768'
        '</td></tr></table></td></tr></table>'
    )


async def send_email(*, to: str, subject: str, html: str, reply_to: str | None = None):
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json=payload,
            )
        resp.raise_for_status()
        return resp.json().get("id")
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        return None


async def send_safe(*, to: str, subject: str, title: str, body_html: str):
    """Non-raising helper used by fire-and-forget notification flows."""
    try:
        html = _wrap(title, body_html)
        return await send_email(to=to, subject=subject, html=html)
    except Exception as e:
        logger.error(f"send_safe failed for {to}: {e}")
        return None


def p(text: str) -> str:
    return f'<p style="color:#334155;font-size:15px;line-height:1.6;margin:0 0 12px">{text}</p>'
