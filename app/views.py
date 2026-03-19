
from django.http import HttpResponse

from django.shortcuts import render

from django.shortcuts import redirect

def landing_page(request):

    # If request comes from tenant → send to React app
    if request.tenant.schema_name != "public":
        return redirect("https://meray.cloud/login")

    # Public schema → show landing page
    return render(request, "landing.html")

# Create your views here.
