"""Copilot orchestrator: the on-command LLM agent that plans and calls tools.

The registry (this phase) exposes tool schemas to the LLM and dispatches tool
calls safely. The orchestrator loop + provider land in a later phase.
"""
