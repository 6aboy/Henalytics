from django.urls import path

from . import views
urlpatterns = [
    path("", views.index, name='index'),
    path("gabo", views.gabo, name='gabo'),
    path("niko", views.niko, name='niko'),
    path("<str:name>", views.greet, name='greet')
]