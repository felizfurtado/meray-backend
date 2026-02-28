# app/admin.py
from django.contrib import admin
from .models import Client, Domain

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['schema_name', 'name']
    search_fields = ['schema_name', 'name']

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
    list_filter = ['is_primary']
    search_fields = ['domain']