"""Pydantic DTOs — the API contract (BUILD_SPEC §5 shapes, JSON-safe).

Domain NaNs (e.g. per-share value with zero shares) become JSON `null`.
"""
