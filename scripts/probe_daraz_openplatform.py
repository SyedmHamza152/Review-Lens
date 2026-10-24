"""Probe the real Daraz Open Platform gateway reachability from this deployment.

Sends a properly-signed /brands/get request with placeholder credentials.
Interpretation of outcomes (all honest, no guessing):
- JSON business error (e.g. invalid app_key/sign) -> gateway REACHABLE and
  the protocol implementation is accepted by the server -> with real creds
  the review flow will work.
- HTTP 403 / RGV587 / timeout -> the Open Platform gateway is ALSO blocked
  from this datacenter IP -> must be stated in the UI status.
"""
import json
import sys

sys.path.insert(0, "/home/z/my-project/backend")
from app.integrations.daraz_open_platform import DarazOpenPlatformClient, DarazOpenPlatformError  # noqa: E402

client = DarazOpenPlatformClient(
    app_key="100126",            # documentation sample app key
    app_secret="probe_not_real", # deliberately not a real secret
    access_token="probe_not_real",
    country="pk",
    sign_method="sha256",
)
try:
    payload = client.get("/brands/get", offset=0, limit=1)
    print("UNEXPECTED SUCCESS (would mean dummy creds accepted - investigate):")
    print(json.dumps(payload)[:400])
except DarazOpenPlatformError as exc:
    print(f"REACHABLE - server processed our signed request and replied with a "
          f"business error (this is the EXPECTED outcome for dummy creds):")
    print(f"  api_path={exc.api_path} code={exc.code} http={exc.http_status}")
    print(f"  message={exc.message[:300]}")
except Exception as exc:  # noqa: BLE001
    print(f"NOT REACHABLE from this deployment: {type(exc).__name__}: {exc}"[:400])
