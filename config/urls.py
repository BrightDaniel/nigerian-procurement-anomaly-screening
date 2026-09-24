from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.dashboard import views as dashboard_views
from apps.accounts import views as accounts_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('ingestion/', include('apps.ingestion.urls')),
    path('reports/', include('apps.reporting.urls')),

    # Analytics — aligned with DESIGN.md
    path('analytics/runs/', dashboard_views.analysis_runs_view, name='analytics_runs'),
    path('analytics/performance/', dashboard_views.model_performance_view, name='analytics_performance'),

    # Administration — aligned with DESIGN.md (server-side enforced, not Django admin)
    path('system/users/', accounts_views.user_list_view, name='admin_users'),
    path('system/users/create/', accounts_views.user_create_view, name='admin_user_create'),
    path('system/users/<int:user_id>/edit/', accounts_views.user_edit_view, name='admin_user_edit'),
    path('system/settings/', accounts_views.settings_view, name='admin_settings'),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
