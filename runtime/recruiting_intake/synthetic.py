"""Synthetic-only intake fixture builder."""

import sqlite3

from .control import ResumeIntakeControl


def build_synthetic_intake() -> ResumeIntakeControl:
    """Create an isolated in-memory control plane with no real personal data."""

    return ResumeIntakeControl(sqlite3.connect(":memory:"))
