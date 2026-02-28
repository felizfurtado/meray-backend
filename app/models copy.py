from django.db import models
from django_tenants.models import TenantMixin , DomainMixin

# Create your models here.
class Client(TenantMixin):
    name = models.CharField(max_length = 100)
    created_on = models.DateField(auto_now_add=True)
    auto_create_schema = True
    config = models.JSONField(default=dict, blank=True)

class Domain(DomainMixin):
    pass
 