from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/export-excel/', views.export_dashboard_excel, name='export-dashboard-excel'),
    path('clustering-atribut/', views.clustering_atribut_view, name='clustering-atribut'),
    path('clustering-atribut/excel/', views.export_clustering_excel, name='export-excel'),
    path('zscore-normalization/', views.zscore_normalization_view, name='zscore-normalization'),
    path('zscore-normalization/excel/', views.export_zscore_excel, name='export-zscore-excel'),
    path('clustering/validation/', views.clustering_validation_view, name='clustering-validation'),
    path('clustering/results/', views.clustering_results_view, name='clustering-results'),
    path('clustering/results/excel/', views.export_clustering_results_excel, name='export-clustering-results-excel'),
    path('clustering-gis/', views.clustering_gis_view, name='clustering-gis'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
