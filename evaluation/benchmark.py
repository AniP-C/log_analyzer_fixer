from __future__ import annotations

import asyncio
import json

from app.core.agent_core import FlowFixAgent


async def run() -> None:
    agent = FlowFixAgent()
    results = await agent.run_benchmark()
    print(json.dumps(results.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(run())
