from django.urls import path
from .views import auth_views, dashboard_views, clustering_views

urlpatterns = [
    path('', auth_views.landing_view, name='landing'),
    path('dashboard/', dashboard_views.dashboard_view, name='dashboard'),
    path('dashboard/export-excel/', dashboard_views.export_dashboard_excel, name='export-dashboard-excel'),
    path('clustering-atribut/', clustering_views.clustering_atribut_view, name='clustering-atribut'),
    path('clustering-atribut/excel/', clustering_views.export_clustering_excel, name='export-excel'),
    path('zscore-normalization/', clustering_views.zscore_normalization_view, name='zscore-normalization'),
    path('zscore-normalization/excel/', clustering_views.export_zscore_excel, name='export-zscore-excel'),
    path('clustering/validation/', clustering_views.clustering_validation_view, name='clustering-validation'),
    path('clustering/results/', clustering_views.clustering_results_view, name='clustering-results'),
    path('clustering/results/excel/', clustering_views.export_clustering_results_excel, name='export-clustering-results-excel'),
    path('clustering-gis/', clustering_views.clustering_gis_view, name='clustering-gis'),
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
]
