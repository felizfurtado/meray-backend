from app.views import landing_page
from django.urls import path
from django.contrib import admin




urlpatterns = [
    path('admin/', admin.site.urls),
    path("home", landing_page, name="landing"),
    


]