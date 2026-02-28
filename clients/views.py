from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Employee

# REST Framework imports
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django_tenants.utils import schema_context
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User  # ADD THIS

from app.models import Client  

from rest_framework.permissions import AllowAny


# Login view - exactly what you want
class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        role = request.data.get("role")  # This is username
        password = request.data.get("password")

        # Authenticate in CURRENT tenant schema
        user = authenticate(
            request,
            username=role,
            password=password
        )

        if not user:
            return Response(
                {"detail": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "email": user.email,
            "tenant": request.tenant.schema_name  # Current company
        })

# Register API - NO company field needed!
from django.contrib.auth import get_user_model  # ADD THIS

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # You're already in the tenant schema
        role = request.data.get("role")  # This is the username
        password = request.data.get("password")
        email = request.data.get("email", "")
        name = request.data.get("name", role)

        # Get the User model for CURRENT tenant
        User = get_user_model()  # 👈 THIS IS IMPORTANT!
        
        # DEBUG: Check where we are
        from django.db import connection
        print(f"🔍 RegisterView DEBUG:")
        print(f"  Current schema: {connection.schema_name}")
        print(f"  Request tenant: {getattr(request, 'tenant', 'NO TENANT')}")
        print(f"  User model: {User}")
        print(f"  Checking for username: {role}")

        # Check if user already exists IN THIS TENANT
        if User.objects.filter(username=role).exists():
            print(f"  ❌ User '{role}' already exists in schema: {connection.schema_name}")
            return Response(
                {"detail": f"User '{role}' already exists in {connection.schema_name}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create user IN THIS TENANT
        user = User.objects.create_user(
            username=role,
            password=password,
            email=email
        )
        
        print(f"  ✅ Created user '{role}' in schema: {connection.schema_name}")

        # Create employee record
        Employee.objects.create(user=user, name=name)

        return Response({
            "message": "User registered successfully",
            "username": role,
            "name": name,
            "email": email,
            "company": request.tenant.schema_name  # Current company
        })
    
    
# Your existing views - keep these
def index(request):
    employees = Employee.objects.all()
    return render(request, "client.html", {"employees": employees})

def create_employee(request):
    if request.POST:
        name = request.POST.get("name")
        employee = Employee(name=name)
        employee.save()
        return redirect("client_index")