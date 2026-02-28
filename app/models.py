from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
import json
from pathlib import Path
from django.conf import settings


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    schema_file = models.CharField(max_length=100)  # e.g. "bigco.json"
    auto_create_schema = True

    def get_schema(self):
        
    
        if not self.schema_file:
            return {}
    
        schema_path = (
            Path(settings.BASE_DIR)
            / "configs"
            / "tenant_schemas"
            / self.schema_file
        )
    
        if not schema_path.exists() or not schema_path.is_file():
            return {}
    
        return json.loads(schema_path.read_text(encoding="utf-8"))


    def get_leads_schema(self):
        return self.get_schema().get("leads", {})


class Domain(DomainMixin):
    pass