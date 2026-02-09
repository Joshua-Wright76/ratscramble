# Rat Scramble - Agent Context

## Project Overview
This repository now contains a working local AI simulation of Rat Scramble with:
- 4 player agents (Carmichael, Quincy, Medici, D'Ambrosio)
- 1 referee agent with final authority
- AWS Bedrock integration (Converse API)
- Rich-based visual CLI
- full event and model-call logging

The game rules source of truth remains `RULES.md`.

## Current Runtime Architecture

### Entrypoints
- `visual_main.py` - Rich TUI simulation
- `main.py` - non-visual simulation

Both load configuration from `config.yml`.

### Core Modules
- `src/game/engine.py` - rules/state transitions, decks/effects, vote logic, promise-token logic
- `src/game/orchestrator.py` - async phase orchestration, retries/timeouts, deadlock handling, logging hooks
- `src/agents/player_agent.py` - player agent logic (tool-calling actions)
- `src/referee/referee_agent.py` - referee rulings/contracts
- `src/llm/bedrock_client.py` - Bedrock Converse client, preflight auth checks, tool-call support
- `src/ui/game_display.py` - Rich dashboard
- `src/logging/game_logger.py` - `events.jsonl`, `raw_llm.jsonl`, `transcript.md`

## Key Session Decisions Implemented
- Local runtime first; CDK is support infra only (`cdk/`).
- Region: `us-west-2`.
- Model profile: `global.anthropic.claude-sonnet-4-5-20250929-v1:0`.
- Fully autonomous simulation.
- Free-form public communication, referee adjudication at phase transitions.
- Referee decisions are final.
- Agreements can span future rounds.
- Explicit mutual consent required to void agreements.
- Binding agreements cannot be broken; referee enforces compliance where possible.
- True async race behavior for token grabs.
- First timestamp wins token races.
- 500-word negotiation cap per player per round (hard mute after cap).
- 10-minute round cap.
- Retry then forfeit behavior for failed model calls.
- Live logging of prompts/responses and scratchpads.

## Configuration
Runtime settings are in `config.yml`, including:
- rounds, win threshold, seed, temperature
- request retries/backoff
- per-call LLM timeout
- deadlock and no-action cooldown settings
- optional `aws_profile`
- optional per-agent model overrides via `agent_models` (`Carmichael`, `Quincy`, `Medici`, `D'Ambrosio`, `Referee`)

## Bedrock Integration Status
Implemented:
- startup AWS preflight (`sts:GetCallerIdentity`) with explicit auth error surfacing
- Converse API calls
- tool-calling support for player actions

Player tools currently used:
- negotiation: `say_public`, `take_vote_token`, `no_action`
- voting: `cast_vote`, `no_action`
- vote-change: `use_target_token`, `force_with_three_tokens`, `no_action`

## Logging Artifacts
Per run under `logs/<timestamp>_<game_id>/`:
- `events.jsonl` - structured game events
- `raw_llm.jsonl` - raw prompts/responses/tool blocks
- `transcript.md` - human-readable public transcript

Recent telemetry improvements:
- `token_intent_inferred` events when token intent is inferred from `say_public`
- `promise_transfer` events on successful vote-change token movements
- `contract_enforcement` events when the referee applies action overrides
- `token_autocorrected` events when repeated invalid token grabs are auto-corrected

## Rich TUI Status
Implemented:
- live panes for chat, state, rulings, events
- live `LLM Usage` pane showing per-round and cumulative Bedrock token usage
- character colors:
  - Carmichael: green
  - Quincy: orange
  - Medici: red
  - D'Ambrosio: blue
- Promise holdings table is now visible in state panel

## Promise Token System Status
Implemented in engine and orchestration:
- `use_target_token` flow
- `force_with_three_tokens` flow
- vote-change cap (max 2 changes per target per round)
- token ownership updates (`holdings`) and event-level transfer logs

## Testing Status
Current tests include:
- rules engine unit tests
- config loader unit test
- player tool-mapping unit tests
- JSON utility unit tests
- optional live Bedrock E2E tests (`RUN_BEDROCK_TESTS=1`, `pytest -m bedrock`)

## Known Gaps / Limitations
- `Transformation` effect is still a no-op placeholder.
- `Gemini Season` is temporarily disabled in the active effect deck.
- Referee now emits plain-text rulings by design; contract/enforcement actions are inferred from ruling text.
- Deadlocks can still occur in negotiation when agents stall or spam no-action; forced assignment still handles terminal stalls.

## Deadlock Root Cause (Observed)
In recent full-run logs, deadlocks were caused by repeated invalid token strategy loops:
- multiple agents repeatedly attempted token `3` after it was already taken
- some agents failed to pivot to remaining available tokens quickly
- this created no-state-change windows until deadlock forcing triggered

Existing mitigations:
- deadlock detection timer (`negotiation_deadlock_seconds`)
- forced remaining token assignment
- no-action backoff to reduce churn/spam
- explicit legal-token hints in negotiation prompts
- auto-correction after repeated invalid token attempts

## Most Recent Full Game Snapshot
Run: `logs/20260209T193342Z_d333ca3b`
- 10 rounds completed
- winners: Quincy and Medici (18 each)
- one formal contract (`contract_001`) created early and later ruled breached
- heavy vote-change activity in mid/late rounds
