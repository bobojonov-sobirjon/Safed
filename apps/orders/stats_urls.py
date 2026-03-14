from django.urls import path

from .views import StatsOverviewView, ProductStatsView

urlpatterns = [
    path('overview/', StatsOverviewView.as_view(), name='stats-overview'),
    path('products/', ProductStatsView.as_view(), name='stats-products'),
]

