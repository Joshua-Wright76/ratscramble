from __future__ import annotations

import asyncio

from rich.console import Console

from src.config.loader import load_simulation_config
from src.game.orchestrator import SimulationOrchestrator


async def _main() -> None:
    config = load_simulation_config("config.yml")
    orchestrator = SimulationOrchestrator(config=config, visual=True)
    summary = await orchestrator.run()
    console = Console()
    console.print("\nSimulation complete")
    console.print(summary)


if __name__ == "__main__":
    asyncio.run(_main())
