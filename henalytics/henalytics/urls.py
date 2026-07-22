"""
URL configuration for henalytics project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.contrib import auth
import importlib

try:
    rest_framework_docs = importlib.import_module('rest_framework.documentation')
    include_docs_urls = rest_framework_docs.include_docs_urls
    docs_available = True
except ImportError:
    docs_available = False

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('EggProduction.urls')),
    path('', include('django.contrib.auth.urls')),
    path('api-auth/', include('rest_framework.urls')),
    path('imissyou/', include('imissyou.urls')),
]

if docs_available:
    urlpatterns.append(path('api/docs/', include_docs_urls(title='Henalytics API')))
