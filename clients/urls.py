from django.urls import path
from .views import *

urlpatterns = [
    # path('', index, name='client_index'),
    path('create_employee', create_employee, name='create_employee'),

    # Auth (JWT – custom)
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
]
