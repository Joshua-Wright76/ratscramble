from __future__ import annotations

import asyncio

from src.config.loader import load_simulation_config
from src.game.orchestrator import SimulationOrchestrator


async def _main() -> None:
    config = load_simulation_config("config.yml")
    orchestrator = SimulationOrchestrator(config=config, visual=False)
    summary = await orchestrator.run()
    print(summary)


if __name__ == "__main__":
    asyncio.run(_main())
