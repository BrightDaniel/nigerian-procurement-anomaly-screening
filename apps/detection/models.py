from django.db import models
from apps.core.models import TimeStampedModel
from apps.ingestion.models import Contract


class AnalysisRun(TimeStampedModel):
    """Records a single detection model execution run for audit/history."""
    run_id = models.AutoField(primary_key=True)
    model_name = models.CharField(max_length=50)
    contamination = models.FloatField(default=0.05)
    n_samples = models.IntegerField(default=0)
    n_features = models.IntegerField(default=0)
    n_anomalies = models.IntegerField(default=0)
    score_mean = models.FloatField(null=True, blank=True)
    score_std = models.FloatField(null=True, blank=True)
    score_min = models.FloatField(null=True, blank=True)
    score_max = models.FloatField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, default='completed')
    params = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'analysis_runs'
        verbose_name = 'Analysis Run'
        verbose_name_plural = 'Analysis Runs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.model_name} — {self.created_at:%Y-%m-%d %H:%M}'


class AnomalyFlag(TimeStampedModel):
    """Anomaly scoring result — one per contract per model."""
    flag_id = models.AutoField(primary_key=True)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='anomaly_flags',
    )
    risk_score = models.DecimalField(max_digits=8, decimal_places=6)
    model_used = models.CharField(max_length=50)
    is_anomaly = models.BooleanField(default=False)
    explanation_text = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'anomaly_flags'
        verbose_name = 'Anomaly Flag'
        verbose_name_plural = 'Anomaly Flags'
        unique_together = [['contract', 'model_used']]

    def __str__(self):
        return f'Flag {self.flag_id} - Contract {self.contract_id} ({self.risk_score})'
