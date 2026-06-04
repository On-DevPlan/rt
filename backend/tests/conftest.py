import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from rt_backend.tts.cache import TTSCache
from rt_backend.tts.router import build_router


@pytest.fixture
def client_app():
    cache = TTSCache(":memory:")
    app = FastAPI()
    app.include_router(build_router(lambda: cache))
    with TestClient(app) as client:
        yield client
