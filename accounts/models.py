import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


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

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="accounts_user_email_ci_unique",
            )
        ]


class CustomerInvitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="customer_invitations",
    )
    email = models.EmailField()
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="issued_customer_invitations",
        null=True,
        blank=True,
    )
    created_by_label = models.CharField(max_length=254)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    email_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_failed_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.CharField(max_length=100, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(accepted_at__isnull=True)
                | models.Q(revoked_at__isnull=True),
                name="customer_invitation_not_accepted_and_revoked",
            ),
            models.CheckConstraint(
                condition=~models.Q(created_by_label=""),
                name="customer_invitation_actor_label_required",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="customer_invite_user_time_idx",
            )
        ]

    @property
    def lifecycle_status(self):
        if self.accepted_at:
            return "Accepted"
        if self.revoked_at:
            return "Superseded"
        if self.expires_at <= timezone.now():
            return "Expired"
        if self.delivery_failed_at:
            return "Delivery failed"
        if self.email_sent_at:
            return "Sent to email provider"
        return "Pending delivery"

    def __str__(self):
        return f"Customer invitation for {self.email} — {self.lifecycle_status}"
