from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel


class ProcuringEntity(TimeStampedModel):
    """MDA (Ministry, Department, or Agency) that procures goods/services."""
    entity_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'procuring_entities'
        verbose_name = 'Procuring Entity'
        verbose_name_plural = 'Procuring Entities'

    def __str__(self):
        return self.name


class Vendor(TimeStampedModel):
    """Supplier/vendor that receives contract awards."""
    vendor_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    cac_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendor'
        verbose_name_plural = 'Vendors'

    def __str__(self):
        return self.name


class Contract(TimeStampedModel):
    """Individual procurement contract record — fact table."""
    contract_id = models.AutoField(primary_key=True)
    entity = models.ForeignKey(
        ProcuringEntity,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts',
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contracts',
    )
    title = models.TextField()
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=10, default='NGN')
    award_date = models.DateField(blank=True, null=True)
    bidding_window_days = models.IntegerField(blank=True, null=True)
    num_bidders = models.IntegerField(blank=True, null=True)
    method = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    nocopo_id = models.CharField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        db_table = 'contracts'
        verbose_name = 'Contract'
        verbose_name_plural = 'Contracts'

    def __str__(self):
        return f'{self.title} ({self.nocopo_id})'


class ImportJob(TimeStampedModel):
    """A background execution of the CSV/OCP import pipeline.

    The import pipeline (staging + validation + contract creation) takes
    minutes on the full dataset, so it runs in a background thread and
    reports progress through this row: stage text and heartbeats are
    persisted so the Import page can show live status, survive refreshes,
    and detect interrupted runs.
    """

    STATUS_QUEUED = 'queued'
    STATUS_RUNNING = 'running'
    STATUS_SUCCEEDED = 'succeeded'
    STATUS_FAILED = 'failed'
    STATUS_INTERRUPTED = 'interrupted'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_SUCCEEDED, 'Succeeded'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_INTERRUPTED, 'Interrupted'),
    ]

    SOURCE_UPLOAD = 'upload'
    SOURCE_OCP = 'ocp'
    SOURCE_CHOICES = [
        (SOURCE_UPLOAD, 'Uploaded CSV'),
        (SOURCE_OCP, 'OCP Data Registry download'),
    ]

    job_id = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    stage = models.CharField(max_length=200, blank=True, default='')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_OCP)
    source_name = models.CharField(max_length=255, blank=True, default='')
    csv_path = models.CharField(max_length=500, blank=True, default='')
    error = models.TextField(blank=True, default='')
    staging = models.JSONField(null=True, blank=True)
    validation = models.JSONField(null=True, blank=True)
    totals = models.JSONField(null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='import_jobs',
    )
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'import_jobs'
        verbose_name = 'Import Job'
        verbose_name_plural = 'Import Jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f'Import job {self.job_id} — {self.status} ({self.created_at:%Y-%m-%d %H:%M})'


class RawRecord(TimeStampedModel):
    """Staging table — raw imported data before schema validation.
    Nothing is written to `contracts` unschema-checked.
    """
    raw_id = models.AutoField(primary_key=True)
    source_file = models.CharField(max_length=255)
    ocds_release = models.JSONField()
    is_validated = models.BooleanField(default=False)
    validation_errors = models.JSONField(blank=True, null=True)
    is_imported = models.BooleanField(default=False)

    class Meta:
        db_table = 'raw_records'
        verbose_name = 'Raw Record'
        verbose_name_plural = 'Raw Records'

    def __str__(self):
        return f'Raw {self.raw_id} from {self.source_file}'
