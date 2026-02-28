from django.contrib import admin
from .models import Employee
from django.contrib.auth.models import User

# Just register Employee model
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    search_fields = ('name', 'user__username')
    
# User model is already registered by Django, no need to register again