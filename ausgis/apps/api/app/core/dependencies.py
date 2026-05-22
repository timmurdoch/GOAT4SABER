from typing import Annotated
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
    api_key: Annotated[str | None, Security(api_key_header)],
) -> User:
    if api_key:
        result = await db.execute(select(User).where(User.api_key == api_key, User.is_active == True))
        user = result.scalar_one_or_none()
        if user:
            return user

    if token:
        subject = decode_token(token)
        if subject:
            result = await db.execute(select(User).where(User.id == subject, User.is_active == True))
            user = result.scalar_one_or_none()
            if user:
                return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
