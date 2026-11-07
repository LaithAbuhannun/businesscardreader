import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # makes "import server" work

import server  # noqa: E402
from helpers import FakeDetector, FakeExtractor  # noqa: E402

# Settings a developer might put in .env that would change how the app behaves
# under test. Each test starts without them, so local .env files can't affect results.
APP_SETTINGS = (
    "BCR_COOKIE_SECURE",
    "BCR_DATA_DIR",
    "BCR_CONFIDENCE",
    "BCR_IOU",
    "BCR_MODEL_PATH",
    "BCR_OPENAI_MODEL",
    "BCR_SESSION_HOURS",
    "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in APP_SETTINGS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("BCR_SECRET_KEY", "test-secret")

    def factory(detector=None, extractor=None):
        app = server.create_app(
            {"TESTING": True, "DATA_DIR": str(tmp_path)},
            detector=detector or FakeDetector(),
            extractor=extractor or FakeExtractor(),
        )
        return app.test_client()

    return factory


@pytest.fixture
def client(make_client):
    return make_client()
