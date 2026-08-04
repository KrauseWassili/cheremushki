from adrf.routers import DefaultRouter

from .views import (
    AccountDeleteViewSet,
    ActivateAccountViewSet,
    LoginViewSet,
    LogoutViewSet,
    PasswordViewSet,
    RegisterViewSet,
    UserMeViewSet,
)

router = DefaultRouter()

router.register("login", LoginViewSet, basename="login")
router.register("user", UserMeViewSet, basename="user")
router.register("sign-up", RegisterViewSet, basename="sign-up")
router.register("activate", ActivateAccountViewSet, basename="activate")
router.register("logout", LogoutViewSet, basename="logout")
router.register("password", PasswordViewSet, basename="password")
router.register("delete", AccountDeleteViewSet, basename="account-delete")
