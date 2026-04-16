import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.main import app, scraper


@pytest_asyncio.fixture
async def client():
    await scraper.start()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await scraper.stop()
