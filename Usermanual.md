 create tenant :
 
 python manage.py create_tenant --domain-domain=felixco.localhost --schema_name=felixco --name=Felixco



update client schema

In [2]: from app.models import Client
   ...:
   ...: c = Client.objects.get(schema_name="bigco")
   ...: c.schema_file = "bigco.json"
   ...: c.save()














pip install reportlab
pip install pdfplumber