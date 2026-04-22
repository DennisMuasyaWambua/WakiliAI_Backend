from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import Role

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
        user.is_active = False 
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