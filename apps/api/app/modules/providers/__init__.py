"""Providers module: business profiles + guide registration + identity verification.

Covers design doc §4 (BusinessProfile), §5 (entity-level verification),
§17 (Local Partners wall) and the Phase 7 DigiLocker-style identity addendum.
"""

from app.modules.providers import identity, router, schemas, service  # noqa: F401
