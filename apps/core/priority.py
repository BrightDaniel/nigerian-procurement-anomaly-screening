"""
Single source of truth for the application's priority scheme.

Every screen that labels a priority (Dashboard queue, Anomaly Queue,
Investigation Reports, Record/Anomaly Detail, Model Performance) maps the
persisted AnomalyFlag.risk_score to a band using the same absolute
thresholds:

    High   — risk_score >= 0.80
    Medium — risk_score >= 0.60 and risk_score < 0.80
    Normal — risk_score <  0.60

risk_score is the normalized [0, 1] score stored on AnomalyFlag
(1 = most anomalous). The bands are absolute and applied uniformly to both
detectors' flags, so the same score means the same priority everywhere.

The percentile values in apps.detection.trainer.PRIORITY_THRESHOLDS
(95th/80th) are training-time analysis artifacts logged with run
statistics; they are deliberately not used to label anything in the
interface.
"""

from decimal import Decimal

HIGH_MIN_SCORE = Decimal('0.80')
MEDIUM_MIN_SCORE = Decimal('0.60')

PRIORITY_CHOICES = ('high', 'medium', 'normal')


def priority_for_score(score):
    """Map an anomaly risk_score to 'high', 'medium', or 'normal'."""
    if score is None:
        return 'normal'
    s = float(score)
    if s >= float(HIGH_MIN_SCORE):
        return 'high'
    if s >= float(MEDIUM_MIN_SCORE):
        return 'medium'
    return 'normal'


def priority_label(priority):
    """Human-readable label for a priority band."""
    return {'high': 'High', 'medium': 'Medium', 'normal': 'Normal'}.get(priority, 'Normal')


def priority_scheme_text():
    """Documented description of the bands, for display on analytics screens."""
    return (
        f'Priority bands (applied uniformly to every screen): '
        f'High ≥ {HIGH_MIN_SCORE:.2f}, Medium ≥ {MEDIUM_MIN_SCORE:.2f}, '
        f'Normal < {MEDIUM_MIN_SCORE:.2f}.'
    )
