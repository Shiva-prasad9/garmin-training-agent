"""Probe which per-activity details the Garmin Personal API offers (summary fields, samples, route, splits).

Prints field names, types, counts and HTTP status only. Never values, coordinates, the key or the token.

    python3 -I scripts/garmin_activity_probe.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from garmin_probe import ENV_PATH, load_key, request, shape  # noqa: E402

LIST = "/activitylist-service/activities/search/activities?start=0&limit=30"


def describe(name, status, body, depth=2):
    print(f"\n== {name}: status {status}")
    if status != 200:
        return None
    try:
        data = json.loads(body)
    except Exception:
        print(f"(not JSON, {len(body)} bytes)")
        return None
    print(json.dumps(shape(data, max_depth=depth), indent=1)[:3500])
    return data


def main():
    status, body = request("/personalapitoken-service/personal-api/personal-api-key/token",
                           {"Authorization": f"ApiKey {load_key()}"}, "POST")
    if status != 200:
        raise SystemExit(f"token exchange failed: {status}")
    auth = {"Authorization": f"Bearer {body.decode().strip().strip(chr(34))}"}

    status, body = request(LIST, auth)
    acts = json.loads(body) if status == 200 else []
    print(f"activity list: status {status}, {len(acts)} activities")
    if acts:
        print("fields present on the first activity (name: type):")
        print(json.dumps({k: type(v).__name__ for k, v in acts[0].items() if v is not None}, indent=0)[:3500])

    seen = {}
    for a in acts:
        key = (a.get("activityType") or {}).get("typeKey")
        seen.setdefault(key, a)
    print("\nactivity types found:", sorted(k for k in seen if k))

    for want in ("cycling", "running", "hiking", "walking"):
        a = next((v for k, v in seen.items() if k and want in k), None)
        if not a:
            continue
        aid = a["activityId"]
        print(f"\n######## {want} activity (id hidden) ########")
        for name, path in {
            "summary": f"/activity-service/activity/{aid}",
            "details (samples + route)": f"/activity-service/activity/{aid}/details?maxChartSize=200&maxPolylineSize=200",
            "splits": f"/activity-service/activity/{aid}/splits",
            "hr time in zones": f"/activity-service/activity/{aid}/hrTimeInZones",
        }.items():
            status, body = request(path, auth)
            describe(name, status, body, depth=3 if "details" in name else 2)
        break  # one example is enough to learn the shape


if __name__ == "__main__":
    main()
