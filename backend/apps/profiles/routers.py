from adrf.routers import DefaultRouter

from .views import MemberProfileViewSet, ProfileMeViewSet

router = DefaultRouter()
# Eigenes Profil – gleiches Muster wie accounts.UserMeViewSet (…/user/me/)
router.register("user", ProfileMeViewSet, basename="profile-user")
# Directory: Liste + Detail + Kontaktanfrage
router.register("", MemberProfileViewSet, basename="profiles")
