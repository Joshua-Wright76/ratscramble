from __future__ import annotations

from dataclasses import dataclass

from src.llm.bedrock_client import BedrockConverseClient


@dataclass
class BaseAgent:
    name: str
    llm: BedrockConverseClient
