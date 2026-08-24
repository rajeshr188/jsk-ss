from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "OWNER", "Owner"
        STAFF = "STAFF", "Staff"
        CUSTOMER = "CUSTOMER", "Customer"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)

    def has_perm(self, perm, obj=None):
        if perm == "wagtailadmin.access_admin" and not self.is_staff:
            return False
        return super().has_perm(perm, obj=obj)

    def __str__(self):
        return self.email or self.username
