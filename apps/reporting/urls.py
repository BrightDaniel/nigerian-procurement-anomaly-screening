from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    path('', views.report_list_view, name='report_list'),
    path('<int:contract_id>/', views.report_detail_view, name='report_detail'),
    path('<int:contract_id>/create/', views.report_create_view, name='report_create'),
]
