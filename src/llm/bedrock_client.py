from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from src.config.settings import SimulationConfig


@dataclass
class LLMResult:
    text: str
    raw_response: dict[str, Any]
    attempts: int
    stop_reason: str | None
    tool_calls: list[dict[str, Any]]


class BedrockConverseClient:
    def __init__(self, config: SimulationConfig):
        self.config = config
        session = boto3.Session(profile_name=config.aws_profile) if config.aws_profile else boto3.Session()
        self.client = session.client("bedrock-runtime", region_name=config.region)
        self.sts = session.client("sts", region_name=config.region)

    async def converse(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        retries = self.config.request_retries
        backoff = self.config.request_retry_backoff_seconds
        last_exc: Exception | None = None

        for attempt in range(retries + 1):
            try:
                payload = {
                    "modelId": self.config.model_id,
                    "system": [{"text": system_prompt}],
                    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
                    "inferenceConfig": {
                        "temperature": self.config.temperature if temperature is None else temperature,
                        "maxTokens": self.config.max_tokens if max_tokens is None else max_tokens,
                    },
                }
                return await self._invoke_with_retries(payload, attempt)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= retries:
                    break
                wait_seconds = backoff[min(attempt, len(backoff) - 1)]
                await asyncio.sleep(wait_seconds)
        readable = self._format_exception(last_exc)
        raise RuntimeError(f"Bedrock converse failed after {retries + 1} attempts: {readable}")

    async def converse_with_tools(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        tools: list[dict[str, Any]],
        tool_choice: str = "any",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        retries = self.config.request_retries
        backoff = self.config.request_retry_backoff_seconds
        last_exc: Exception | None = None

        for attempt in range(retries + 1):
            try:
                payload = {
                    "modelId": self.config.model_id,
                    "system": [{"text": system_prompt}],
                    "messages": [{"role": "user", "content": [{"text": user_prompt}]}],
                    "inferenceConfig": {
                        "temperature": self.config.temperature if temperature is None else temperature,
                        "maxTokens": self.config.max_tokens if max_tokens is None else max_tokens,
                    },
                    "toolConfig": {
                        "tools": tools,
                        "toolChoice": self._tool_choice_payload(tool_choice),
                    },
                }
                return await self._invoke_with_retries(payload, attempt)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt >= retries:
                    break
                wait_seconds = backoff[min(attempt, len(backoff) - 1)]
                await asyncio.sleep(wait_seconds)
        readable = self._format_exception(last_exc)
        raise RuntimeError(f"Bedrock converse (tools) failed after {retries + 1} attempts: {readable}")

    async def preflight_check(self) -> dict[str, str]:
        identity = await asyncio.to_thread(self.sts.get_caller_identity)
        return {
            "account": str(identity.get("Account", "")),
            "arn": str(identity.get("Arn", "")),
            "region": self.config.region,
            "model_id": self.config.model_id,
        }

    async def _invoke_with_retries(self, payload: dict[str, Any], attempt: int) -> LLMResult:
        response = await asyncio.to_thread(self.client.converse, **payload)
        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        for chunk in response.get("output", {}).get("message", {}).get("content", []):
            text = chunk.get("text")
            if text:
                text_chunks.append(text)
            tool_use = chunk.get("toolUse")
            if tool_use:
                tool_calls.append(
                    {
                        "tool_use_id": str(tool_use.get("toolUseId", "")),
                        "name": str(tool_use.get("name", "")),
                        "input": tool_use.get("input", {}),
                    }
                )
        return LLMResult(
            text="\n".join(text_chunks).strip(),
            raw_response=response,
            attempts=attempt + 1,
            stop_reason=response.get("stopReason"),
            tool_calls=tool_calls,
        )

    def _tool_choice_payload(self, choice: str) -> dict[str, Any]:
        if choice == "auto":
            return {"auto": {}}
        if choice == "any":
            return {"any": {}}
        if choice == "none":
            return {"auto": {}}
        if choice.startswith("tool:"):
            return {"tool": {"name": choice.split(":", 1)[1]}}
        return {"any": {}}

    def _format_exception(self, exc: Exception | None) -> str:
        if exc is None:
            return "Unknown Bedrock error"
        if isinstance(exc, NoCredentialsError):
            return "No AWS credentials found. Configure credentials or run aws sso login."
        if isinstance(exc, ClientError):
            code = str(exc.response.get("Error", {}).get("Code", "ClientError"))
            message = str(exc.response.get("Error", {}).get("Message", str(exc)))
            if code in {"ExpiredTokenException", "UnrecognizedClientException", "InvalidClientTokenId"}:
                return (
                    f"{code}: credentials expired/invalid. "
                    "Run aws sso login (or refresh credentials) and verify AWS_PROFILE."
                )
            if code in {"AccessDeniedException", "UnauthorizedOperation"}:
                return (
                    f"{code}: missing Bedrock permissions. "
                    "Need bedrock:InvokeModel and bedrock:InvokeModelWithResponseStream."
                )
            if code == "ResourceNotFoundException":
                return (
                    f"{code}: model/profile not found in this region. "
                    f"Check model_id and region ({self.config.region})."
                )
            return f"{code}: {message}"
        return str(exc)
