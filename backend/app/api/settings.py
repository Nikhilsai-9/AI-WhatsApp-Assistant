"""Settings routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.settings import UserSettings
from app.models.user import User
from app.schemas.settings import SettingsUpdate, SettingsResponse

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=SettingsResponse)
async def get_settings(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings_row = result.scalar_one_or_none()
    if not settings_row:
        settings_row = UserSettings(user_id=user.id)
        session.add(settings_row)
        await session.commit()
        await session.refresh(settings_row)
    return SettingsResponse.model_validate(settings_row)


@router.patch("/", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    )
    settings_row = result.scalar_one_or_none()
    if not settings_row:
        settings_row = UserSettings(user_id=user.id)
        session.add(settings_row)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)

    session.add(AuditLog(user_id=user.id, action="settings_updated"))
    await session.commit()
    await session.refresh(settings_row)
    logger.info("settings_updated", user_id=str(user.id))
    return SettingsResponse.model_validate(settings_row)