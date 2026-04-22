from django.urls import path
from . import views

app_name = "authentication"

urlpatterns = [
    path("register/", views.RegisterAPIView.as_view(), name="register-api"),
    path("activate/<uidb64>/<uuid:token>/", views.ActivateAccountAPIView.as_view(), name="activate-account"),
    path("login/", views.LoginAPIView.as_view(), name="login-api"),
    path("login/verify/", views.LoginOTPVerificationAPIView.as_view(), name="login-otp-verification-api"),
    path("logout/", views.LogoutAPIView.as_view(), name="logout-api"),
    path("reset-password/", views.ResetPasswordOTPAPIView.as_view(), name="reset-password"),
    path("reset-password/confirm/<uidb64>/<token>/", views.ConfirmResetPasswordAPIView.as_view(), name="reset-password-confirm"),
]