import os

import pytest_asyncio
from httpx import AsyncClient

from src.config import settings


@pytest_asyncio.fixture
async def client():
    test_url = os.getenv("TEST_BASE_URL", settings.test_base_url)
    if test_url and test_url != "http://test":
        async with AsyncClient(base_url=test_url, timeout=30.0) as ac:
            yield ac
        return

    # Fallback for local direct ASGI tests
    from httpx import ASGITransport
    from src.main import app, scraper
    await scraper.start()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await scraper.stop()
