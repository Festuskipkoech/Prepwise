from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.core.exceptions.auth import AuthenticationError
from app.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepository(db)

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repo.get_by_email(email)

        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError()

        return create_access_token(subject=user.email)