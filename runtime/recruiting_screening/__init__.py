"""Synthetic screening and department-decision control plane.

This package deliberately reuses the intake control's public ``submit`` / ``read``
seam and its authoritative ``application_cases`` rows.  It proves bounded domain
semantics with synthetic facts; it is not a model, IAM, messaging, or worker
integration.
"""

from .control import RecruitingG2Control
from .synthetic import SyntheticClock, build_synthetic_screening

__all__ = ["RecruitingG2Control", "SyntheticClock", "build_synthetic_screening"]
