"""Workforce optimization pipeline: forecast -> capacity -> coverage -> optimize.

Ported from the validated notebooks in backend/notebooks/01-04. Each module is a
pure computation over pandas frames supplied by ``loaders``; the service layer
(``app.services.wfm``) caches the results and maps them to response schemas.
"""
