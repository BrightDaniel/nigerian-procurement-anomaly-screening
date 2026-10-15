from django.urls import path
from . import views

app_name = 'ingestion'

urlpatterns = [
    path('import/', views.import_data_view, name='import_data'),
    path('import/status/<int:job_id>/', views.import_status_view, name='import_status'),
]
