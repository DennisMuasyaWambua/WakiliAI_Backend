from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
import random
import string


def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))


def encode_uid(user_pk):
    return urlsafe_base64_encode(force_bytes(user_pk))


def build_activation_link(request, uid, token):
    return f"{request.scheme}://{request.get_host()}/apps/api/v1/auth/activate/{uid}/{token}/"


def build_reset_link(request, uid, token):
    return f"{request.scheme}://{request.get_host()}/apps/api/v1/auth/reset-password/confirm/{uid}/{token}/"