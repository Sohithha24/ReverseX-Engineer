# Cursor / Codex: next task after opening this starter

Inspect the existing project and **do not rewrite it from scratch**.

Phase 1a already includes: a locally hosted TaskBoard fixture; Playwright browser snapshots with short-lived element IDs; a strict Pydantic action contract; a local-origin allowlist and request interception; an offline scripted smoke test; an optional Meta Muse Spark JSON decision planner; a small development API; and unit tests.

YOUR TASK:
1. Create a Python virtual environment and install `requirements.txt` and Playwright Chromium.
2. Run `python -m pytest -q`; report every test outcome.
3. Start `python -m http.server 8001 --bind 127.0.0.1 --directory sample_app` and run `python -m reversex.run --mode scripted`. Fix any genuine browser failures.
4. Review `artifacts/report.json`. Confirm the empty task validation and a valid task's persistence after reload are **observed**; add assertions against the observed text instead of relying on command completion alone.
5. If I provide `MODEL_API_KEY` as a local environment variable, run `python -m reversex.run --mode muse` and verify that the Meta call works. Never log or print my key. If there is no key, say Meta integration is UNTESTED, do not simulate it.
6. Add one adversarial text-in-HTML test showing that injected instructions on the page cannot expand the available browser actions; retain the strict allowlist and fresh snapshot IDs.
7. Do not start feature reconstruction, enable arbitrary URLs, deploy publicly, or add a database in this phase.

At the end: show commands run, tests that passed/failed/skipped, files changed, security limitations, and the next smallest functional task.
