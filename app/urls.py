from app.views import *
from django.urls import path
from django.contrib import admin




urlpatterns = [
    path('admin/', admin.site.urls),
    path("home/", landing_html, name="landing"),
    path("early-access/", early_access),
    path("success/", success_page),
    path("check/", check_leads, name="check_leads"),
    

]