# Rat Scramble Simulation

Local visual CLI simulation of Rat Scramble using five AI agents (four players + one referee) via AWS Bedrock.

Player agents use Bedrock tool-calling for game actions (`say_public`, `take_vote_token`, `cast_vote`, vote-change tools), while chat remains natural language in the TUI.

## Quick start

1. Install dependencies:
   - `python3 -m pip install --user -r requirements-dev.txt`
2. Configure AWS credentials with Bedrock access in `us-west-2`.
   - If using AWS SSO profile: `aws sso login --profile <your-profile>`
   - Set profile in `config.yml` (`aws_profile`) or export `AWS_PROFILE=<your-profile>`
3. Edit `config.yml` for game settings (rounds, win threshold, seed, temperature, etc).
   - Optional: set per-agent model overrides via `agent_models`:
     - `Carmichael`, `Quincy`, `Medici`, `D'Ambrosio`, `Referee`
     - any unspecified agent uses default `model_id`
   - Example (1 Sonnet vs 3 Haiku):
     ```yaml
     model_id: global.anthropic.claude-haiku-4-5-20251001-v1:0
     agent_models:
       Carmichael: global.anthropic.claude-sonnet-4-5-20250929-v1:0
     ```
4. Run simulation:
   - `python3 visual_main.py`
5. Non-visual mode:
   - `python3 main.py`

Artifacts are written under `logs/<timestamp>_<game_id>/`:
- `events.jsonl`
- `transcript.md`
- `raw_llm.jsonl`

## Tests

- Unit tests: `python3 -m pytest tests/unit`
- Live Bedrock E2E tests (opt-in): `python3 -m pytest -m bedrock tests/e2e`
  - Requires: `RUN_BEDROCK_TESTS=1`

## Troubleshooting AWS auth

- Verify identity: `aws sts get-caller-identity --profile <your-profile>`
- Verify region/profile in `config.yml`
- Common startup failures:
  - expired token/session: re-run `aws sso login`
  - access denied: add `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream`
