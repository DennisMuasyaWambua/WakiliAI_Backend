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

from authentication.tasks import send_activation_email_async, send_otp_email_async, send_reset_password_email_async

from .models import ActivationToken, PasswordResetToken, LoginOtp
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    OTPVerificationSerializer,
    ResetPasswordSerializer,
    ConfirmResetPasswordSerializer,
)
from .utils import (
    build_activation_link,
    build_reset_link,
    encode_uid,
    generate_otp,
)

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

        # Create activation token and send email
        # activation = ActivationToken.objects.create(user=user)
        # uid = encode_uid(user.pk)
        # activation_link = build_activation_link(request, uid, activation.token)
        # send_activation_email_async.delay(user.first_name, user.email, activation_link)

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