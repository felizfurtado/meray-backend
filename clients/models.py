from django.db import models
from django.contrib.auth.models import User

class Employee(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="employee",
        null=True,        # 👈 IMPORTANT
        blank=True        # 👈 IMPORTANT
    )
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
