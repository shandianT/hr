"""Synthetic resume-intake control plane.

The public seam is deliberately small: callers submit commands and read a
tenant projection.  Parsing models, mailbox connectors and storage details are
outside this first executable slice.
"""

from .control import ResumeIntakeControl
from .synthetic import build_synthetic_intake

__all__ = ["ResumeIntakeControl", "build_synthetic_intake"]
