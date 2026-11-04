"""The LLM layer may only choose within the cap; every failure falls back to the rules plan."""
import json
from datetime import date

from training_agent.core.models import Intensity, PlanContext
from training_agent.planner.llm_agent import LlmAgent, build_prompt
from training_agent.planner.rules_planner import RulesPlanner
from training_agent.planner.week_plans.fixed_template import FixedTemplate
from training_agent.core.models import Activity, DailyAssessment, Sport
from datetime import datetime

DAY = date(2026, 11, 4)


class FakeClient:
    model = "fake"
    available = True

    def __init__(self, answer=None, error=None):
        self.answer, self.error, self.calls, self.last_user = answer, error, 0, ""

    def choose(self, system, user, tool):
        self.calls += 1
        self.last_user = user
        if self.error:
            raise self.error
        return self.answer


def ctx():
    ride = Activity(id="garmin:1", source="garmin", sport=Sport.BIKE, start_time=datetime(2026, 11, 3, 8), duration_s=5400, training_load=120)
    return PlanContext(day=DAY, assessments=[DailyAssessment(date=DAY)], activities=[ride])


def agent(client, tmp_path):
    return LlmAgent(client=client, rules=RulesPlanner(sources=[FixedTemplate()]), cache_dir=tmp_path)


def test_valid_choice_within_cap_is_used_and_explained(tmp_path):
    base = RulesPlanner(sources=[FixedTemplate()]).plan_day(ctx())
    choice = Intensity.EASY if base.recommended != Intensity.EASY else Intensity.REST
    plan = agent(FakeClient({"intensity": choice.value, "coach_note": "Keep it light today."}), tmp_path).plan_day(ctx())
    assert plan.decided_by == "llm" and plan.recommended == choice and plan.coach_note == "Keep it light today."
    assert [o.intensity for o in plan.options if o.risk == "recommended"] == [choice]
    assert plan.cap == base.cap


def test_choice_above_the_cap_is_ignored(tmp_path):
    rules = RulesPlanner(sources=[FixedTemplate()])
    base = rules.plan_day(ctx())
    if base.cap == Intensity.HARD:  # force a cap by asking for something above a lowered plan
        base = base.model_copy(update={"cap": Intensity.EASY, "recommended": Intensity.EASY})
    a = agent(FakeClient({"intensity": "hard", "coach_note": "Go all out."}), tmp_path)
    a.rules = type("R", (), {"plan_day": lambda self, c: base, "to_session": rules.to_session})()
    plan = a.plan_day(ctx())
    assert plan.decided_by == "rules" and plan.recommended == base.recommended and plan.coach_note == ""


def test_api_error_falls_back_to_rules(tmp_path):
    plan = agent(FakeClient(error=RuntimeError("down")), tmp_path).plan_day(ctx())
    assert plan.decided_by == "rules" and plan.coach_note == ""


def test_garbage_answer_falls_back_to_rules(tmp_path):
    assert agent(FakeClient({"intensity": "extreme", "coach_note": "x"}), tmp_path).plan_day(ctx()).decided_by == "rules"
    assert agent(FakeClient({"coach_note": "no intensity"}), tmp_path).plan_day(ctx()).decided_by == "rules"


def test_no_key_means_no_call(tmp_path):
    client = FakeClient({"intensity": "rest", "coach_note": "x"})
    client.available = False
    assert agent(client, tmp_path).plan_day(ctx()).decided_by == "rules" and client.calls == 0


def test_same_day_same_facts_is_answered_from_cache(tmp_path):
    client = FakeClient({"intensity": "easy", "coach_note": "Easy."})
    a = agent(client, tmp_path)
    a.plan_day(ctx()); a.plan_day(ctx())
    assert client.calls == 1


def test_prompt_is_compact_facts_only():
    plan = RulesPlanner(sources=[FixedTemplate()]).plan_day(ctx())
    facts = json.loads(build_prompt(plan, ctx()))
    assert {"cap", "options", "rule_verdicts", "workouts_last_7_days"} <= set(facts)
    assert facts["workouts_last_7_days"][0]["sport"] == "bike"
    assert "@" not in json.dumps(facts)


# ---------- plug-and-play providers ----------
import pytest
from training_agent.planner.llm_client import ManualClient, NullClient, NoReply, make_client


def manual_agent(tmp_path):
    return LlmAgent(client=ManualClient(tmp_path / "llm"), rules=RulesPlanner(sources=[FixedTemplate()]), cache_dir=tmp_path / "c")


def test_manual_mode_writes_prompt_and_stays_rules_only_until_a_reply_exists(tmp_path):
    plan = manual_agent(tmp_path).plan_day(ctx())
    assert plan.decided_by == "rules"
    text = (tmp_path / "llm" / f"prompt_{DAY}.md").read_text()
    assert "Facts for today" in text and "ONLY a JSON object" in text


def test_manual_reply_is_used_even_with_chatter_and_still_checked(tmp_path):
    a = manual_agent(tmp_path)
    base = a.rules.plan_day(ctx())
    a.plan_day(ctx())
    choice = "rest" if base.recommended != Intensity.REST else "easy"
    (tmp_path / "llm" / f"reply_{DAY}.json").write_text(f'Sure!\n```json\n{{"intensity": "{choice}", "coach_note": "Pasted."}}\n```')
    plan = a.plan_day(ctx())
    assert plan.decided_by == "llm" and plan.coach_note == "Pasted."
    (tmp_path / "llm" / f"reply_{DAY}.json").write_text('{"intensity": "hard", "coach_note": "x"}')
    capped = a.plan_day(ctx())
    assert capped.recommended in (Intensity.EASY, Intensity.REST, Intensity.MODERATE, Intensity.HARD)
    assert capped.cap == base.cap


def test_provider_switch_by_config():
    assert isinstance(make_client({"provider": "manual"}), ManualClient)
    assert isinstance(make_client({"provider": "none"}), NullClient)
    assert make_client({"provider": "anthropic"}).__class__.__name__ == "AnthropicClient"
    with pytest.raises(ValueError):
        make_client({"provider": "typo"})
