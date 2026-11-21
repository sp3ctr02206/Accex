"""The mock catalog must match the real one, so the brain sees the same actions either way."""
from __future__ import annotations

from actions.executor import RegistryExecutor
from mocks.actions import DEMO_SPECS


def test_mock_specs_match_real():
    assert DEMO_SPECS == RegistryExecutor().specs()
