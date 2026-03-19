from app.views import *
from django.urls import path
from django.contrib import admin




urlpatterns = [
    path('admin/', admin.site.urls),
    path("home/", landing_html, name="landing"),
    

]