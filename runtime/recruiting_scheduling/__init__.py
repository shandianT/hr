"""Synthetic-only interview scheduling control plane.

Business-state reads and writes use only ``submit`` and case-bound ``read``.
``bind_synthetic_case`` and ``synthetic_case_id`` are inherited G2 fixture
setup helpers used by the synthetic test harness; they are not business APIs.
The package does not connect to a real calendar, meeting, or invitation
provider.
"""

from .control import RecruitingSchedulingControl
from .synthetic import (
    SyntheticSchedulingAdapters,
    build_synthetic_scheduling,
)

__all__ = [
    "RecruitingSchedulingControl",
    "SyntheticSchedulingAdapters",
    "build_synthetic_scheduling",
]
