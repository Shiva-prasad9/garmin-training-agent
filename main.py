"""Single entry point for one daily run. STUB ONLY.

Intended flow (not implemented):
    1. load enabled plugins from config/features.yaml
    2. collect: each Collector -> DailyMetrics, Activity
    3. store: Repository.save_*
    4. plan: Planner.plan_day for today
    5. publish: each Output.publish(DailyBrief)
"""


def main() -> None:
    raise NotImplementedError("Phase 1 skeleton: no logic yet.")


if __name__ == "__main__":
    main()
