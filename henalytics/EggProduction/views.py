from django.http import HttpResponse
from django.shortcuts import render

# Create your views here.
def index(request):
    return HttpResponse("Hello, world. You're at the egg production index.")

def gabo(request):
    return HttpResponse("Hello, GABO")
def niko(request):
    return HttpResponse("Hello, niko")
def greet(request, name):
    return HttpResponse(f"Hello, {name.capitalize()}!")