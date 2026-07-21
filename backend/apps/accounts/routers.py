from adrf.routers import DefaultRouter

from .views import RegisterViewSet, UserMeViewSet

router = DefaultRouter()

router.register("user", UserMeViewSet, "user")
router.register("sign-up", RegisterViewSet, "sign-up")
