from __future__ import annotations

import asyncio
import hashlib
import random
import re
import time
import uuid
from contextlib import nullcontext
from dataclasses import replace
from typing import Any

from rich.live import Live

from src.agents.player_agent import PlayerAgent
from src.config.settings import SimulationConfig
from src.game.engine import RulesEngine
from src.game.models import CHARACTER_ORDER, Character, Contract, Phase
from src.llm.bedrock_client import BedrockConverseClient
from src.llm.json_utils import try_extract_json_object
from src.logging.game_logger import GameLogger
from src.referee.referee_agent import RefereeAgent
from src.ui.game_display import GameDisplay


class SimulationOrchestrator:
    def __init__(self, config: SimulationConfig, visual: bool = True):
        self.config = config
        self.visual = visual
        self.engine = RulesEngine(config)
        self._llm_clients_by_model: dict[str, BedrockConverseClient] = {}
        self.llm = self._client_for_model(config.model_id)
        strategy_players = set()
        if config.strategy_doc_enabled:
            strategy_players = {name.strip() for name in config.strategy_doc_players}
        self.player_agents = {
            character: PlayerAgent(
                name=character.value,
                llm=self._client_for_model(self._model_for_actor(character.value)),
                character=character,
                negotiation_word_cap=config.negotiation_word_cap,
                use_strategy_doc=character.value in strategy_players,
            )
            for character in CHARACTER_ORDER
        }
        self.referee = RefereeAgent(name="Referee", llm=self._client_for_model(self._model_for_actor("Referee")))
        self._referee_scratchpad = ""
        self.game_id = str(uuid.uuid4())[:8]
        self.logger = GameLogger(root=config.log_root, game_id=self.game_id)
        self.display = GameDisplay()
        self.rng = random.Random(config.seed)
        self._live: Live | None = None
        self._usage_actor_order = [character.value for character in CHARACTER_ORDER] + ["Referee"]
        self._usage_totals = self._new_usage_bucket()
        self._usage_round = self._new_usage_bucket()
        self._usage_requests_total = 0
        self._usage_requests_round = 0
        self._usage_requests_by_actor_total = {name: 0 for name in self._usage_actor_order}
        self._usage_requests_by_actor_round = {name: 0 for name in self._usage_actor_order}
        self._usage_by_actor_total = {name: self._new_usage_bucket() for name in self._usage_actor_order}
        self._usage_by_actor_round = {name: self._new_usage_bucket() for name in self._usage_actor_order}

    async def run(self) -> dict[str, Any]:
        context = (
            Live(self.display.render(), refresh_per_second=8, vertical_overflow="crop")
            if self.visual
            else nullcontext()
        )
        if self.visual and isinstance(context, Live):
            self._live = context
        with context:
            self.display.add_event("Running AWS preflight check...")
            self._refresh_state()
            try:
                identity = await self.llm.preflight_check()
                active_models = self._active_model_ids()
                identity["active_models"] = active_models
                identity["agent_models"] = {
                    character.value: self._model_for_actor(character.value)
                    for character in CHARACTER_ORDER
                } | {"Referee": self._model_for_actor("Referee")}
                self.display.add_event(
                    "AWS ready: "
                    f"{identity['arn']} | {identity['region']} | "
                    f"default={identity['model_id']} | active={len(active_models)} model(s)"
                )
                self._record_event("preflight_ok", identity)
                self._refresh_state()
            except Exception as exc:  # noqa: BLE001
                message = f"Preflight failed: {str(exc)}"
                self.display.add_event(message)
                self._record_event("preflight_failed", {"error": str(exc)})
                self._refresh_state()
                raise RuntimeError(message) from exc

            while self.engine.state.phase != Phase.COMPLETE:
                self.engine.start_round()
                if self.engine.state.phase == Phase.COMPLETE:
                    break

                self._reset_round_usage()
                self._record_event("round_started", {"round": self.engine.state.round_number})
                self._refresh_state()

                await self._run_negotiation_phase()
                await self._referee_phase_change("negotiation", "voting")
                self.engine.enter_voting_phase()
                self._record_event("phase_change", {"phase": "voting"})
                self._refresh_state()

                await self._run_voting_phase()
                await self._referee_phase_change("voting", "resolution")
                round_result = self.engine.resolve_round()
                self._record_event(
                    "round_resolved",
                    {
                        "passed_proposal": round_result.passed_proposal_index,
                        "outcome": round_result.outcome_type.value if round_result.outcome_type else None,
                        "winning_votes": round_result.winning_votes,
                        "effect": round_result.applied_effect,
                    },
                )
                self._refresh_state()
                await self._referee_phase_change("resolution", "next_round")

            scores = self.engine.score_players()
            winners = [char.value for char, score in scores.items() if score >= self.config.win_threshold]
            summary = {
                "game_id": self.game_id,
                "scores": {character.value: score for character, score in scores.items()},
                "winners": winners,
                "log_dir": self.logger.run_path(),
            }
            self._record_event("game_complete", summary)
            self.display.add_event(f"Game complete. Winners: {winners if winners else 'None'}")
            self._refresh_state()
            return summary

    async def _run_negotiation_phase(self) -> None:
        self.display.add_event("Negotiation phase started; agents are thinking...")
        self._refresh_state()
        round_deadline = time.time() + self.config.round_timeout_seconds
        lock = asyncio.Lock()
        stop_event = asyncio.Event()
        last_heartbeat = time.time()
        last_progress_time = time.time()
        forced_reason: str | None = None

        async def loop_player(character: Character) -> None:
            nonlocal last_progress_time
            agent = self.player_agents[character]
            no_action_streak = 0
            repeated_invalid_token = 0
            last_invalid_token: int | None = None
            while not stop_event.is_set():
                if time.time() >= round_deadline:
                    stop_event.set()
                    return

                async with lock:
                    if self.engine.state.phase != Phase.NEGOTIATION:
                        return
                    state = self.engine.export_public_state()
                    transcript_tail = self.engine.state.transcript[-20:]
                    scratchpad_before = self.engine.state.scratchpads[character]

                try:
                    result = await asyncio.wait_for(
                        agent.negotiation_action(state, transcript_tail, scratchpad_before),
                        timeout=self.config.llm_request_timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    self._record_event(
                        "agent_timeout",
                        {
                            "character": character.value,
                            "phase": "negotiation",
                            "timeout_seconds": self.config.llm_request_timeout_seconds,
                        },
                    )
                    self.display.add_event(f"{character.value} timed out in negotiation; retrying")
                    self._refresh_state()
                    await asyncio.sleep(0.1)
                    continue
                except Exception as exc:  # noqa: BLE001
                    self._record_event(
                        "agent_error",
                        {"character": character.value, "phase": "negotiation", "error": str(exc)},
                    )
                    self.display.add_event(f"{character.value} negotiation error: {str(exc)[:80]}")
                    self._refresh_state()
                    await asyncio.sleep(0.1)
                    continue

                timestamp = time.time()
                async with lock:
                    if stop_event.is_set() or self.engine.state.phase != Phase.NEGOTIATION:
                        return

                    self._log_llm_exchange("player", character, result, scratchpad_before)
                    self._record_parse_warning("player", character.value, "negotiation", result)

                    new_scratchpad = result.get("scratchpad")
                    if isinstance(new_scratchpad, str):
                        self.engine.state.scratchpads[character] = new_scratchpad

                    control_action = str(result.get("_control_action", ""))
                    utterance = (result.get("utterance") or "").strip()
                    if utterance:
                        binding_allowed = character not in self.engine.state.token_assignments.values()
                        was_muted = character in self.engine.state.muted_players
                        kept, muted = self.engine.record_utterance(character, utterance, binding_allowed)
                        if kept:
                            self._record_chat(f"{character.value}: {kept}")
                        if muted and not was_muted:
                            self._record_event("muted", {"character": character.value, "reason": "word_cap_reached"})

                    attempt = result.get("attempt_take_token")
                    inferred_from_text = control_action == "say_public" and isinstance(attempt, int)
                    if inferred_from_text:
                        self._record_event(
                            "token_intent_inferred",
                            {"character": character.value, "token": attempt, "source": "say_public_text"},
                        )
                    if isinstance(attempt, int):
                        success = self.engine.take_token(character, attempt)
                        self._record_event(
                            "token_attempt",
                            {
                                "character": character.value,
                                "token": attempt,
                                "success": success,
                                "timestamp": timestamp,
                            },
                        )
                        if success:
                            last_progress_time = time.time()
                            repeated_invalid_token = 0
                            last_invalid_token = None
                            self.display.add_event(f"{character.value} took token {attempt}")
                        else:
                            if last_invalid_token == attempt:
                                repeated_invalid_token += 1
                            else:
                                repeated_invalid_token = 1
                                last_invalid_token = attempt
                            fallback = self._first_legal_token_for_player(character)
                            if fallback is not None and repeated_invalid_token >= 2:
                                fallback_success = self.engine.take_token(character, fallback)
                                self._record_event(
                                    "token_autocorrected",
                                    {
                                        "character": character.value,
                                        "requested_token": attempt,
                                        "fallback_token": fallback,
                                        "success": fallback_success,
                                        "repeat_count": repeated_invalid_token,
                                        "timestamp": time.time(),
                                    },
                                )
                                if fallback_success:
                                    last_progress_time = time.time()
                                    repeated_invalid_token = 0
                                    last_invalid_token = None
                                    self.display.add_event(
                                        f"{character.value} auto-corrected to token {fallback} after invalid retries"
                                    )

                    if self.engine.all_tokens_taken():
                        stop_event.set()

                    if control_action == "no_action":
                        no_action_streak += 1
                    else:
                        no_action_streak = 0

                self._refresh_state()
                if no_action_streak > 0:
                    delay = min(
                        self.config.no_action_cooldown_max_seconds,
                        self.config.no_action_cooldown_base_seconds * (2 ** min(no_action_streak - 1, 4)),
                    )
                else:
                    delay = 0.05
                if self.visual:
                    delay = max(delay, max(0.0, self.config.visual_step_delay_seconds))
                await asyncio.sleep(delay)

        tasks = [asyncio.create_task(loop_player(character)) for character in CHARACTER_ORDER]

        while not stop_event.is_set():
            now = time.time()
            if time.time() >= round_deadline:
                stop_event.set()
                break
            if self.engine.all_tokens_taken():
                stop_event.set()
                break
            if (now - last_progress_time) >= self.config.negotiation_deadlock_seconds:
                forced = self.engine.force_remaining_tokens_seeded()
                forced_reason = "deadlock_no_state_change"
                self._record_event(
                    "forced_token_assignment",
                    {
                        "reason": forced_reason,
                        "assignments": [(player.value, token) for player, token in forced],
                    },
                )
                self.display.add_event("Negotiation deadlock detected. Forced remaining token assignments.")
                self._refresh_state()
                stop_event.set()
                break
            if (now - last_heartbeat) >= 5:
                remaining = max(0, int(round_deadline - now))
                self.display.add_event(
                    f"Negotiation active... tokens {len(self.engine.state.token_assignments)}/4, {remaining}s left"
                )
                self._refresh_state()
                last_heartbeat = now
            await asyncio.sleep(0.1)

        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if not self.engine.all_tokens_taken():
            forced = self.engine.force_remaining_tokens_seeded()
            reason = forced_reason or "round_timeout"
            self._record_event(
                "forced_token_assignment",
                {
                    "reason": reason,
                    "assignments": [(player.value, token) for player, token in forced],
                },
            )
            self.display.add_event("Round timed out. Forced remaining token assignments.")
            self._refresh_state()

    async def _run_voting_phase(self) -> None:
        self.display.add_event("Voting phase started")
        self._refresh_state()
        for token in [1, 2, 3, 4]:
            if self._round_timed_out():
                self._record_event("round_timeout", {"phase": "voting", "action": "auto_cast_remaining_votes"})
                for remaining_token in [t for t in [1, 2, 3, 4] if t >= token]:
                    remaining_player = self.engine.state.token_assignments[remaining_token]
                    if remaining_player in self.engine.state.votes:
                        continue
                    fallback_vote = self.rng.choice([0, 1])
                    self.engine.cast_vote(remaining_player, fallback_vote)
                    self._record_event(
                        "vote_cast",
                        {
                            "character": remaining_player.value,
                            "token": remaining_token,
                            "vote": fallback_vote,
                            "reason": "round_timeout_default",
                        },
                    )
                self._refresh_state()
                return

            player = self.engine.state.token_assignments[token]
            snapshot = self.engine.export_public_state()
            transcript_tail = self.engine.state.transcript[-20:]
            scratchpad_before = self.engine.state.scratchpads[player]

            vote: int
            try:
                result = await asyncio.wait_for(
                    self.player_agents[player].voting_action(snapshot, transcript_tail, scratchpad_before, token),
                    timeout=self.config.llm_request_timeout_seconds,
                )
                self._log_llm_exchange("player", player, result, scratchpad_before)
                self._record_parse_warning("player", player.value, "voting", result)
                new_scratchpad = result.get("scratchpad")
                if isinstance(new_scratchpad, str):
                    self.engine.state.scratchpads[player] = new_scratchpad
                utterance = (result.get("utterance") or "").strip()
                if utterance:
                    kept, _ = self.engine.record_utterance(player, utterance, binding_allowed=False)
                    if kept:
                        self._record_chat(f"{player.value}: {kept}")
                vote = int(result.get("vote"))
                if vote not in (0, 1):
                    raise ValueError("Vote must be 0 or 1")
            except asyncio.TimeoutError:
                self._record_event(
                    "agent_timeout",
                    {
                        "character": player.value,
                        "phase": "voting",
                        "timeout_seconds": self.config.llm_request_timeout_seconds,
                        "action": "forfeit_vote",
                    },
                )
                self.display.add_event(f"{player.value} timed out in voting; default vote applied")
                vote = self.rng.choice([0, 1])
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    "agent_error",
                    {"character": player.value, "phase": "voting", "error": str(exc), "action": "forfeit_vote"},
                )
                self.display.add_event(f"{player.value} voting error; default vote applied")
                vote = self.rng.choice([0, 1])

            if not self.engine.cast_vote(player, vote):
                fallback = self.rng.choice([0, 1])
                self.engine.cast_vote(player, fallback)
                vote = fallback

            self._record_event("vote_cast", {"character": player.value, "token": token, "vote": vote})
            self.display.add_event(f"{player.value} voted for proposal {vote}")
            self._refresh_state()
            await self._maybe_visual_delay()

            if self._round_timed_out():
                self._record_event("round_timeout", {"phase": "voting", "action": "skip_vote_change_window"})
                continue
            await self._run_vote_change_window(target=player)

    async def _run_vote_change_window(self, target: Character) -> None:
        actors = [p for p in CHARACTER_ORDER if p != target]

        async def one_action(actor: Character) -> tuple[Character, dict[str, Any] | None, float]:
            state = self.engine.export_public_state()
            transcript_tail = self.engine.state.transcript[-20:]
            scratchpad_before = self.engine.state.scratchpads[actor]
            try:
                result = await asyncio.wait_for(
                    self.player_agents[actor].vote_change_action(state, transcript_tail, scratchpad_before, target),
                    timeout=self.config.llm_request_timeout_seconds,
                )
                self._log_llm_exchange("player", actor, result, scratchpad_before)
                self._record_parse_warning("player", actor.value, "voting_change_window", result)
                new_scratchpad = result.get("scratchpad")
                if isinstance(new_scratchpad, str):
                    self.engine.state.scratchpads[actor] = new_scratchpad
                return actor, result, time.time()
            except asyncio.TimeoutError:
                self._record_event(
                    "agent_timeout",
                    {
                        "character": actor.value,
                        "phase": "voting_change_window",
                        "timeout_seconds": self.config.llm_request_timeout_seconds,
                        "action": "forfeit_vote_change",
                    },
                )
                self.display.add_event(f"{actor.value} vote-change timed out")
                self._refresh_state()
                return actor, None, time.time()
            except Exception as exc:  # noqa: BLE001
                self._record_event(
                    "agent_error",
                    {
                        "character": actor.value,
                        "phase": "voting_change_window",
                        "error": str(exc),
                        "action": "forfeit_vote_change",
                    },
                )
                return actor, None, time.time()

        tasks = [asyncio.create_task(one_action(actor)) for actor in actors]
        ordered_results: list[tuple[Character, dict[str, Any] | None, float]] = []
        for coro in asyncio.as_completed(tasks):
            ordered_results.append(await coro)

        for actor, result, ts in ordered_results:
            if not result:
                continue
            utterance = (result.get("utterance") or "").strip()
            if utterance:
                kept, _ = self.engine.record_utterance(actor, utterance, binding_allowed=False)
                if kept:
                    self._record_chat(f"{actor.value}: {kept}")

            action = result.get("action")
            new_vote = result.get("new_vote")
            if action == "none" or new_vote not in (0, 1):
                continue

            success = False
            if action == "use_target_token":
                success = self.engine.change_vote_using_target_token(actor, target, int(new_vote))
            elif action == "force_with_three_tokens":
                success = self.engine.force_vote_change_with_three_tokens(actor, target, int(new_vote))

            self._record_event(
                "vote_change_attempt",
                {
                    "actor": actor.value,
                    "target": target.value,
                    "action": action,
                    "new_vote": int(new_vote),
                    "timestamp": ts,
                    "success": success,
                },
            )
            if success:
                self.display.add_event(f"{actor.value} changed {target.value}'s vote")
                self._record_promise_transfer_event(actor, target, action, int(new_vote), ts)
            self._refresh_state()
            await self._maybe_visual_delay()

    async def _referee_phase_change(self, from_phase: str, to_phase: str) -> None:
        state = self.engine.export_public_state()
        transcript_tail = self.engine.state.transcript[-40:]
        contracts = state.get("contracts", {})
        self.display.add_event(f"Referee reviewing: {from_phase} -> {to_phase}")
        self._refresh_state()
        referee_scratchpad_before = self._referee_scratchpad
        try:
            result = await asyncio.wait_for(
                self.referee.evaluate_phase_change(
                    from_phase,
                    to_phase,
                    state,
                    transcript_tail,
                    contracts,
                    self._referee_scratchpad,
                ),
                timeout=self.config.llm_request_timeout_seconds,
            )
            self._log_llm_exchange("referee", None, result, referee_scratchpad_before)
            self._record_parse_warning("referee", "Referee", f"{from_phase}->{to_phase}", result)
            new_scratchpad = result.get("scratchpad")
            if isinstance(new_scratchpad, str):
                self._referee_scratchpad = new_scratchpad
        except asyncio.TimeoutError:
            self._record_event(
                "referee_timeout",
                {
                    "from": from_phase,
                    "to": to_phase,
                    "timeout_seconds": self.config.llm_request_timeout_seconds,
                },
            )
            self.display.add_event(f"Referee timeout on {from_phase}->{to_phase}; continuing without new rulings")
            self._refresh_state()
            return
        except Exception as exc:  # noqa: BLE001
            self._record_event(
                "referee_error",
                {"from": from_phase, "to": to_phase, "error": str(exc)},
            )
            self.display.add_event(f"Referee error on {from_phase}->{to_phase}: {str(exc)[:80]}")
            self._refresh_state()
            return

        rulings = self._humanize_referee_rulings(result)
        for line in rulings:
            self.display.add_ruling(line)
            self._record_event("referee_ruling", {"from": from_phase, "to": to_phase, "text": line})

        self._infer_contracts_from_rulings(rulings)
        self._apply_inferred_referee_enforcement_from_rulings(from_phase, to_phase, rulings)
        self._refresh_state()

    def _parse_character(self, raw: str) -> Character:
        normalized = raw.strip().lower().replace("'", "")
        mapping = {
            "carmichael": Character.CARMICHAEL,
            "quincy": Character.QUINCY,
            "medici": Character.MEDICI,
            "dambrosio": Character.DAMBROSIO,
        }
        if normalized not in mapping:
            raise ValueError(f"Unknown character: {raw}")
        return mapping[normalized]

    def _first_legal_token_for_player(self, player: Character) -> int | None:
        for token in (3, 4, 2, 1):
            if self.engine.can_take_token(player, token):
                return token
        return None

    def _humanize_referee_rulings(self, result: dict[str, Any]) -> list[str]:
        raw_rulings = result.get("rulings", [])
        if not isinstance(raw_rulings, list):
            return []
        lines: list[str] = []
        for ruling in raw_rulings:
            lines.extend(self._extract_human_ruling_lines(str(ruling)))
        return [line for line in lines if line]

    def _extract_human_ruling_lines(self, text: str) -> list[str]:
        cleaned = text.strip()
        if not cleaned:
            return []

        parsed = try_extract_json_object(cleaned)
        if isinstance(parsed, dict):
            raw = parsed.get("rulings", [])
            if isinstance(raw, list):
                return [self._clean_ruling_text(str(item)) for item in raw if str(item).strip()]

        de_fenced = self._strip_code_fence(cleaned)
        parsed_fenced = try_extract_json_object(de_fenced)
        if isinstance(parsed_fenced, dict):
            raw_fenced = parsed_fenced.get("rulings", [])
            if isinstance(raw_fenced, list):
                return [self._clean_ruling_text(str(item)) for item in raw_fenced if str(item).strip()]

        if "\n" in de_fenced:
            parts = [self._clean_ruling_text(part) for part in de_fenced.splitlines() if part.strip()]
            if parts:
                return parts[:8]
        return [self._clean_ruling_text(de_fenced)]

    def _strip_code_fence(self, text: str) -> str:
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _clean_ruling_text(self, text: str) -> str:
        normalized = " ".join(text.replace("`", "").split()).strip()
        if len(normalized) <= 280:
            return normalized
        return f"{normalized[:277]}..."

    def _infer_contracts_from_rulings(self, rulings: list[str]) -> None:
        for line in rulings:
            contract = self._inferred_contract_from_line(line)
            if contract is None:
                continue
            if contract.contract_id in self.engine.state.contracts:
                continue
            self.engine.add_or_update_contract(contract)
            self._record_event(
                "contract_added",
                {
                    "contract_id": contract.contract_id,
                    "parties": [p.value for p in contract.parties],
                    "text": contract.text,
                    "notes": contract.notes,
                    "source": "referee_ruling_inference",
                },
            )

    def _inferred_contract_from_line(self, line: str) -> Contract | None:
        cleaned = " ".join(line.strip().split())
        if not cleaned:
            return None
        if "committed to" not in cleaned.lower():
            return None

        pattern = re.compile(
            r"(?i)^(?:\d+[.)]\s*)?"
            r"(Carmichael|Quincy|Medici|D'Ambrosio)\s+"
            r"(?:made\s+)?(?:a\s+)?(?:binding\s+)?"
            r"(?:commitment|commitments)?\s*"
            r"(?:to:?\s*|committed to\s+)"
            r"(.+)$"
        )
        match = pattern.search(cleaned)
        if not match:
            return None

        actor = self._parse_character(match.group(1))
        clause = match.group(2).strip(" .")
        if len(clause) < 18:
            return None
        if not any(word in clause.lower() for word in ("vote", "support", "proposal", "round", "season")):
            return None

        parties = {actor, *self._characters_mentioned(clause)}
        if len(parties) < 2:
            return None

        normalized_text = f"{actor.value} committed to {clause}"
        digest = hashlib.sha1(
            f"{normalized_text.lower()}|{'|'.join(sorted(p.value for p in parties))}".encode("utf-8")
        ).hexdigest()[:10]
        contract_id = f"inferred_{digest}"
        return Contract(
            contract_id=contract_id,
            text=normalized_text,
            parties=tuple(sorted(parties, key=lambda c: c.value)),
            created_round=self.engine.state.round_number,
            notes="Inferred from referee ruling text",
        )

    def _characters_mentioned(self, text: str) -> set[Character]:
        lowered = text.lower()
        mentions: set[Character] = set()
        aliases = {
            Character.CARMICHAEL: ("carmichael",),
            Character.QUINCY: ("quincy",),
            Character.MEDICI: ("medici",),
            Character.DAMBROSIO: ("d'ambrosio", "dambrosio"),
        }
        for character, names in aliases.items():
            if any(name in lowered for name in names):
                mentions.add(character)
        return mentions

    def _apply_inferred_referee_enforcement_from_rulings(
        self,
        from_phase: str,
        to_phase: str,
        rulings: list[str],
    ) -> None:
        if from_phase != "voting" or to_phase != "resolution":
            return

        keywords = ("final vote state", "authoritative", "binding final vote", "final vote position")
        pattern = re.compile(
            r"(?i)\b(?:set|shift(?:ed)?|redirect(?:ed)?)\s+"
            r"(Carmichael|Quincy|Medici|D'Ambrosio)\s+"
            r"(?:to|toward)\s+proposal\s*([01])"
        )
        fallback_pattern = re.compile(
            r"(?i)\b(Carmichael|Quincy|Medici|D'Ambrosio)\b.{0,50}\bproposal\s*([01])\b"
        )

        applied_any = False
        for line in rulings:
            lowered = line.lower()
            if not any(key in lowered for key in keywords):
                continue
            match = pattern.search(line) or fallback_pattern.search(line)
            if not match:
                continue
            player = self._parse_character(match.group(1))
            vote = int(match.group(2))
            previous_vote = self.engine.state.votes.get(player)
            applied = self.engine.force_vote_by_referee(player, vote)
            self._record_event(
                "contract_enforcement",
                {
                    "from": from_phase,
                    "to": to_phase,
                    "action": "set_vote",
                    "player": player.value,
                    "previous_vote": previous_vote,
                    "enforced_vote": vote,
                    "applied": applied,
                    "contract_ids": [],
                    "reason": f"Inferred from referee ruling text: {self._clean_ruling_text(line)}",
                },
            )
            if applied:
                self.display.add_ruling(f"Referee enforcement: {player.value} vote set to proposal {vote}")
                self.display.add_event(f"Referee inferred and enforced {player.value}'s final vote state")
                self.engine.state.transcript.append(
                    f"Referee enforcement: {player.value} vote set to proposal {vote} (inferred from ruling)"
                )
                applied_any = True
        if applied_any:
            self._refresh_state()

    def _record_event(self, event_type: str, payload: dict[str, Any]) -> None:
        self.logger.log_event(
            event_type,
            self.engine.state.round_number,
            self.engine.state.phase.value,
            payload,
        )

    def _record_chat(self, line: str) -> None:
        self.display.add_chat(line)
        self.logger.log_transcript_line(line)

    def _log_llm_exchange(
        self,
        role: str,
        character: Character | None,
        result: dict[str, Any],
        scratchpad_before: str | None,
    ) -> None:
        scratchpad_after = result.get("scratchpad") if isinstance(result, dict) else None
        self.logger.log_llm(
            role=role,
            player=character.value if character else "Referee",
            prompt=result.get("_prompt", {}),
            response_text=result.get("_raw_text", ""),
            raw_response=result.get("_raw_response", {}),
            metadata={
                "attempts": result.get("_attempts", 0),
                "scratchpad_before": scratchpad_before,
                "scratchpad_after": scratchpad_after,
            },
        )
        actor_name = character.value if character else "Referee"
        usage = self._extract_usage_from_raw_response(result.get("_raw_response"))
        self._accumulate_usage(actor_name, usage)

    def _refresh_state(self) -> None:
        state = self.engine.export_public_state()
        state["scratchpads_view"] = {
            character.value: self.engine.state.scratchpads.get(character, "")
            for character in CHARACTER_ORDER
        } | {"Referee": self._referee_scratchpad}
        state["llm_usage"] = self._usage_snapshot()
        self.display.set_state(state)
        if self._live is not None:
            self._live.update(self.display.render())

    def _round_timed_out(self) -> bool:
        started_at = float(self.engine.state.metadata.get("round_started_at") or 0.0)
        if started_at <= 0:
            return False
        return (time.time() - started_at) >= self.config.round_timeout_seconds

    def _record_parse_warning(self, role: str, actor: str, phase: str, result: dict[str, Any]) -> None:
        warning = result.get("_parse_warning")
        if not warning:
            return
        self._record_event(
            "response_parse_warning",
            {
                "role": role,
                "actor": actor,
                "phase": phase,
                "warning": str(warning),
            },
        )
        self.display.add_event(f"{actor} response parsed with fallback in {phase}")

    async def _maybe_visual_delay(self) -> None:
        delay = max(0.0, self.config.visual_step_delay_seconds)
        if self.visual and delay > 0:
            await asyncio.sleep(delay)

    def _record_promise_transfer_event(
        self,
        actor: Character,
        target: Character,
        action: str,
        new_vote: int,
        timestamp: float,
    ) -> None:
        if action == "use_target_token":
            payload = {
                "method": "use_target_token",
                "actor": actor.value,
                "target": target.value,
                "owner_token": target.value,
                "amount": 1,
                "from_holder": actor.value,
                "to_holder": target.value,
                "new_vote": new_vote,
                "timestamp": timestamp,
            }
        elif action == "force_with_three_tokens":
            payload = {
                "method": "force_with_three_tokens",
                "actor": actor.value,
                "target": target.value,
                "owner_token": actor.value,
                "amount": 3,
                "from_holder": actor.value,
                "to_holder": target.value,
                "new_vote": new_vote,
                "timestamp": timestamp,
            }
        else:
            return
        self._record_event("promise_transfer", payload)

    def _model_for_actor(self, actor_name: str) -> str:
        override = (self.config.agent_models or {}).get(actor_name)
        if isinstance(override, str) and override.strip():
            return override.strip()
        return self.config.model_id

    def _client_for_model(self, model_id: str) -> BedrockConverseClient:
        if model_id in self._llm_clients_by_model:
            return self._llm_clients_by_model[model_id]
        cfg = self.config if model_id == self.config.model_id else replace(self.config, model_id=model_id)
        client = BedrockConverseClient(cfg)
        self._llm_clients_by_model[model_id] = client
        return client

    def _active_model_ids(self) -> list[str]:
        models = {
            self.config.model_id,
            self._model_for_actor("Referee"),
            *(self._model_for_actor(character.value) for character in CHARACTER_ORDER),
        }
        return sorted(models)

    def _new_usage_bucket(self) -> dict[str, int]:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }

    def _reset_round_usage(self) -> None:
        self._usage_round = self._new_usage_bucket()
        self._usage_requests_round = 0
        self._usage_requests_by_actor_round = {name: 0 for name in self._usage_actor_order}
        self._usage_by_actor_round = {name: self._new_usage_bucket() for name in self._usage_actor_order}

    def _extract_usage_from_raw_response(self, raw_response: Any) -> dict[str, int]:
        if not isinstance(raw_response, dict):
            return self._new_usage_bucket()
        usage = raw_response.get("usage", {})
        if not isinstance(usage, dict):
            return self._new_usage_bucket()
        return {
            "input_tokens": int(usage.get("inputTokens") or 0),
            "output_tokens": int(usage.get("outputTokens") or 0),
            "total_tokens": int(usage.get("totalTokens") or 0),
            "cache_read_tokens": int(usage.get("cacheReadInputTokens") or 0),
            "cache_write_tokens": int(usage.get("cacheWriteInputTokens") or 0),
        }

    def _accumulate_usage(self, actor: str, usage: dict[str, int]) -> None:
        if actor not in self._usage_by_actor_total:
            self._usage_actor_order.append(actor)
            self._usage_by_actor_total[actor] = self._new_usage_bucket()
            self._usage_by_actor_round[actor] = self._new_usage_bucket()
            self._usage_requests_by_actor_total[actor] = 0
            self._usage_requests_by_actor_round[actor] = 0

        for key in self._usage_totals:
            value = max(0, int(usage.get(key, 0)))
            self._usage_totals[key] += value
            self._usage_round[key] += value
            self._usage_by_actor_total[actor][key] += value
            self._usage_by_actor_round[actor][key] += value

        self._usage_requests_total += 1
        self._usage_requests_round += 1
        self._usage_requests_by_actor_total[actor] += 1
        self._usage_requests_by_actor_round[actor] += 1

    def _usage_snapshot(self) -> dict[str, Any]:
        return {
            "requests_total": self._usage_requests_total,
            "requests_round": self._usage_requests_round,
            "tokens_total": dict(self._usage_totals),
            "tokens_round": dict(self._usage_round),
            "by_actor_total": {name: dict(self._usage_by_actor_total[name]) for name in self._usage_actor_order},
            "by_actor_round": {name: dict(self._usage_by_actor_round[name]) for name in self._usage_actor_order},
            "requests_by_actor_total": dict(self._usage_requests_by_actor_total),
            "requests_by_actor_round": dict(self._usage_requests_by_actor_round),
        }
