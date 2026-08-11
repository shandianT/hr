"""Executable G1a control-plane reference module.

Callers and behaviour tests use the same two-entry interface: ``submit`` and
``read``.  Storage and domain handlers remain private implementation details.
"""

from .control import RecruitingCaseControl

__all__ = ["RecruitingCaseControl"]
