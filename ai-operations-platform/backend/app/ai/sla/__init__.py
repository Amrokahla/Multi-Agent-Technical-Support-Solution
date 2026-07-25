"""SLA breach-risk model — features, calibrated classifier, and the staffing overlay.

Ported from backend/notebooks/05_sla_risk.ipynb: a single HistGradientBoosting
classifier (metric as a feature) with isotonic calibration, trained on real
breach/fulfill labels using only intake-known features (no outcome leakage).
"""
