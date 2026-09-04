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


class CustomerRegistration(models.Model):
    class Status(models.TextChoices):
        PENDING_EMAIL_VERIFICATION = (
            "PENDING_EMAIL_VERIFICATION",
            "Pending email verification",
        )
        AWAITING_OWNER_APPROVAL = (
            "AWAITING_OWNER_APPROVAL",
            "Awaiting owner approval",
        )
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    mobile_number = models.CharField(max_length=20)
    address = models.TextField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_EMAIL_VERIFICATION,
    )
    email_token_digest = models.CharField(max_length=64, unique=True, editable=False)
    submitted_at = models.DateTimeField(auto_now_add=True)
    email_verification_expires_at = models.DateTimeField()
    email_sent_at = models.DateTimeField(null=True, blank=True)
    delivery_failed_at = models.DateTimeField(null=True, blank=True)
    delivery_error = models.CharField(max_length=100, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=40)
    privacy_version = models.CharField(max_length=40)
    consent_accepted_at = models.DateTimeField()
    source_ip_digest = models.CharField(max_length=64, editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="reviewed_customer_registrations",
        null=True,
        blank=True,
    )
    reviewed_by_label = models.CharField(max_length=254, blank=True)
    review_reason = models.TextField(blank=True)
    mobile_verified_at = models.DateTimeField(null=True, blank=True)
    approved_user = models.OneToOneField(
        CustomUser,
        on_delete=models.PROTECT,
        related_name="approved_customer_registration",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-submitted_at", "-pk"]
        indexes = [
            models.Index(
                fields=["status", "submitted_at"],
                name="customer_reg_status_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING_EMAIL_VERIFICATION",
                        "AWAITING_OWNER_APPROVAL",
                        "APPROVED",
                        "REJECTED",
                        "EXPIRED",
                    ]
                ),
                name="customer_registration_status_valid",
            ),
            models.UniqueConstraint(
                Lower("email"),
                condition=models.Q(
                    status__in=[
                        "PENDING_EMAIL_VERIFICATION",
                        "AWAITING_OWNER_APPROVAL",
                    ]
                ),
                name="customer_registration_active_email_unique",
            ),
            models.UniqueConstraint(
                fields=["mobile_number"],
                condition=models.Q(
                    status__in=[
                        "PENDING_EMAIL_VERIFICATION",
                        "AWAITING_OWNER_APPROVAL",
                    ]
                ),
                name="customer_registration_active_mobile_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING_EMAIL_VERIFICATION",
                        email_verified_at__isnull=True,
                        reviewed_at__isnull=True,
                        reviewed_by_label="",
                        review_reason="",
                        mobile_verified_at__isnull=True,
                        approved_user__isnull=True,
                    )
                    | models.Q(
                        status="EXPIRED",
                        email_verified_at__isnull=True,
                        reviewed_at__isnull=True,
                        reviewed_by_label="",
                        review_reason="",
                        mobile_verified_at__isnull=True,
                        approved_user__isnull=True,
                    )
                    | models.Q(
                        status="AWAITING_OWNER_APPROVAL",
                        email_verified_at__isnull=False,
                        reviewed_at__isnull=True,
                        reviewed_by_label="",
                        review_reason="",
                        mobile_verified_at__isnull=True,
                        approved_user__isnull=True,
                    )
                    | models.Q(
                        status="APPROVED",
                        email_verified_at__isnull=False,
                        reviewed_at__isnull=False,
                        reviewed_by_label__gt="",
                        review_reason__gt="",
                        mobile_verified_at__isnull=False,
                        approved_user__isnull=False,
                    )
                    | models.Q(
                        status="REJECTED",
                        email_verified_at__isnull=False,
                        reviewed_at__isnull=False,
                        reviewed_by_label__gt="",
                        review_reason__gt="",
                        approved_user__isnull=True,
                    )
                ),
                name="customer_registration_lifecycle_valid",
            ),
        ]

    @property
    def lifecycle_status(self):
        if (
            self.status == self.Status.PENDING_EMAIL_VERIFICATION
            and self.email_verification_expires_at <= timezone.now()
        ):
            return "Email verification expired"
        return self.get_status_display()

    def __str__(self):
        return f"Customer registration for {self.email} — {self.lifecycle_status}"


class CustomerRegistrationAttempt(models.Model):
    class Outcome(models.TextChoices):
        CREATED = "CREATED", "Application created"
        IGNORED = "IGNORED", "Request accepted without creating an application"

    email_digest = models.CharField(max_length=64, editable=False)
    mobile_digest = models.CharField(max_length=64, editable=False)
    source_ip_digest = models.CharField(max_length=64, editable=False)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attempted_at", "-pk"]
        indexes = [
            models.Index(
                fields=["source_ip_digest", "attempted_at"],
                name="customer_reg_attempt_ip_idx",
            ),
            models.Index(
                fields=["email_digest", "attempted_at"],
                name="customer_reg_attempt_email_idx",
            ),
            models.Index(
                fields=["mobile_digest", "attempted_at"],
                name="cust_reg_attempt_mobile_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome__in=["CREATED", "IGNORED"]),
                name="customer_registration_attempt_outcome_valid",
            ),
        ]
