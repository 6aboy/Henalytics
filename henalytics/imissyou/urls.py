from django.urls import path

from . import views


app_name = 'imissyou'

urlpatterns = [
    path('', views.index, name='index'),
]
