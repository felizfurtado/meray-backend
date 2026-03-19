
from django.shortcuts import render, redirect

def landing_page(request):

    if request.tenant.schema_name != "public":
        return redirect("https://meray.cloud/login")

    return render(request, "landing.html")
