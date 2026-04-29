from django.db import models

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
import uuid
from django.conf import settings
from django.utils import timezone
from datetime import timedelta



# =========================
# ===== Firm Model (Tenant)
# =========================
import uuid

class Firm(models.Model):
    FIRM_TYPE_CHOICES = [
        ("big_law", "Big Law Firm"),
        ("mid_size", "Mid-Sized Firm"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)  # tenant UUID
    name = models.CharField(max_length=255, unique=True)
    firm_type = models.CharField(max_length=20, choices=FIRM_TYPE_CHOICES, default="big_law")
    email = models.EmailField(unique=True, help_text="Primary contact email for the firm")
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="firm_logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # The senior-most user onboarded by super admin
    owner = models.OneToOneField(
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_firm"
    )

    class Meta:
        db_table = "firm"

    def __str__(self):
        return f"{self.name} ({self.id})"


# =========================
# ===== Role Model ========
# =========================
class Role(models.Model):
    ROLE_CHOICES = [
        # Big Law Firm Roles
        ("managing_partner", "Managing Partner"),
        ("senior_partner", "Senior Partner"),
        ("junior_partner", "Junior Partner"),
        ("senior_associate", "Senior Associate"),
        ("associate", "Associate"),
        ("junior_associate", "Junior Associate"),
        ("trainee", "Trainee Advocate / Pupil"),

        # Mid-Sized Firm Roles
        ("founding_partner", "Founding Partner"),
        ("partner", "Partner"),
        ("junior_advocate", "Junior Advocate"),
        ("pupil", "Pupil / Trainee Advocate"),

        # System
        ("admin", "System Admin"),
    ]

    FIRM_TYPE_CHOICES = [
        ("big_law", "Big Law Firm"),
        ("mid_size", "Mid-Sized Firm"),
        ("system", "System"),
    ]

    firm = models.ForeignKey(     
        Firm,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="roles",
        help_text="Null = system-level default role"
    )

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=100, choices=ROLE_CHOICES, unique=True)
    description = models.CharField(max_length=255)
    firm_type = models.CharField(max_length=20, choices=FIRM_TYPE_CHOICES, default="big_law")
    access_level = models.IntegerField(
        default=1,
        help_text="Numeric rank: higher = more access. e.g Managing Partner=10, Trainee=1"
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.short_name} @ {self.firm or 'SYSTEM'}"

    class Meta:
        db_table = "role"
        ordering = ["-access_level"]
        unique_together = ("firm", "short_name")

# =========================
# ===== Permission Model ==
# =========================
class Permission(models.Model):
    PERMISSION_CHOICES = [
        # Workspace
        ("private_workspace", "Private Workspace"),
        ("view_team_workspace", "View Team Workspace"),

        # Case Files
        ("view_assigned_cases", "View Assigned Cases"),
        ("view_all_cases", "View All Cases"),
        ("view_closed_cases", "View Closed Cases"),
        ("manage_cases", "Manage Cases"),

        # Diary / Calendar
        ("own_diary", "Own Diary"),
        ("view_team_diary", "View Team Diary"),
        ("manage_all_diaries", "Manage All Diaries"),

        # Client Updates
        ("view_client_updates", "View Client Updates"),
        ("send_client_updates", "Send Client Updates"),

        # Repository
        ("view_repository", "View Repository"),
        ("add_to_repository", "Add to Repository"),
        ("manage_repository", "Manage Repository"),

        # Billing
        ("view_own_billing", "View Own Billing"),
        ("manage_billing", "Manage Billing"),
        ("full_billing_access", "Full Billing Access"),

        # AI Component
        ("use_ai", "Use AI Component"),
        ("train_ai", "Train AI / Upload Documents"),
        ("admin_ai", "Admin AI Settings"),

        # User Management
        ("view_users", "View Users"),
        ("manage_users", "Manage Users"),
        ("full_user_management", "Full User Management"),

        # Digital Repository
        ("view_digital_repository", "View Digital Repository"),
        ("manage_digital_repository", "Manage Digital Repository"),
    ]

    name = models.CharField(max_length=100, unique=True)
    short_name = models.CharField(max_length=100, choices=PERMISSION_CHOICES, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.short_name

    class Meta:
        db_table = "permission"


# =========================
# === Role Permission ======
# =========================
class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name="permission_roles")
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "role_permission"
        unique_together = ("role", "permission")

    def __str__(self):
        return f"{self.role.short_name} -> {self.permission.short_name}"


# =========================
# Custom User Model
# =========================
class User(AbstractUser):
    FIRM_TYPE_CHOICES = [
        ("big_law", "Big Law Firm"),
        ("mid_size", "Mid-Sized Firm"),
    ]

    firm = models.ForeignKey( 
        Firm,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
        help_text="Null only for super admins"
    )

    role = models.ManyToManyField(Role, related_name="users", blank=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    mobile_number = models.CharField(
        max_length=15,
        validators=[RegexValidator(
            regex=r"^\+?\d{9,15}$",
            message="Phone number must be in E.164 format"
        )],
        unique=True
    )
    id_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=255, unique=True)
    firm_type = models.CharField(
        max_length=20,
        choices=FIRM_TYPE_CHOICES,
        default="big_law",
        help_text="Determines which role hierarchy applies"
    )
    status = models.IntegerField(default=0)
    is_mfa = models.IntegerField(default=0)
    is_activated = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_users"
    )
    updated_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_users"
    )
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='authentication_users',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='authentication_users',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    REQUIRED_FIELDS = ["mobile_number", "email"]

    class Meta:
        db_table = "user"

    def __str__(self):
        return f"{self.username} ({self.email})"

    def has_permission(self, permission_short_name):
        """Check if user has a specific permission via their roles."""
        return RolePermission.objects.filter(
            role__in=self.role.all(),
            permission__short_name=permission_short_name,
            permission__is_active=True,
            is_active=True
        ).exists()

    def get_access_level(self):
        """Return the highest access level among user's roles."""
        roles = self.role.all()
        if not roles:
            return 0
        return max(r.access_level for r in roles)
    
    def is_firm_owner(self):
        """Returns True if this user is their firm's owner."""
        return self.firm is not None and self.firm.owner_id == self.pk

    def can_onboard(self):
        """Firm owner or anyone with manage_users / full_user_management permission."""
        return (
            self.is_firm_owner()
            or self.has_permission("manage_users")
            or self.has_permission("full_user_management")
        )


# =========================
# ==== Advocate Profile ===
# =========================
class AdvocateProfile(models.Model):
    """
    Profile for all legal staff — replaces AdminProfile, BuyerProfile, FreelancerProfile.
    Covers Managing Partner down to Trainee.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="advocate_profile")
    practice_number = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="LSK admission / practice number"
    )
    years_of_experience = models.IntegerField(default=0)
    specialization = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="e.g. Conveyancing, Litigation, Family Law"
    )
    profile_photo = models.ImageField(upload_to="advocate_photos/", blank=True, null=True)
    bio = models.TextField(max_length=1000, blank=True, null=True)
    id_document = models.FileField(upload_to="advocate_ids/", blank=True, null=True)
    date_of_admission = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "advocate_profile"

    def __str__(self):
        return f"AdvocateProfile - {self.user.get_full_name()}"


# =========================
# ==== Admin Profile ======
# =========================
class AdminProfile(models.Model):
    """System-level admin profile (non-legal staff managing the platform)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="admin_profile")
    designation = models.CharField(max_length=100, blank=True, null=True)
    profile_photo = models.ImageField(upload_to="admin_photos/", blank=True, null=True)

    class Meta:
        db_table = "admin_profile"

    def __str__(self):
        return f"AdminProfile - {self.user.username}"


# =========================
# ==== Private Workspace ==
# =========================
class PrivateWorkspace(models.Model):
    """
    Each advocate gets an isolated workspace.
    Partitioned by document category — mirrors Google Drive structure.
    """
    PARTITION_CHOICES = [
        ("notes", "Notes"),
        ("drafts", "Drafts"),
        ("pleadings", "Pleadings"),
        ("affidavits", "Affidavits"),
        ("applications", "Applications"),
        ("conveyancing", "Conveyancing"),
        ("agreements", "Agreements"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name="workspace_items"
    )
    partition = models.CharField(max_length=50, choices=PARTITION_CHOICES)
    title = models.CharField(max_length=255)
    content = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to="workspace/%Y/%m/%d/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "private_workspace"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user.get_full_name()} | {self.partition} | {self.title}"


# =========================
# Activation Token
# =========================
class ActivationToken(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    token_used = models.IntegerField(default=0)

    def __str__(self):
        return f"Activation token for {self.user.email}"

    class Meta:
        db_table = "activation_token"


# =========================
# Password Reset Token
# =========================
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    token_used = models.IntegerField(default=0)

    def __str__(self):
        return f"Password Reset token for {self.user.email}"

    class Meta:
        db_table = "password_reset_token"


# =========================
# Login OTP
# =========================
class LoginOtp(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=10)
    used = models.IntegerField(default=0)
    time_created = models.DateTimeField(auto_now_add=True)
    expiry_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expiry_time = timezone.now() + timedelta(minutes=15)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expiry_time

    def __str__(self):
        return f"Login OTP for {self.user.email}"

    class Meta:
        db_table = "login_otp"


class FirmInvite(models.Model):
    """
    Super admin creates a Firm + sends invite to the senior-most role.
    That person activates and then invites the rest of their team.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firm = models.ForeignKey(Firm, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_invites"
    )
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=48)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    class Meta:
        db_table = "firm_invite"

    def __str__(self):
        return f"Invite → {self.email} @ {self.firm.name}"