from datetime import timedelta
import uuid

from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import get_user_model, authenticate
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator

from authentication.tasks import send_activation_email_async, send_firm_owner_invite_async, send_otp_email_async, send_reset_password_email_async, send_team_invite_async

from .models import ActivationToken, AdvocateProfile, Firm, FirmInvite, PasswordResetToken, LoginOtp, Role
from .serializers import (
    ActivateFromInviteSerializer,
    CreateFirmSerializer,
    FirmInviteSerializer,
    FirmSerializer,
    RegisterSerializer,
    LoginSerializer,
    OTPVerificationSerializer,
    ResetPasswordSerializer,
    ConfirmResetPasswordSerializer,
    SendTeamInviteSerializer,
)
from .utils import (
    build_activation_link,
    build_reset_link,
    encode_uid,
    generate_otp,
)

from django.conf import settings

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# =========================
# Register
# =========================
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = serializer.save()

        activation = ActivationToken.objects.create(user=user)
        uid = encode_uid(user.pk)
        activation_link = build_activation_link(request, uid, activation.token)
        send_activation_email_async.delay(user.first_name, user.email, activation_link)

        return Response(
            {
                "success": True,
                "message": "Registration successful. Check your email to activate your account.",
            },
            status=status.HTTP_201_CREATED
        )


# =========================
# Activate Account
# =========================
class ActivateAccountAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
            activation = ActivationToken.objects.get(user=user, token=token)
        except (User.DoesNotExist, ActivationToken.DoesNotExist, ValueError):
            return Response(
                {"success": False, "message": "Invalid activation link."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if activation.token_used:
            return Response(
                {"success": False, "message": "Activation link already used."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.is_active = True
        user.is_activated = 1
        user.save()

        activation.token_used = 1
        activation.save()

        return Response(
            {"success": True, "message": "Account activated successfully. You can now log in."},
            status=status.HTTP_200_OK
        )


# =========================
# Login
# =========================
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(request, username=user_obj.username, password=password)

        if not user:
            return Response(
                {"success": False, "message": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return Response(
                {"success": False, "message": "Account not activated. Check your email."},
                status=status.HTTP_403_FORBIDDEN
            )

        # If MFA is enabled, send OTP instead of tokens
        if user.is_mfa:
            otp = generate_otp()
            LoginOtp.objects.filter(user=user, used=0).update(used=1)
            LoginOtp.objects.create(user=user, otp=otp)
            send_otp_email_async.delay(user.first_name, user.email, otp)
            
            return Response(
                {
                    "success": True,
                    "mfa_required": True,
                    "message": "OTP sent to your email. Please verify to complete login.",
                },
                status=status.HTTP_200_OK
            )

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "success": True,
                "mfa_required": False,
                "message": "Login successful.",
                "data": {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.get_full_name(),
                        "firm_type": user.firm_type,
                        "roles": list(user.role.values_list("short_name", flat=True)),
                        "access_level": user.get_access_level(),
                    },
                    "tokens": tokens,
                },
            },
            status=status.HTTP_200_OK
        )


# =========================
# Login OTP Verification
# =========================
class LoginOTPVerificationAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"success": False, "message": "User not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        otp_obj = LoginOtp.objects.filter(user=user, otp=otp, used=0).last()

        if not otp_obj:
            return Response(
                {"success": False, "message": "Invalid OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if otp_obj.is_expired():
            return Response(
                {"success": False, "message": "OTP has expired. Please log in again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        otp_obj.used = 1
        otp_obj.save()

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "success": True,
                "message": "OTP verified. Login successful.",
                "data": {
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.get_full_name(),
                        "firm_type": user.firm_type,
                        "roles": list(user.role.values_list("short_name", flat=True)),
                        "access_level": user.get_access_level(),
                    },
                    "tokens": tokens,
                },
            },
            status=status.HTTP_200_OK
        )


# =========================
# Logout
# =========================
class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response(
                    {"success": False, "message": "Refresh token is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"success": True, "message": "Logged out successfully."},
                status=status.HTTP_200_OK
            )
        except Exception:
            return Response(
                {"success": False, "message": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )


# =========================
# Reset Password (Send Email)
# =========================
class ResetPasswordOTPAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Return success anyway to prevent email enumeration
            return Response(
                {"success": True, "message": "If this email exists, a reset link has been sent."},
                status=status.HTTP_200_OK
            )

        token = uuid.uuid4()
        PasswordResetToken.objects.create(user=user, token=token)
        uid = encode_uid(user.pk)
        reset_link = build_reset_link(request, uid, token)
        send_reset_password_email_async.delay(user.first_name, user.email, reset_link)

        return Response(
            {"success": True, "message": "Password reset link sent to your email."},
            status=status.HTTP_200_OK
        )
class ConfirmResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError):
            return Response(
                {"success": False, "message": "Invalid reset link."},
                status=status.HTTP_400_BAD_REQUEST
            )

        reset_token = PasswordResetToken.objects.filter(
            user=user, token=token, token_used=0
        ).last()

        if not reset_token:
            return Response(
                {"success": False, "message": "Invalid or already used reset link."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ UUID expiry check only - no default_token_generator
        if timezone.now() > reset_token.created_at + timedelta(hours=1):
            return Response(
                {"success": False, "message": "Reset link has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ConfirmResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        reset_token.token_used = 1
        reset_token.save()

        return Response(
            {"success": True, "message": "Password reset successfully. You can now log in."},
            status=status.HTTP_200_OK
        )
    

def build_invite_link(request, token):
    frontend_url = settings.FRONTEND_URL
    return f"{frontend_url}/activate?token={token}"


# ==============================================
# SUPER ADMIN — Create Firm + Invite Owner
# ==============================================
class CreateFirmAPIView(APIView):
    """
    Only Django superusers can hit this.
    Creates the Firm tenant and shoots an invite to the senior-most person.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_superuser:
            return Response(
                {"success": False, "message": "Only super admins can create firms."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = CreateFirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        if Firm.objects.filter(email=data["firm_email"]).exists():
            return Response(
                {"success": False, "message": "A firm with this email already exists."},
                status=status.HTTP_409_CONFLICT
            )

        if Firm.objects.filter(name=data["firm_name"]).exists():
            return Response(
                {"success": False, "message": "A firm with this name already exists."},
                status=status.HTTP_409_CONFLICT
            )

        # Create firm
        firm = Firm.objects.create(
            name=data["firm_name"],
            firm_type=data["firm_type"],
            email=data["firm_email"],
            phone=data.get("firm_phone", ""),
            address=data.get("firm_address", ""),
        )

        # Create invite for the owner
        invite = FirmInvite.objects.create(
            firm=firm,
            email=data["owner_email"],
            role=data["owner_role"],
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(hours=48),
        )

        invite_link = build_invite_link(request, invite.token)
        send_firm_owner_invite_async.delay(
            first_name="",           # we don't know their name yet
            email=invite.email,
            firm_name=firm.name,
            role_name=invite.role.name,
            invite_link=invite_link
        )

        return Response(
            {
                "success": True,
                "message": f"Firm '{firm.name}' created. Invite sent to {invite.email}.",
                "data": {
                    "firm_id": str(firm.id),
                },
            },
            status=status.HTTP_201_CREATED
        )


# ==============================================
# OWNER — Activate Account from Invite
# ==============================================
class ActivateOwnerAPIView(APIView):
    """
    The senior-most invitee activates their account.
    They automatically become firm.owner.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ActivateFromInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            invite = FirmInvite.objects.select_related("firm", "role").get(
                token=data["token"], is_used=False
            )
        except FirmInvite.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or already used invite token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if invite.is_expired():
            return Response(
                {"success": False, "message": "This invite link has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Guard: owner slot must be empty (only 1 owner per firm)
        if invite.firm.owner is not None:
            return Response(
                {"success": False, "message": "This firm already has an owner."},
                status=status.HTTP_409_CONFLICT
            )

        if User.objects.filter(email=invite.email).exists():
            return Response(
                {"success": False, "message": "An account with this email already exists."},
                status=status.HTTP_409_CONFLICT
            )

        if User.objects.filter(username=data["username"]).exists():
            return Response(
                {"success": False, "message": "Username already taken."},
                status=status.HTTP_409_CONFLICT
            )

        # Create user
        user = User.objects.create_user(
            username=data["username"],
            email=invite.email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            mobile_number=data["mobile_number"],
            password=data["password"],
            firm=invite.firm,
            is_activated=1,
            status=1,
        )
        user.role.add(invite.role)

        # Make them the firm owner
        invite.firm.owner = user
        invite.firm.save(update_fields=["owner"])

        # Mark invite used
        invite.is_used = True
        invite.save(update_fields=["is_used"])

        AdvocateProfile.objects.create(user=user)

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "success": True,
                "message": "Account activated. You are now the firm owner.",
                "data": {
                    "firm_id": str(invite.firm.id),
                    "firm_name": invite.firm.name,
                    "tokens": tokens,
                },
            },
            status=status.HTTP_201_CREATED
        )


# ==============================================
# OWNER / MANAGER — Invite a Team Member
# ==============================================
class SendTeamInviteAPIView(APIView):
    """
    Firm owner or any user with manage_users permission
    can invite team members scoped to their own firm.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.can_onboard():
            return Response(
                {"success": False, "message": "You do not have permission to invite users."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = SendTeamInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data
        role = data["role_id"]

        # Enforce hierarchy — can't invite equal or higher
        if role.access_level >= request.user.get_access_level():
            return Response(
                {
                    "success": False,
                    "message": "You cannot invite a user with an equal or higher role than yours.",
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Role must belong to same firm or be a system role
        if role.firm and role.firm != request.user.firm:
            return Response(
                {"success": False, "message": "This role does not belong to your firm."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Prevent duplicate active invite
        if FirmInvite.objects.filter(
            firm=request.user.firm, email=data["email"], is_used=False
        ).exists():
            return Response(
                {"success": False, "message": "An active invite already exists for this email."},
                status=status.HTTP_409_CONFLICT
            )

        # Prevent inviting someone already in the firm
        if User.objects.filter(firm=request.user.firm, email=data["email"]).exists():
            return Response(
                {"success": False, "message": "This user is already a member of your firm."},
                status=status.HTTP_409_CONFLICT
            )

        invite = FirmInvite.objects.create(
            firm=request.user.firm,
            email=data["email"],
            role=role,
            invited_by=request.user,
            expires_at=timezone.now() + timedelta(hours=48),
        )

        invite_link = build_invite_link(request, invite.token)
        send_team_invite_async.delay(
            email=invite.email,
            firm_name=request.user.firm.name,
            role_name=role.name,
            invite_link=invite_link,
            
        )

        return Response(
            {
                "success": True,
                "message": f"Invite sent to {invite.email} for role '{role.name}'.",
            },
            status=status.HTTP_201_CREATED
        )


# ==============================================
# TEAM MEMBER — Activate Account from Invite
# ==============================================
class ActivateMemberAPIView(APIView):
    """Same activation flow as owner but for non-owner team members."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ActivateFromInviteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = serializer.validated_data

        try:
            invite = FirmInvite.objects.select_related("firm", "role", "invited_by").get(
                token=data["token"], is_used=False
            )
        except FirmInvite.DoesNotExist:
            return Response(
                {"success": False, "message": "Invalid or already used invite token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if invite.is_expired():
            return Response(
                {"success": False, "message": "This invite link has expired."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(email=invite.email).exists():
            return Response(
                {"success": False, "message": "An account with this email already exists."},
                status=status.HTTP_409_CONFLICT
            )

        if User.objects.filter(username=data["username"]).exists():
            return Response(
                {"success": False, "message": "Username already taken."},
                status=status.HTTP_409_CONFLICT
            )

        user = User.objects.create_user(
            username=data["username"],
            email=invite.email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            mobile_number=data["mobile_number"],
            password=data["password"],
            firm=invite.firm,
            created_by=invite.invited_by,
            is_activated=1,
            status=1,
        )
        user.role.add(invite.role)

        invite.is_used = True
        invite.save(update_fields=["is_used"])

        AdvocateProfile.objects.create(user=user)

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "success": True,
                "message": "Account activated. Welcome to your firm.",
                "data": {
                    "firm_id": str(invite.firm.id),
                    "firm_name": invite.firm.name,
                    "tokens": tokens,
                },
            },
            status=status.HTTP_201_CREATED
        )


# ==============================================
# FIRM — Details + Update
# ==============================================
class FirmDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.firm:
            return Response(
                {"success": False, "message": "You are not associated with any firm."},
                status=status.HTTP_404_NOT_FOUND
            )
        return Response(
            {"success": True, "data": FirmSerializer(request.user.firm).data},
            status=status.HTTP_200_OK
        )

    def patch(self, request):
        if not request.user.is_firm_owner():
            return Response(
                {"success": False, "message": "Only the firm owner can update firm details."},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = FirmSerializer(request.user.firm, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(
                {"success": False, "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer.save()
        return Response(
            {"success": True, "message": "Firm updated.", "data": serializer.data},
            status=status.HTTP_200_OK
        )


# ==============================================
# FIRM — Members List
# ==============================================
class FirmMembersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.has_permission("view_users"):
            return Response(
                {"success": False, "message": "You do not have permission to view members."},
                status=status.HTTP_403_FORBIDDEN
            )
        members = (
            User.objects
            .filter(firm=request.user.firm)
            .prefetch_related("role")
            .order_by("-date_joined")
        )
        data = [
            {
                "id": u.id,
                "full_name": u.get_full_name(),
                "email": u.email,
                "mobile_number": u.mobile_number,
                "roles": list(u.role.values_list("short_name", flat=True)),
                "access_level": u.get_access_level(),
                "is_activated": u.is_activated,
                "status": u.status,
                "date_joined": u.date_joined,
            }
            for u in members
        ]
        return Response({"success": True, "data": data}, status=status.HTTP_200_OK)


# ==============================================
# FIRM — Pending Invites
# ==============================================
class FirmInviteListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.can_onboard():
            return Response(
                {"success": False, "message": "Permission denied."},
                status=status.HTTP_403_FORBIDDEN
            )
        invites = (
            FirmInvite.objects
            .filter(firm=request.user.firm, is_used=False)
            .select_related("role", "invited_by")
            .order_by("-created_at")
        )
        return Response(
            {"success": True, "data": FirmInviteSerializer(invites, many=True).data},
            status=status.HTTP_200_OK
        )

# ==============================================
# Roles — List
# ==============================================
class RoleListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        roles = Role.objects.filter(is_active=True).values(
            "id", "name", "short_name", "access_level"
        )
        return Response({"success": True, "data": list(roles)}, status=status.HTTP_200_OK)