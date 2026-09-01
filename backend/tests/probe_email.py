"""One-off probe: inspect the Emergent email integration 422 response body."""
import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")


async def main():
    payload = {"to": ["qa.probe@example.com"], "subject": "TEST probe", "html": "<p>hi</p>",
               "from_name": os.environ.get("EMAIL_FROM_NAME")}
    if os.environ.get("EMAIL_REPLY_TO"):
        payload["contact_email"] = os.environ["EMAIL_REPLY_TO"]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://integrations.emergentagent.com/api/v1/email/send",
                         headers={"X-Email-Key": os.environ.get("EMERGENT_EMAIL_KEY", "")}, json=payload)
    print(r.status_code, r.text[:500])


asyncio.run(main())
