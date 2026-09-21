"""DigiLocker-style identity verification with a swappable verifier.

ARCHITECTURE (mirrors the PaymentGateway pattern, design doc §18):
    IdentityVerifier  ← the contract
      ├── DemoDigiLockerVerifier  (this MVP: local, clearly labelled demo that
      │                            simulates the DigiLocker consent + eKYC flow)
      └── DigiLockerVerifier      (future: real API via app.core settings
                                   credentials — plugs in without schema or
                                   endpoint changes)

SECURITY RULES (hard):
- The Aadhaar number / any full document number is NEVER accepted by any
  endpoint here, NEVER stored, and NEVER logged. The demo verifier asks only
  for a consent acknowledgement, exactly like the real flow's consent screen;
  the actual document fetch happens inside the provider, and VIRĀM receives
  only a boolean "verified" plus the provider's own opaque reference id.
- The schema has no column that could hold a document number.

The real DigiLocker integration requires government-issued API credentials
registered with DIGLOCKER; until then the demo verifier is the only
implementation, and every response the UI shows carries the demo label.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class IdentityResult:
    verified: bool
    provider_reference: str
    expires_at: datetime | None
    note: str


class IdentityVerifier:
    """Contract: initiate + complete a document-verification session."""

    name: str = "IDENTITY_VERIFIER"

    async def initiate(self, *, user_id: uuid.UUID, id_proof_type: str) -> tuple[str, str]:
        """Return (consent_url, session_note) for the provider's consent screen."""
        raise NotImplementedError

    async def complete(
        self, *, user_id: uuid.UUID, verification_id: uuid.UUID, id_proof_type: str
    ) -> IdentityResult:
        raise NotImplementedError


class DemoDigiLockerVerifier(IdentityVerifier):
    """Local demo verifier — simulates the DigiLocker eKYC handshake.

    Clearly labelled in every payload that reaches the UI ("demo_note"). The
    completion is deterministic (APPROVED) so the whole provider-onboarding
    journey can be demonstrated end-to-end offline; FAILED/EXPIRED states
    still exist in the vocabulary for the real integration's outcomes.
    """

    name = "DIGILOCKER_DEMO"
    CONSENT_BASE = "/identity/demo-consent"

    async def initiate(self, *, user_id: uuid.UUID, id_proof_type: str) -> tuple[str, str]:
        token = uuid.uuid4().hex[:16]
        consent_url = f"{self.CONSENT_BASE}?proof={id_proof_type}&session={token}"
        note = (
            "DEMO VERIFIER — simulates DigiLocker. No document number is asked "
            "for or stored; the real integration needs DigiLocker API credentials."
        )
        return consent_url, note

    async def complete(
        self, *, user_id: uuid.UUID, verification_id: uuid.UUID, id_proof_type: str
    ) -> IdentityResult:
        # Opaque provider reference only — never contains document digits.
        reference = f"DLDEMO-{verification_id.hex[:12].upper()}"
        return IdentityResult(
            verified=True,
            provider_reference=reference,
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            note=(
                "Identity verified via the DEMO DigiLocker verifier. The Aadhaar "
                "number was never transmitted to or stored by VIRĀM."
            ),
        )


def get_identity_verifier() -> IdentityVerifier:
    """Composition root — swap the implementation here when credentials arrive."""
    return DemoDigiLockerVerifier()
