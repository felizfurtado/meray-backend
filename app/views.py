
from django.shortcuts import render, redirect

from django.http import HttpResponse
from django.template.loader import render_to_string

def landing_html(request):
    return render(request, "landing.html")

import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect

@csrf_exempt
def early_access(request):

    if request.method == "POST":

        try:
            data = {
                "name": request.POST.get("name", ""),
                "company": request.POST.get("company", ""),
                "email": request.POST.get("email", ""),
                "phone": request.POST.get("phone", ""),
                "message": request.POST.get("message", "")
            }

            file_path = os.path.join(os.path.dirname(__file__), "early_access.json")

            if not os.path.exists(file_path):
                with open(file_path, "w") as f:
                    json.dump([], f)

            with open(file_path, "r") as f:
                records = json.load(f)

            records.append(data)

            with open(file_path, "w") as f:
                json.dump(records, f, indent=2)

            return redirect("/success/")

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request"})



def success_page(request):
    return render(request, "success.html")



def check_leads(request):

    file_path = os.path.join(os.path.dirname(__file__), "early_access.json")

    # If file doesn't exist return empty list
    if not os.path.exists(file_path):
        leads = []
    else:
        with open(file_path, "r") as f:
            leads = json.load(f)

    return render(request, "check.html", {"leads": leads})