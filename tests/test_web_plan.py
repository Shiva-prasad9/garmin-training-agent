"""Plan, choose/override, and gym log endpoints."""
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from training_agent.core.models import Activity, DailyMetrics, Sport
from training_agent.storage.sqlite import SqliteRepository
from training_agent.web.app import create_app

TODAY = date(2026, 2, 11)  # a Wednesday


def make(tmp_path, poor_sleep=False):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    start = TODAY - timedelta(days=41)
    repo.save_metrics([
        DailyMetrics(date=start + timedelta(days=i), sleep_hours=7, sleep_score=60 if (poor_sleep and i == 41) else 80,
                     hrv_last_night_ms=50 + i % 3, resting_hr=48, body_battery_morning=80) for i in range(42)])
    repo.save_activities([
        Activity(id=f"g:{k}", source="garmin", sport=Sport.BIKE if k % 2 else Sport.RUN,
                 start_time=datetime.combine(TODAY - timedelta(days=2 * k), datetime.min.time()).replace(hour=8),
                 duration_s=3600, training_load=(70, 90, 130)[k % 3], avg_hr=140.0) for k in range(1, 30)])
    return repo, TestClient(create_app(repo, today=TODAY))


def test_plan_has_four_options_and_week_info(tmp_path):
    _, c = make(tmp_path)
    body = c.get("/api/plan").json()
    assert [o["intensity"] for o in body["plan"]["options"]] == ["rest", "easy", "moderate", "hard"]
    assert body["plan"]["day"] == "2026-02-11" and body["chosen"] == []
    assert "remaining_slots" in body["plan"] and body["plan"]["week_source"] == "fixed_template"


def test_choose_saves_and_replaces_the_choice(tmp_path):
    repo, c = make(tmp_path)
    first = c.post("/api/plan/choose", json={"intensity": "easy"}).json()
    c.post("/api/plan/choose", json={"intensity": "moderate"})
    saved = repo.get_plan(TODAY, TODAY)
    assert len(saved) == 1 and saved[0].intensity.value == "moderate"
    assert first["overridden"] is False and c.get("/api/plan").json()["chosen"][0]["intensity"] == "moderate"


def test_choosing_above_the_cap_is_recorded_as_override(tmp_path):
    repo, c = make(tmp_path, poor_sleep=True)
    plan = c.get("/api/plan").json()["plan"]
    assert plan["cap"] == "easy"
    hard = c.post("/api/plan/choose", json={"intensity": "hard"}).json()
    assert hard["overridden"] is True and hard["recommended_intensity"] == plan["recommended"]
    assert "readiness_gate" in hard["rule_flags"] and repo.get_plan(TODAY, TODAY)[0].overridden


def test_clear_removes_the_choice(tmp_path):
    repo, c = make(tmp_path)
    c.post("/api/plan/choose", json={"intensity": "easy"})
    c.post("/api/plan/clear")
    assert repo.get_plan(TODAY, TODAY) == []


def test_yesterdays_choice_shapes_today(tmp_path):
    repo, c = make(tmp_path)
    # a hard session chosen yesterday and nothing recorded: today is capped at easy
    from training_agent.core.models import Intensity, PlannedSession
    repo.save_plan([PlannedSession(date=TODAY - timedelta(days=1), sport=Sport.RUN, intensity=Intensity.HARD,
                                   title="x", rationale="x")])
    plan = c.get("/api/plan").json()["plan"]
    assert plan["cap"] == "easy" and any("planned for yesterday" in r for v in plan["verdicts"] for r in v["reasons"])


def test_manual_gym_entry_counts_for_the_week_and_can_be_deleted(tmp_path):
    repo, c = make(tmp_path)
    monday = TODAY - timedelta(days=2)
    before = c.get("/api/plan").json()["plan"]
    entry = c.post("/api/manual", json={"sport": "gym", "minutes": 50, "effort": 6, "kind": "lower", "day": monday.isoformat()}).json()
    assert entry["sport"] == "gym" and entry["duration_min"] == 50
    after = c.get("/api/plan").json()["plan"]
    gym = lambda p: sum(1 for s in p["remaining_slots"] if s["kind"] == "strength")  # noqa: E731
    assert gym(after) == gym(before) - 1 or after["dropped_slots"] != before["dropped_slots"]
    assert any("gym" in line for line in after["done_this_week"])
    assert len(c.get("/api/manual").json()) == 1
    assert c.delete(f"/api/manual/{entry['id']}").status_code == 200 and c.get("/api/manual").json() == []


def test_only_manual_entries_can_be_deleted_and_input_is_validated(tmp_path):
    _, c = make(tmp_path)
    assert c.delete("/api/manual/g:1").status_code == 400
    assert c.post("/api/manual", json={"minutes": 1, "effort": 5}).status_code == 422
    assert c.post("/api/manual", json={"minutes": 40, "effort": 11}).status_code == 422
    assert c.post("/api/manual", json={"minutes": 40, "effort": 5, "day": "2025-01-01"}).status_code == 422
    assert c.post("/api/plan/choose", json={"intensity": "extreme"}).status_code == 422


def test_changes_are_refused_from_other_computers_but_reading_is_open(tmp_path):
    repo, _ = make(tmp_path)
    remote = TestClient(create_app(repo, today=TODAY), client=("203.0.113.9", 5000))
    assert remote.get("/api/plan").status_code == 200
    assert remote.post("/api/plan/choose", json={"intensity": "easy"}).status_code == 403
    assert remote.post("/api/manual", json={"minutes": 40, "effort": 5}).status_code == 403
    assert remote.delete("/api/manual/manual:gym:2026-02-10:1").status_code == 403
    assert repo.get_plan(TODAY, TODAY) == []


def test_any_activity_can_be_logged_by_hand(tmp_path):
    repo, c = make(tmp_path)
    run = c.post("/api/manual", json={"sport": "run", "minutes": 45, "effort": 5, "distance_km": 7.5}).json()
    assert run["sport"] == "run" and run["distance_km"] == 7.5 and run["id"].startswith("manual:run:")
    hike = c.post("/api/manual", json={"sport": "hike", "minutes": 120, "effort": 4}).json()
    assert hike["sport"] == "other" and hike["source_sport"] == "hiking"
    log = c.get(f"/api/activity-log?kind=hike&days=30").json()
    assert [a["id"] for a in log["activities"]] == [hike["id"]]  # shows under Hiking & walking
    assert c.post("/api/manual", json={"sport": "kayak", "minutes": 30, "effort": 5}).status_code == 422
    assert c.post("/api/manual", json={"sport": "run", "minutes": 30, "effort": 5, "distance_km": -2}).status_code == 422
    assert c.post("/api/manual", json={"sport": "run", "minutes": 30, "effort": 5, "day": (TODAY - timedelta(days=200)).isoformat()}).status_code == 422
