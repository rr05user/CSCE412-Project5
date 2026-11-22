import json
import os
import sys
import time
import urllib.request

URL = os.environ.get(
    "PRODUCTION_URL",
    "https://csce412rahul021005.me"
).rstrip("/")

EXPECTED = os.environ.get("EXPECTED_RELEASE", "").strip()

def fetch(path):
    request = urllib.request.Request(
        URL + path,
        headers={"Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"{path}: HTTP {response.status}")
        return response.read()

def verify():
    homepage = fetch("/")
    if b"<html" not in homepage.lower():
        raise RuntimeError("Homepage is not valid HTML")

    manifest = json.loads(fetch("/release.json"))
    actual = manifest.get("release_id")

    if EXPECTED and actual != EXPECTED:
        raise RuntimeError(
            f"Release mismatch: expected {EXPECTED}, got {actual}"
        )

    print("Production verification passed:", actual)

for attempt in range(1, 7):
    try:
        verify()
        sys.exit(0)
    except Exception as exc:
        print(f"Attempt {attempt}/6 failed: {exc}")
        if attempt < 6:
            time.sleep(10)

sys.exit("Production verification failed")
