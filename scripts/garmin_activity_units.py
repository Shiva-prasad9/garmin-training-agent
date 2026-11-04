"""Second activity probe: metric names, unit factors and ONE mid-activity sample row, for a cycling and a running activity.

Prints no coordinates, no names and no ids. Run: python3 -I scripts/garmin_activity_units.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from garmin_probe import load_key, request  # noqa: E402


def main():
    status, body = request("/personalapitoken-service/personal-api/personal-api-key/token",
                           {"Authorization": f"ApiKey {load_key()}"}, "POST")
    if status != 200:
        raise SystemExit(f"token exchange failed: {status}")
    auth = {"Authorization": f"Bearer {body.decode().strip().strip(chr(34))}"}
    acts = json.loads(request("/activitylist-service/activities/search/activities?start=0&limit=30", auth)[1])
    for want in ("cycling", "running", "hiking"):
        a = next((x for x in acts if want in ((x.get("activityType") or {}).get("typeKey") or "")), None)
        if not a:
            continue
        status, body = request(f"/activity-service/activity/{a['activityId']}/details?maxChartSize=400&maxPolylineSize=400", auth)
        if status != 200:
            print(want, "status", status)
            continue
        d = json.loads(body)
        print(f"\n=== {want}: {d.get('measurementCount')} samples, {len(d['geoPolylineDTO']['polyline'])} route points")
        for m in d["metricDescriptors"]:
            u = m.get("unit") or {}
            print(f"  [{m['metricsIndex']}] {m['key']}  unit={u.get('key')} factor={u.get('factor')}")
        rows = d["activityDetailMetrics"]
        print("  mid sample:", rows[len(rows) // 2]["metrics"])
        print("  route point keys:", sorted(d["geoPolylineDTO"]["polyline"][0].keys()))
        print("  split summary keys:", sorted((a.get("splitSummaries") or [{}])[0].keys()))


if __name__ == "__main__":
    main()
