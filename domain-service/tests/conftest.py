import os

import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def client():
    if os.getenv("FORCE_EXTERNAL_TEST_BASE_URL") == "1":
        test_url = os.getenv("TEST_BASE_URL")
        if not test_url:
            raise RuntimeError("FORCE_EXTERNAL_TEST_BASE_URL=1 requires TEST_BASE_URL")
        async with AsyncClient(base_url=test_url, timeout=30.0) as ac:
            yield ac
        return

    # Default deterministic mode: direct ASGI app without external network calls.
    from httpx import ASGITransport
    from src.main import app, scraper
    await scraper.start()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await scraper.stop()
