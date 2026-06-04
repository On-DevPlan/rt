import pytest
from httpx import AsyncClient

from rt_backend.core.http import HttpClientHolder


@pytest.mark.asyncio
async def test_holder_starts_and_closes_client():
    holder = HttpClientHolder(timeout=5.0)
    assert holder.client is None
    await holder.start()
    assert isinstance(holder.client, AsyncClient)
    await holder.close()
    assert holder.client is None


@pytest.mark.asyncio
async def test_holder_idempotent():
    holder = HttpClientHolder()
    await holder.start()
    first = holder.client
    await holder.start()  # second call should not replace
    assert holder.client is first
    await holder.close()
