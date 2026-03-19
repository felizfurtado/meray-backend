
from django.shortcuts import render, redirect

from django.http import HttpResponse
from django.template.loader import render_to_string

def landing_html(request):
    return render(request, "landing.html")
