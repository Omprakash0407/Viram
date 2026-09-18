"""Payment gateway abstraction.

The MVP rule: the gateway is replaceable and the webhook is authoritative for
final payment state (design doc §18). No card/CVV/UPI data is ever accepted or
stored — only gateway identifiers and safe metadata.

Gateways in this project implement `PaymentGateway`:
- `MockPaymentGateway` (below): local/dev only, clearly labelled; simulates an
  order + a confirmable payment so the full booking→payment→webhook flow can
  be demonstrated without real credentials.
- `RazorpayGateway` (future): raises NotConfigured until RAZORPAY_KEY_ID /
  RAZORPAY_KEY_SECRET are supplied; selection is environment-driven.

Amounts are integer paise everywhere (D15). The gateway never sees card data
because the schema and API never accept it.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings


@dataclass(frozen=True)
class GatewayOrder:
    gateway_order_id: str
    amount_paise: int
    currency: str
    checkout_url: str | None  # hosted-checkout URL when the gateway has one


class PaymentGateway:
    """Interface for order creation + webhook verification (replaceable, §18)."""

    name: str = "ABSTRACT"

    def create_order(self, *, amount_paise: int, currency: str, receipt: str) -> GatewayOrder:
        raise NotImplementedError

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool:
        raise NotImplementedError


class MockPaymentGateway(PaymentGateway):
    """DEV/DEMO ONLY — not a real payment provider.

    Simulates order creation and HMAC-signed webhook events so the confirm
    path (booking PENDING_PAYMENT → CONFIRMED) is exercised end to end in
    development. Never enabled outside local/test environments.
    """

    name = "MOCK"

    def create_order(self, *, amount_paise: int, currency: str, receipt: str) -> GatewayOrder:
        order_id = f"order_mock_{uuid.uuid4().hex[:20]}"
        return GatewayOrder(
            gateway_order_id=order_id,
            amount_paise=amount_paise,
            currency=currency,
            checkout_url=None,  # in-app "Simulate payment" control acts as the checkout
        )

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool:
        secret = settings.MOCK_WEBHOOK_SECRET.encode()
        expected = hmac.new(secret, payload_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class RazorpayGateway(PaymentGateway):
    """Real gateway — intentionally unimplemented until credentials exist.

    Implemented strictly per design doc §18/External-API table: keys live only
    in env config; nothing is faked in their absence.
    """

    name = "RAZORPAY"

    def __init__(self) -> None:
        if not (getattr(settings, "RAZORPAY_KEY_ID", None) and
                getattr(settings, "RAZORPAY_KEY_SECRET", None)):
            raise GatewayNotConfigured(
                "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not configured; "
                "the Razorpay gateway cannot be used yet."
            )

    def create_order(self, *, amount_paise: int, currency: str, receipt: str) -> GatewayOrder:
        raise GatewayNotConfigured("Razorpay order creation lands with the real integration.")

    def verify_webhook_signature(self, *, payload_body: bytes, signature: str) -> bool:
        raise GatewayNotConfigured("Razorpay webhook verification lands with the real integration.")


class GatewayNotConfigured(RuntimeError):
    """Raised when a gateway is selected but its credentials are absent."""


def get_payment_gateway() -> PaymentGateway:
    """Environment-driven gateway selection (replaceable-engine principle).

    - ENVIRONMENT=local|test → MockPaymentGateway (clearly labelled dev sim).
    - ENVIRONMENT=production → RazorpayGateway only; startup fails fast if
      credentials are missing rather than silently faking payments.
    """
    if settings.is_local:
        return MockPaymentGateway()
    return RazorpayGateway()


def mock_payment_id() -> str:
    """Fake-but-labelled gateway payment id for the mock gateway."""
    return f"pay_mock_{uuid.uuid4().hex[:20]}"


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def new_reference(prefix: str) -> str:
    """Human-readable booking reference, e.g. VIR-HB-4F9A2C."""
    return f"VIR-{prefix}-{secrets.token_hex(3).upper()}"
