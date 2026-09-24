from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.ingestion.models import Contract


class InvestigationReport(TimeStampedModel):
    """Stores investigation notes for flagged anomalies."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('reviewed', 'Reviewed'),
    ]

    report_id = models.AutoField(primary_key=True)
    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name='investigation_reports',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='investigation_reports',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    finding = models.TextField(blank=True, default='')
    recommendation = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'investigation_reports'
        verbose_name = 'Investigation Report'
        verbose_name_plural = 'Investigation Reports'
        ordering = ['-created_at']

    def __str__(self):
        return f'Report {self.report_id} — Contract {self.contract_id}'
