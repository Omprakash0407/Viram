"""Auth + profile endpoints (/api/v1/auth, /api/v1/users)."""


from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import TravellerProfile, User
from app.modules.users import schemas, service
from app.modules.users.deps import get_current_user

router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post(
    "/register", response_model=schemas.AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    payload: schemas.RegisterRequest, db: AsyncSession = Depends(get_db)
) -> schemas.AuthResponse:
    user = await service.register(
        db, email=payload.email, password=payload.password, display_name=payload.display_name
    )
    tokens = await service.issue_tokens(db, user)
    await db.commit()
    return _auth_response(user, tokens)


@auth_router.post("/login", response_model=schemas.AuthResponse)
async def login(
    payload: schemas.LoginRequest, db: AsyncSession = Depends(get_db)
) -> schemas.AuthResponse:
    result = await service.login(db, email=payload.email, password=payload.password)
    await db.commit()
    return _auth_response(result["user"], result)


@auth_router.post("/refresh", response_model=schemas.TokensResponse)
async def refresh(
    payload: schemas.RefreshRequest, db: AsyncSession = Depends(get_db)
) -> schemas.TokensResponse:
    result = await service.refresh(db, raw_refresh_token=payload.refresh_token)
    await db.commit()
    return schemas.TokensResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: schemas.LogoutRequest, db: AsyncSession = Depends(get_db)
) -> None:
    await service.revoke_session(db, raw_refresh_token=payload.refresh_token)
    await db.commit()


def _auth_response(user: User, tokens: dict, avatar_url: str | None = None) -> schemas.AuthResponse:
    out = schemas.UserOut.model_validate(user)
    out.avatar_url = avatar_url
    return schemas.AuthResponse(
        user=out,
        tokens=schemas.TokensResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
        ),
    )


@users_router.get("/me", response_model=schemas.UserOut)
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.UserOut:
    out = schemas.UserOut.model_validate(current_user)
    profile = await db.get(TravellerProfile, current_user.id)
    out.avatar_url = profile.avatar_url if profile else None
    return out


@users_router.get("/me/profile", response_model=schemas.ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ProfileOut:
    profile = await service.get_profile(db, user_id=current_user.id)
    return schemas.ProfileOut.model_validate(profile)


@users_router.patch("/me/profile", response_model=schemas.ProfileOut)
async def update_profile(
    payload: schemas.ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.ProfileOut:
    profile = await service.update_profile(
        db, user_id=current_user.id, data=payload.model_dump(exclude_unset=True)
    )
    await db.commit()
    return schemas.ProfileOut.model_validate(profile)


@users_router.get("/me/preferences", response_model=schemas.PreferencesOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.PreferencesOut:
    prefs = await service.get_or_create_preferences(db, user_id=current_user.id)
    await db.commit()
    return schemas.PreferencesOut.model_validate(prefs)


@users_router.patch("/me/preferences", response_model=schemas.PreferencesOut)
async def update_preferences(
    payload: schemas.PreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> schemas.PreferencesOut:
    prefs = await service.update_preferences(
        db, user_id=current_user.id, data=payload.model_dump(exclude_unset=True)
    )
    await db.commit()
    return schemas.PreferencesOut.model_validate(prefs)
