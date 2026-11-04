"""The daily run with fake plugins: collect -> store -> plan -> publish, and what happens when things go wrong."""
from datetime import date, datetime, timedelta

import pytest

from training_agent.collectors.base import Collector
from training_agent.core.models import Activity, DailyMetrics, Sport
from training_agent.outputs.base import Output
from training_agent.outputs.console_brief import format_brief
from training_agent.pipeline import run_daily
from training_agent.planner.rules_planner import RulesPlanner
from training_agent.planner.week_plans.fixed_template import FixedTemplate
from training_agent.storage.sqlite import SqliteRepository

TODAY = date(2026, 2, 11)


def metrics_for(first, last):
    out, d = [], first
    while d <= last:
        out.append(DailyMetrics(date=d, sleep_hours=7, sleep_score=80, hrv_last_night_ms=50 + d.toordinal() % 3,
                                resting_hr=48, body_battery_morning=80))
        d += timedelta(days=1)
    return out


class FakeCollector(Collector):
    name = "fake_source"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    def collect_metrics(self, start, end):
        self.calls.append((start, end))
        if self.fail:
            raise ConnectionError("network down")
        return metrics_for(start, end)

    def collect_activities(self, start, end):
        return [Activity(id=f"f:{end}", source="garmin", sport=Sport.RUN, duration_s=3000,
                         start_time=datetime.combine(end, datetime.min.time()).replace(hour=7), training_load=90.0, avg_hr=145.0)]


class Capture(Output):
    name = "capture"

    def __init__(self, boom=False):
        self.briefs, self.boom = [], boom

    def publish(self, brief):
        if self.boom:
            raise RuntimeError("email server down")
        self.briefs.append(brief)


def planner():
    return RulesPlanner(sources=[FixedTemplate()])


def stocked_repo(tmp_path, last=TODAY):
    repo = SqliteRepository(tmp_path / "t.sqlite")
    repo.save_metrics(metrics_for(last - timedelta(days=45), last))
    return repo


def test_full_run_collects_stores_plans_and_publishes(tmp_path):
    repo, col, out = stocked_repo(tmp_path, TODAY - timedelta(days=3)), FakeCollector(), Capture()
    brief = run_daily(day=TODAY, days=3, collectors=[col], repo=repo, planner=planner(), outputs=[out])
    assert col.calls == [(TODAY - timedelta(days=2), TODAY)]
    assert repo.get_metrics(TODAY, TODAY)  # today's metrics were stored
    assert [o.intensity.value for o in brief.plan.options] == ["rest", "easy", "moderate", "hard"]
    assert brief.notes == [] and brief.latest_data == TODAY and out.briefs == [brief]


def test_a_failing_source_does_not_stop_the_run(tmp_path):
    repo, out = stocked_repo(tmp_path, TODAY), Capture()
    brief = run_daily(day=TODAY, collectors=[FakeCollector(fail=True)], repo=repo, planner=planner(), outputs=[out])
    assert any("Could not refresh from fake_source" in n and "network down" in n for n in brief.notes)
    assert out.briefs  # the brief still went out, from stored data


def test_stale_data_is_reported(tmp_path):
    repo = stocked_repo(tmp_path, TODAY - timedelta(days=3))
    brief = run_daily(day=TODAY, collect=False, collectors=[], repo=repo, planner=planner(), outputs=[])
    assert brief.latest_data == TODAY - timedelta(days=3)
    assert any("3 days old" in n for n in brief.notes)
    assert brief.plan.cap.value == "easy"  # no reading for today: careful


def test_no_collect_does_not_call_the_sources(tmp_path):
    col = FakeCollector()
    run_daily(day=TODAY, collect=False, collectors=[col], repo=stocked_repo(tmp_path), planner=planner(), outputs=[])
    assert col.calls == []


def test_empty_database_is_a_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="backfill"):
        run_daily(day=TODAY, collect=False, collectors=[], repo=SqliteRepository(tmp_path / "e.sqlite"),
                  planner=planner(), outputs=[])


def test_one_broken_output_does_not_stop_the_others(tmp_path):
    good = Capture()
    run_daily(day=TODAY, collect=False, collectors=[], repo=stocked_repo(tmp_path), planner=planner(),
              outputs=[Capture(boom=True), good])
    assert len(good.briefs) == 1


def test_choices_from_yesterday_shape_the_brief(tmp_path):
    from training_agent.core.models import Intensity, PlannedSession
    repo = stocked_repo(tmp_path)
    repo.save_plan([PlannedSession(date=TODAY - timedelta(days=1), sport=Sport.RUN, intensity=Intensity.HARD,
                                   title="x", rationale="x")])
    brief = run_daily(day=TODAY, collect=False, collectors=[], repo=repo, planner=planner(), outputs=[])
    assert brief.plan.cap.value == "easy"


def test_brief_text_has_the_essentials(tmp_path):
    repo = stocked_repo(tmp_path, TODAY - timedelta(days=1))
    brief = run_daily(day=TODAY, collect=False, collectors=[], repo=repo, planner=planner(), outputs=[])
    text = format_brief(brief)
    for part in ("TRAINING BRIEF", "Wednesday 11 February 2026", "Allowed today", "RECOMMENDED:", "Your options",
                 "This week", "[rest", "[hard", "1 day old"):
        assert part in text, part


def test_the_real_config_loads_every_stage():
    from training_agent.core.plugin import load_enabled_plugins
    from training_agent.pipeline import CONFIG
    names = {s: sorted(p.name for p in load_enabled_plugins(CONFIG, s)) for s in ("collectors", "storage", "planner", "outputs")}
    assert names == {"collectors": ["garmin_personal_api", "strava_export"], "storage": ["sqlite"],
                     "planner": ["rules_planner"], "outputs": ["console_brief"]}
