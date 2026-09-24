from django.db import models
from apps.core.models import TimeStampedModel
from apps.ingestion.models import Contract


class Feature(TimeStampedModel):
    """Computed risk features for a contract — 1:1 with contracts table."""
    feature_id = models.AutoField(primary_key=True)
    contract = models.OneToOneField(
        Contract,
        on_delete=models.CASCADE,
        related_name='features',
    )
    price_deviation = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    single_bidder_flag = models.BooleanField(default=False)
    vendor_win_frequency = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    vendor_win_concentration = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True)
    splitting_flag = models.BooleanField(default=False)
    splitting_count = models.IntegerField(default=0)
    log_contract_value = models.DecimalField(max_digits=15, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = 'features'
        verbose_name = 'Feature'
        verbose_name_plural = 'Features'

    def __str__(self):
        return f'Features for Contract {self.contract_id}'
