import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
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


class CustomerAccountDeletionAttempt(models.Model):
    class Outcome(models.TextChoices):
        CREATED = "CREATED", "Deletion request created"
        IGNORED = "IGNORED", "Request accepted without creating a deletion request"

    email_digest = models.CharField(max_length=64, editable=False)
    source_ip_digest = models.CharField(max_length=64, editable=False)
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attempted_at", "-pk"]
        indexes = [
            models.Index(
                fields=["source_ip_digest", "attempted_at"],
                name="acct_del_attempt_ip_idx",
            ),
            models.Index(
                fields=["email_digest", "attempted_at"],
                name="acct_del_attempt_email_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outcome__in=["CREATED", "IGNORED"]),
                name="account_deletion_attempt_outcome_valid",
            ),
        ]


class CustomerAccountDeletionRequest(models.Model):
    class Source(models.TextChoices):
        PUBLIC = "PUBLIC", "Public email verification"
        AUTHENTICATED = "AUTHENTICATED", "Authenticated customer"

    class Status(models.TextChoices):
        PENDING_VERIFICATION = "PENDING_VERIFICATION", "Pending verification"
        VERIFIED = "VERIFIED", "Verified"
        CONTAINED = "CONTAINED", "Account contained"
        AWAITING_SETTLEMENT = "AWAITING_SETTLEMENT", "Awaiting settlement or review"
        APPROVED = "APPROVED", "Approved for final disposition"
        COMPLETED = "COMPLETED", "Completed"
        COMPLETED_WITH_RETENTION = (
            "COMPLETED_WITH_RETENTION",
            "Completed with retained records",
        )
        REJECTED = "REJECTED", "Rejected"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        EXPIRED = "EXPIRED", "Expired"

    OPEN_STATUSES = (
        "PENDING_VERIFICATION",
        "VERIFIED",
        "CONTAINED",
        "AWAITING_SETTLEMENT",
        "APPROVED",
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "schemes.Customer",
        on_delete=models.PROTECT,
        related_name="account_deletion_requests",
    )
    requested_email = models.EmailField()
    email_digest = models.CharField(max_length=64, editable=False)
    source_ip_digest = models.CharField(max_length=64, editable=False)
    verification_token_digest = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
    )
    source = models.CharField(max_length=20, choices=Source.choices)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_VERIFICATION,
    )
    policy_version = models.CharField(max_length=40)
    requested_at = models.DateTimeField(auto_now_add=True)
    verification_expires_at = models.DateTimeField()
    verification_email_sent_at = models.DateTimeField(null=True, blank=True)
    verification_delivery_failed_at = models.DateTimeField(null=True, blank=True)
    verification_delivery_error = models.CharField(max_length=100, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    contained_at = models.DateTimeField(null=True, blank=True)
    owner_review_due_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-requested_at", "-pk"]
        indexes = [
            models.Index(
                fields=["status", "requested_at"],
                name="acct_del_status_time_idx",
            ),
            models.Index(
                fields=["customer", "requested_at"],
                name="acct_del_customer_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=["PUBLIC", "AUTHENTICATED"]),
                name="account_deletion_source_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(requested_email="")
                    & ~models.Q(policy_version="")
                ),
                name="account_deletion_request_identity_policy_required",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING_VERIFICATION",
                        "VERIFIED",
                        "CONTAINED",
                        "AWAITING_SETTLEMENT",
                        "APPROVED",
                        "COMPLETED",
                        "COMPLETED_WITH_RETENTION",
                        "REJECTED",
                        "WITHDRAWN",
                        "EXPIRED",
                    ]
                ),
                name="account_deletion_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING_VERIFICATION",
                        verified_at__isnull=True,
                        contained_at__isnull=True,
                        closed_at__isnull=True,
                    )
                    | models.Q(
                        status="VERIFIED",
                        verified_at__isnull=False,
                        contained_at__isnull=True,
                        closed_at__isnull=True,
                    )
                    | models.Q(
                        status__in=[
                            "CONTAINED",
                            "AWAITING_SETTLEMENT",
                            "APPROVED",
                        ],
                        verified_at__isnull=False,
                        contained_at__isnull=False,
                        closed_at__isnull=True,
                    )
                    | models.Q(
                        status__in=[
                            "COMPLETED",
                            "COMPLETED_WITH_RETENTION",
                            "REJECTED",
                        ],
                        verified_at__isnull=False,
                        contained_at__isnull=False,
                        closed_at__isnull=False,
                    )
                    | models.Q(
                        status__in=["WITHDRAWN", "EXPIRED"],
                        closed_at__isnull=False,
                    )
                ),
                name="account_deletion_lifecycle_valid",
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(
                    status__in=[
                        "PENDING_VERIFICATION",
                        "VERIFIED",
                        "CONTAINED",
                        "AWAITING_SETTLEMENT",
                        "APPROVED",
                    ]
                ),
                name="account_deletion_one_open_per_customer",
            ),
        ]

    @property
    def lifecycle_status(self):
        if (
            self.status == self.Status.PENDING_VERIFICATION
            and self.verification_expires_at <= timezone.now()
        ):
            return "Verification expired"
        return self.get_status_display()

    def __str__(self):
        return f"Account deletion request {self.pk} — {self.lifecycle_status}"


class CustomerAccountDeletionDecision(models.Model):
    class Outcome(models.TextChoices):
        AWAITING_SETTLEMENT = (
            "AWAITING_SETTLEMENT",
            "Awaiting settlement or retention review",
        )

    request = models.ForeignKey(
        CustomerAccountDeletionRequest,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    outcome = models.CharField(max_length=32, choices=Outcome.choices)
    reason = models.TextField()
    retained_categories = models.TextField(blank=True)
    review_due_at = models.DateTimeField(null=True, blank=True)
    policy_version = models.CharField(max_length=40)
    decided_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="customer_deletion_decisions",
        null=True,
        blank=True,
    )
    decided_by_label = models.CharField(max_length=254)
    decided_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-decided_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    outcome="AWAITING_SETTLEMENT"
                ),
                name="account_deletion_decision_outcome_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason="") & ~models.Q(decided_by_label=""),
                name="account_deletion_decision_actor_reason_required",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    review_due_at__isnull=False,
                    retained_categories__gt="",
                ),
                name="account_deletion_decision_review_shape_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Account deletion decisions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Account deletion decisions cannot be deleted.")


class CustomerAccountDeletionAction(models.Model):
    class Action(models.TextChoices):
        REQUESTED = "REQUESTED", "Request created"
        VERIFICATION_EMAIL_ACCEPTED = (
            "VERIFICATION_EMAIL_ACCEPTED",
            "Verification email accepted",
        )
        VERIFICATION_EMAIL_FAILED = (
            "VERIFICATION_EMAIL_FAILED",
            "Verification email failed",
        )
        VERIFIED = "VERIFIED", "Request verified"
        SESSIONS_REVOKED = "SESSIONS_REVOKED", "Sessions revoked"
        GOOGLE_LINK_REMOVED = "GOOGLE_LINK_REMOVED", "Google link removed"
        CONTAINED = "CONTAINED", "Account contained"
        OWNER_HOLD_RECORDED = "OWNER_HOLD_RECORDED", "Owner hold recorded"
        OWNER_REJECTED = "OWNER_REJECTED", "Owner rejected request"
        NOTICE_ACCEPTED = "NOTICE_ACCEPTED", "Customer notice accepted"
        NOTICE_FAILED = "NOTICE_FAILED", "Customer notice failed"

    request = models.ForeignKey(
        CustomerAccountDeletionRequest,
        on_delete=models.PROTECT,
        related_name="actions",
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    actor = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        related_name="customer_deletion_actions",
        null=True,
        blank=True,
    )
    actor_label = models.CharField(max_length=254)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        indexes = [
            models.Index(
                fields=["request", "created_at"],
                name="acct_del_action_time_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    action__in=[
                        "REQUESTED",
                        "VERIFICATION_EMAIL_ACCEPTED",
                        "VERIFICATION_EMAIL_FAILED",
                        "VERIFIED",
                        "SESSIONS_REVOKED",
                        "GOOGLE_LINK_REMOVED",
                        "CONTAINED",
                        "OWNER_HOLD_RECORDED",
                        "OWNER_REJECTED",
                        "NOTICE_ACCEPTED",
                        "NOTICE_FAILED",
                    ]
                ),
                name="account_deletion_action_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(actor_label=""),
                name="account_deletion_action_actor_required",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Account deletion actions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Account deletion actions cannot be deleted.")
