from django.db import models
from apps.ingestion.models import Contract


class Explanation(models.Model):
    """SHAP explanation data for an anomaly flag."""
    explanation_id = models.AutoField(primary_key=True)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='explanations',
    )
    model_used = models.CharField(max_length=50, default='isolation_forest')
    shap_values = models.JSONField()
    feature_importance = models.JSONField()
    force_plot_data = models.JSONField(blank=True, null=True)
    natural_language = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'explanations'
        verbose_name = 'Explanation'
        verbose_name_plural = 'Explanations'
        unique_together = [['contract', 'model_used']]

    def __str__(self):
        return f'Explanation for Contract {self.contract_id} ({self.model_used})'
