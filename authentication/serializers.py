from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Firm, FirmInvite, Role

User = get_user_model()


# =========================
# Register Serializer
# =========================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.SlugRelatedField(
        slug_field="short_name",
        queryset=Role.objects.filter(is_active=True),
        many=True
    )

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "username",
            "email", "mobile_number", "id_number",
            "firm_type", "role", "password", "confirm_password"
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        roles = validated_data.pop("role", [])
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = True 
        user.save()
        user.role.set(roles)
        return user


# =========================
# Login Serializer
# =========================
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


# =========================
# OTP Verification Serializer
# =========================
class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=10)


# =========================
# Reset Password Serializer
# =========================
class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


# =========================
# Confirm Reset Password Serializer
# =========================
class ConfirmResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs
    

# -----------------------------------------------
# Super Admin: Create Firm + Invite Owner
# -----------------------------------------------
class CreateFirmSerializer(serializers.Serializer):
    firm_name    = serializers.CharField(max_length=255)
    firm_type    = serializers.ChoiceField(choices=["big_law", "mid_size"])
    firm_email   = serializers.EmailField()
    firm_phone   = serializers.CharField(max_length=20, required=False, allow_blank=True)
    firm_address = serializers.CharField(required=False, allow_blank=True)
    owner_email  = serializers.EmailField(help_text="Senior-most person's email")
    owner_role   = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.filter(firm=None)  # system-level roles only
    )


# -----------------------------------------------
# Activate account from invite (owner + members)
# -----------------------------------------------
class ActivateFromInviteSerializer(serializers.Serializer):
    token            = serializers.UUIDField()
    username         = serializers.CharField(max_length=150)
    first_name       = serializers.CharField(max_length=50)
    last_name        = serializers.CharField(max_length=50)
    mobile_number    = serializers.CharField(max_length=15)
    password         = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return data


# -----------------------------------------------
# Firm owner / manager invites a team member
# -----------------------------------------------
class SendTeamInviteSerializer(serializers.Serializer):
    email   = serializers.EmailField()
    role_id = serializers.PrimaryKeyRelatedField(queryset=Role.objects.all())


# -----------------------------------------------
# Read serializers
# -----------------------------------------------
class FirmSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Firm
        fields = ["id", "name", "firm_type", "email", "phone", "address", "logo", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class FirmInviteSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model  = FirmInvite
        fields = ["id", "email", "role_name", "is_used", "expires_at", "created_at"]
        read_only_fields = fields