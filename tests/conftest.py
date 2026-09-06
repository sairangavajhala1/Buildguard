"""Shared pytest fixtures for the BuildGuard test suite."""

import pytest


@pytest.fixture(autouse=True)
def default_dodo_product_id(monkeypatch):
    """Pin a product id so endpoint/service tests never hit product resolution.

    Individual tests may still delete or override it with their own monkeypatch
    calls.
    """
    monkeypatch.setenv("DODO_PRODUCT_ID", "pdt_test_escrow")
    yield