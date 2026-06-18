"""Authoritative judgment guards — block, do not merely log."""

from judgment.guards.harm_aware import apply_harm_guard
from judgment.guards.safe_divergence import apply_safe_divergence

__all__ = ["apply_harm_guard", "apply_safe_divergence"]
