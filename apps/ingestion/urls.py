from django.urls import path
from . import views

app_name = 'ingestion'

urlpatterns = [
    path('import/', views.import_data_view, name='import_data'),
]
