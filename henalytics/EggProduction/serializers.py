from rest_framework import serializers
from .models import (
    UserProfile, Flock, ProductionLog, GradingLog,
    SalesTransaction, SalesItem, ModelVersion, HarvestForecast, SalesForecast
)


class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'username', 'email', 'role', 'assigned_house', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class FlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flock
        fields = ['id', 'house_no', 'breed_strain', 'date_started', 'initial_hen_count', 
                 'status', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class ProductionLogSerializer(serializers.ModelSerializer):
    flock_detail = FlockSerializer(source='flock', read_only=True)
    entered_by_username = serializers.CharField(source='entered_by.username', read_only=True)
    
    class Meta:
        model = ProductionLog
        fields = ['id', 'flock', 'flock_detail', 'log_date', 'age_weeks', 'age_days',
                 'hen_count', 'dead_count', 'culled_count', 'feed_bags', 'eggs_total',
                 'pct_hen_day', 'pct_hen_housed', 'fcr', 'remarks', 'entered_by',
                 'entered_by_username', 'created_at', 'updated_at']
        read_only_fields = [
            'hen_count', 'pct_hen_day', 'pct_hen_housed', 'fcr',
            'entered_by', 'created_at', 'updated_at'
        ]


class GradingLogSerializer(serializers.ModelSerializer):
    flock_detail = FlockSerializer(source='flock', read_only=True)
    
    class Meta:
        model = GradingLog
        fields = ['id', 'flock', 'flock_detail', 'log_date', 'age_weeks', 'eggs_total',
                 'eggs_aa', 'eggs_a', 'eggs_b', 'eggs_small', 'eggs_broken',
                 'eggs_decode', 'eggs_source', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class SalesItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesItem
        fields = ['id', 'transaction', 'grade', 'quantity_pieces', 'amount', 'unit_price']
        read_only_fields = ['unit_price']


class SalesTransactionSerializer(serializers.ModelSerializer):
    items = SalesItemSerializer(many=True, read_only=True)
    flock_detail = FlockSerializer(source='flock', read_only=True)
    recorded_by_username = serializers.CharField(source='recorded_by.username', read_only=True)
    total_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = SalesTransaction
        fields = ['id', 'flock', 'flock_detail', 'sale_date', 'recorded_by', 
                 'recorded_by_username', 'or_number', 'notes', 'items', 'total_amount', 'created_at', 'updated_at']
        read_only_fields = ['recorded_by', 'created_at', 'updated_at']
    
    def get_total_amount(self, obj):
        """Calculate total amount from all items"""
        return sum(item.amount for item in obj.items.all())


class ModelVersionSerializer(serializers.ModelSerializer):
    triggered_by_username = serializers.CharField(source='triggered_by.username', read_only=True)
    
    class Meta:
        model = ModelVersion
        fields = ['id', 'model_type', 'trained_at', 'triggered_by', 'triggered_by_username',
                 'r2_score', 'rmse', 'mae', 'mape', 'baseline_rmse', 'aic_score',
                 'arima_order', 'pkl_path', 'is_active',
                 'training_rows', 'created_at']
        read_only_fields = ['created_at']


class HarvestForecastSerializer(serializers.ModelSerializer):
    flock_detail = FlockSerializer(source='flock', read_only=True)
    model_version_detail = ModelVersionSerializer(source='model_version', read_only=True)
    
    class Meta:
        model = HarvestForecast
        fields = ['id', 'flock', 'flock_detail', 'model_version', 'model_version_detail',
                 'forecast_date', 'predicted_qty', 'lower_qty', 'upper_qty', 'created_at']
        read_only_fields = ['created_at']


class SalesForecastSerializer(serializers.ModelSerializer):
    model_version_detail = ModelVersionSerializer(source='model_version', read_only=True)
    
    class Meta:
        model = SalesForecast
        fields = ['id', 'model_version', 'model_version_detail', 'forecast_date', 
                 'grade', 'predicted_trays', 'predicted_amount', 'created_at']
        read_only_fields = ['created_at']

