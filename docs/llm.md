# The LLM layer: plug and play

The rules decide what is allowed. A language model may then pick among the allowed options and write a short
coach note. The model is optional and swappable: change one line in `config/llm.yaml`.

```yaml
provider: manual      # manual | anthropic | none
```

## Safety, whatever the provider
The rules set the cap and build every option. The model can only choose at or below the cap, and code checks its
answer. If the model is missing, fails or answers outside the rules, the plan stays rules-only.

## provider: manual (default, no key)
1. Run `.venv/bin/python main.py` (or `--no-collect`). It writes `data/llm/prompt_<date>.md`.
2. Paste that file into any chat model (Claude, ChatGPT, a local model).
3. Save the model's reply (a JSON object, extra text around it is fine) as `data/llm/reply_<date>.json`.
4. Run again or refresh the dashboard. The coach note appears and the pick is used if the rules allow it.

## provider: anthropic (automatic, needs an API key)
1. Create an account at console.anthropic.com, add a little credit under Billing, create a key under API Keys.
2. Put `ANTHROPIC_API_KEY=your-key` in `.env` (never in `.env.example`).
3. In `config/llm.yaml` set `provider: anthropic`. Optionally change `model`.
4. Run `main.py`. Answers are cached per day in `data/cache/llm/`, so refreshing the dashboard costs nothing extra.

## provider: none
Rules only.

## Adding another model (a local one, another vendor)
Write a small client class in `planner/llm_client.py` with `available`, `cacheable`, `model` and
`choose(system, user, tool) -> {"intensity": ..., "coach_note": ...}`, then add its name to `make_client`.
Nothing else changes.

## What is sent
Only a compact summary: rule reasons, the options, workouts of the last 7 days (sport, minutes, load). No raw
files, no key, no name. In manual mode you see exactly what you paste.
