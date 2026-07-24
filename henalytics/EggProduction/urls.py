from django.urls import path, include
from django.contrib.auth import views as auth_views
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'eggproduction'

# Create a router and register viewsets
router = DefaultRouter()
router.register(r'flocks', views.FlockViewSet, basename='api-flock')
router.register(r'production-logs', views.ProductionLogViewSet, basename='api-production-log')
router.register(r'grading-logs', views.GradingLogViewSet, basename='api-grading-log')
router.register(r'sales-transactions', views.SalesTransactionViewSet, basename='api-sales-transaction')
router.register(r'sales-items', views.SalesItemViewSet, basename='api-sales-item')
router.register(r'model-versions', views.ModelVersionViewSet, basename='api-model-version')
router.register(r'harvest-forecasts', views.HarvestForecastViewSet, basename='api-harvest-forecast')
router.register(r'sales-forecasts', views.SalesForecastViewSet, basename='api-sales-forecast')

urlpatterns = [
    # Dashboard and Auth
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('login/', views.CustomLoginView.as_view(template_name='login.html'), name='login'),
    
    # Flock Management
    path('flocks/', views.FlockListView.as_view(), name='flock-list'),
    path('flocks/create/', views.FlockCreateView.as_view(), name='flock-create'),
    path('flocks/<int:pk>/', views.FlockDetailView.as_view(), name='flock-detail'),
    path('flocks/<int:pk>/edit/', views.FlockUpdateView.as_view(), name='flock-edit'),
    path('flocks/<int:pk>/delete/', views.FlockDeleteView.as_view(), name='flock-delete'),
    
    # Production Log Management
    path('production-logs/', views.ProductionLogListView.as_view(), name='production-log-list'),
    path('production-logs/create/', views.ProductionLogCreateView.as_view(), name='production-log-create'),
    path('production-logs/<int:pk>/', views.ProductionLogDetailView.as_view(), name='production-log-detail'),
    path('production-logs/<int:pk>/edit/', views.ProductionLogUpdateView.as_view(), name='production-log-edit'),
    path('production-logs/<int:pk>/delete/', views.ProductionLogDeleteView.as_view(), name='production-log-delete'),
    
    # Grading Log Management
    path('grading-logs/', views.GradingLogListView.as_view(), name='grading-log-list'),
    path('grading-logs/create/', views.GradingLogCreateView.as_view(), name='grading-log-create'),
    path('grading-logs/<int:pk>/', views.GradingLogDetailView.as_view(), name='grading-log-detail'),
    path('grading-logs/<int:pk>/edit/', views.GradingLogUpdateView.as_view(), name='grading-log-edit'),
    path('grading-logs/<int:pk>/delete/', views.GradingLogDeleteView.as_view(), name='grading-log-delete'),
    
    # Sales Transaction Management
    path('sales/', views.SalesTransactionListView.as_view(), name='sales-transaction-list'),
    path('sales/create/', views.SalesTransactionCreateView.as_view(), name='sales-transaction-create'),
    path('sales/<int:pk>/', views.SalesTransactionDetailView.as_view(), name='sales-transaction-detail'),
    path('sales/<int:pk>/edit/', views.SalesTransactionUpdateView.as_view(), name='sales-transaction-edit'),
    path('sales/<int:pk>/delete/', views.SalesTransactionDeleteView.as_view(), name='sales-transaction-delete'),
    
    # Sales Item Management
    path('sales/<int:transaction_id>/items/add/', views.SalesItemAddView.as_view(), name='sales-item-add'),
    path('sales-items/<int:pk>/edit/', views.SalesItemUpdateView.as_view(), name='sales-item-edit'),
    path('sales-items/<int:pk>/delete/', views.SalesItemDeleteView.as_view(), name='sales-item-delete'),
    
    # Forecast Views
    path('harvest-forecasts/', views.HarvestForecastListView.as_view(), name='harvest-forecast-list'),
    path('harvest-forecasts/<int:pk>/', views.HarvestForecastDetailView.as_view(), name='harvest-forecast-detail'),
    path('sales-forecasts/', views.SalesForecastListView.as_view(), name='sales-forecast-list'),
    path('sales-forecasts/<int:pk>/', views.SalesForecastDetailView.as_view(), name='sales-forecast-detail'),
    path('forecast-maintenance/clear/', views.ForecastMaintenanceClearView.as_view(), name='forecast-maintenance-clear'),
    path('testing-data/clear/', views.TestingDataClearView.as_view(), name='testing-data-clear'),
    path('model-versions/', views.ModelVersionListView.as_view(), name='model-version-list'),
    path('model-versions/<int:pk>/', views.ModelVersionDetailView.as_view(), name='model-version-detail'),
    
    # API Endpoints
    path('api/', include(router.urls)),
]
