from pathlib import Path

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings

from apps.accounts.decorators import administrator_required
from .models import ImportJob
from .services.import_job import (
    start_import_job,
    job_status,
    latest_job,
    ImportAlreadyRunning,
)


@login_required
@administrator_required
def import_data_view(request):
    """Import Dataset — queues a background import job (POST) or shows status."""
    if request.method == 'POST':
        uploaded_file = request.FILES.get('csv_file')
        use_ocp = request.POST.get('use_ocp')

        if uploaded_file:
            dest_dir = Path(settings.DATA_RAW_DIR)
            dest_dir.mkdir(parents=True, exist_ok=True)
            csv_path = dest_dir / 'full.csv'
            with open(csv_path, 'wb') as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)
            source = ImportJob.SOURCE_UPLOAD
            source_name = uploaded_file.name
        elif use_ocp:
            source = ImportJob.SOURCE_OCP
            source_name = 'OCP Data Registry — Publication 64'
            csv_path = ''
        else:
            messages.error(request, 'No file selected. Please upload a CSV file or use the OCP download.')
            return redirect('ingestion:import_data')

        try:
            job = start_import_job(
                request.user,
                source=source,
                csv_path=csv_path,
                source_name=source_name,
            )
            messages.success(
                request,
                f'Import job #{job.job_id} queued — progress and results appear on this page.',
            )
        except ImportAlreadyRunning as exc:
            messages.info(request, str(exc))
        return redirect('ingestion:import_data')

    job = latest_job()
    status = job_status(job) if job else None
    context = {
        'job': job,
        'job_status': status,
        'job_active': bool(status and status['status'] in ('queued', 'running')),
    }
    return render(request, 'ingestion/import.html', context)


@login_required
@administrator_required
def import_status_view(request, job_id):
    """JSON status of an import job — polled by the Import page."""
    job = get_object_or_404(ImportJob, pk=job_id)
    return JsonResponse(job_status(job))
