from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('anomalies/', views.anomalies_view, name='anomalies'),
    path('anomalies/<int:contract_id>/', views.anomaly_detail_view, name='anomaly_detail'),
    path('records/', views.records_view, name='records'),
    path('records/<int:contract_id>/', views.record_detail_view, name='record_detail'),
    path('analysis-runs/', views.analysis_runs_view, name='analysis_runs'),
    path('model-performance/', views.model_performance_view, name='model_performance'),
]
