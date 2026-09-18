"""Model registry - importing this package registers all tables on Base.metadata."""

# Import every model module so all relationships resolve regardless of which
# entrypoint (app, seed scripts, alembic) imports first.
from app.models import commerce, geo, planning, user  # noqa: F401  (registry)
from app.models.commerce import (
    AdminAuditLog,
    GuideAvailability,
    GuideBooking,
    GuideProfile,
    Hotel,
    HotelBooking,
    Payment,
    PaymentWebhookEvent,
    Refund,
    RoomType,
)
from app.models.user import AccountRole
from app.models.user import AccountStatus
from app.models.user import TravellerProfile
from app.models.user import User
from app.models.user import UserPreference
from app.models.user import UserSession

__all__ = [
    "AccountRole",
    "AccountStatus",
    "AdminAuditLog",
    "GuideAvailability",
    "GuideBooking",
    "GuideProfile",
    "Hotel",
    "HotelBooking",
    "Payment",
    "PaymentWebhookEvent",
    "Refund",
    "RoomType",
    "TravellerProfile",
    "User",
    "UserPreference",
    "UserSession",
]
