"""Pytest configuration for BDD tests."""

import pytest


@pytest.fixture
def context():
    """Shared context for BDD tests."""
    return {}
