"""
Management command to generate risk features from imported contracts.

Usage:
    python manage.py generate_features
"""
from django.core.management.base import BaseCommand

from apps.features.engineering import compute_all_features
from apps.ingestion.models import Contract
from apps.features.models import Feature


class Command(BaseCommand):
    help = 'Generate procurement-risk features from imported contracts'

    def handle(self, *args, **options):
        contract_count = Contract.objects.count()
        if contract_count == 0:
            self.stdout.write(self.style.WARNING('No contracts found. Run import_data first.'))
            return

        self.stdout.write(f'Found {contract_count} contracts. Generating features...')

        count = compute_all_features()

        self.stdout.write(self.style.SUCCESS(
            f'Feature generation complete: {count} feature records created/updated.'
        ))

        # Show summary
        feature_count = Feature.objects.count()
        self.stdout.write(f'Total features in database: {feature_count}')
