"""
Management command to import OCP data.

Usage:
    python manage.py import_data
    python manage.py import_data --url https://example.com/full.csv.tar.gz
"""
from django.core.management.base import BaseCommand, CommandError
from apps.ingestion.services.csv_importer import (
    download_csv_bundle,
    import_csv_to_raw,
    validate_and_import_records,
)


class Command(BaseCommand):
    help = 'Import procurement data from the OCP Data Registry CSV bundle'

    def add_arguments(self, parser):
        parser.add_argument(
            '--url',
            type=str,
            help='Override download URL for the CSV bundle',
        )
        parser.add_argument(
            '--skip-download',
            action='store_true',
            help='Skip download and use existing CSV in data/raw/',
        )

    def handle(self, *args, **options):
        try:
            if options['skip_download']:
                from pathlib import Path
                from django.conf import settings
                csv_path = Path(settings.DATA_RAW_DIR) / 'full.csv'
                if not csv_path.exists():
                    raise CommandError(f'No CSV found at {csv_path}. Run without --skip-download first.')
                self.stdout.write(f'Using existing CSV: {csv_path}')
            else:
                self.stdout.write('Downloading OCP data bundle...')
                csv_path = download_csv_bundle(url=options.get('url'))
                self.stdout.write(self.style.SUCCESS(f'Downloaded: {csv_path}'))

            self.stdout.write('Importing raw records...')
            import_stats = import_csv_to_raw(csv_path)
            self.stdout.write(self.style.SUCCESS(f'Import stats: {import_stats}'))

            self.stdout.write('Validating and importing into main tables...')
            validation_stats = validate_and_import_records()
            self.stdout.write(self.style.SUCCESS(f'Validation stats: {validation_stats}'))

            self.stdout.write(self.style.SUCCESS('Data import complete.'))

        except Exception as e:
            raise CommandError(f'Import failed: {e}')
