"""Tuning constants for the WFM pipeline.

These mirror the values validated in the notebooks. They are model assumptions,
not data — kept in one place so every stage reads the same numbers.
"""

from __future__ import annotations

# Target agent utilization (occupancy). Required agents = workload / UTIL.
UTIL_TARGET = 0.8

# Agent-occupied handle time per ticket = base triage + minutes per agent reply.
# This is agent-busy time, NOT elapsed resolution time.
HANDLE_BASE_MIN = 6
HANDLE_PER_REPLY_MIN = 12

# Recent window (days back from the dataset "now") where agent shifts exist.
WINDOW_DAYS = 56

# Custom-field ids on the Zendesk ticket carrying WFM signal.
CF_LOCALE = 900001
CF_QUEUE = 900002

# Variant tickets (the LLM-paraphrased H2 echo) have ids above this threshold.
VARIANT_ID_THRESHOLD = 5000

# Symmetric colour range for the coverage-gap heatmap (agents over/under).
GAP_HEATMAP_LIMIT = 8
