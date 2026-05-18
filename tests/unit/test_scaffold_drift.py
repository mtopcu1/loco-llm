"""Tests for passive scaffold drift detection."""
from __future__ import annotations

import pytest

from llm_cli.core.scaffold_drift import DriftSeverity, classify_drift


def test_classify_drift_ok() -> None:
    assert classify_drift("0.4.1", "v0.4.1") == DriftSeverity.OK


def test_classify_drift_patch() -> None:
    assert classify_drift("0.4.1", "v0.4.0") == DriftSeverity.PATCH


def test_classify_drift_minor() -> None:
    assert classify_drift("0.5.0", "v0.4.1") == DriftSeverity.MINOR_OR_MAJOR


def test_classify_drift_missing() -> None:
    assert classify_drift("0.4.1", None) == DriftSeverity.MISSING
