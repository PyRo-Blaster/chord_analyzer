from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE0_FIXTURES = REPO_ROOT / "fixtures" / "phase0"


@pytest.fixture
def phase0_fixtures() -> Path:
    return PHASE0_FIXTURES
