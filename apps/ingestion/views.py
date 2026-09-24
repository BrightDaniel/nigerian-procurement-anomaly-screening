import os
import tempfile
from pathlib import Path
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from apps.accounts.decorators import administrator_required
from .services.csv_importer import import_csv_to_raw, validate_and_import_records


@login_required
@administrator_required
def import_data_view(request):
    context = {'stats': None, 'error': None, 'imported_file': None}
    if request.method == 'POST':
        uploaded_file = request.FILES.get('csv_file')
        use_ocp = request.POST.get('use_ocp')

        try:
            if uploaded_file:
                # Save uploaded file to temp location
                dest_dir = Path(settings.DATA_RAW_DIR)
                dest_dir.mkdir(parents=True, exist_ok=True)
                csv_path = dest_dir / 'full.csv'

                with open(csv_path, 'wb') as f:
                    for chunk in uploaded_file.chunks():
                        f.write(chunk)
                context['imported_file'] = uploaded_file.name
            elif use_ocp:
                from .services.csv_importer import download_csv_bundle
                csv_path = download_csv_bundle()
            else:
                context['error'] = 'No file selected. Please upload a CSV file or use the OCP download.'
                return render(request, 'ingestion/import.html', context)

            import_stats = import_csv_to_raw(csv_path)
            validation_stats = validate_and_import_records()
            context['stats'] = {
                'import': import_stats,
                'validation': validation_stats,
            }
        except Exception as e:
            context['error'] = str(e)
    return render(request, 'ingestion/import.html', context)
