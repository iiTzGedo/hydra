"""Entry point for running hydra-mcp as a module."""

import asyncio

from hydra_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
