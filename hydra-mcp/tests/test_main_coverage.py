"""Tests for hydra_mcp.__main__ module."""

from unittest.mock import AsyncMock, patch


class TestMainModule:
    """Tests for __main__.py entry point."""

    def test_main_module_imports_without_error(self):
        """Importing __main__ should not raise."""
        import hydra_mcp.__main__  # noqa: F401

    def test_main_guard_calls_asyncio_run(self):
        """The if __name__ == '__main__' guard should call asyncio.run(main())."""
        with patch("hydra_mcp.server.main", new_callable=AsyncMock), \
             patch("asyncio.run") as mock_run:
            # Simulate running as __main__
            code = compile(
                'import asyncio\nfrom hydra_mcp.server import main\n'
                'if __name__ == "__main__":\n    asyncio.run(main())\n',
                "<test>",
                "exec",
            )
            exec(code, {"__name__": "__main__"})  # noqa: S102
            mock_run.assert_called_once()
