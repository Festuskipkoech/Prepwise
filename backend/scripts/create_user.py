import asyncio
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
import bcrypt

from app.db.session import AsyncSessionFactory, engine, Base
from app.db.models.users import User


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 bytes.")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


async def create_user(email: str, password: str) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User with email {email} already exists.")
            return

        user = User(
            email=email,
            password_hash=hash_password(password),
        )
        session.add(user)
        await session.commit()
        print(f"User created successfully: {email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the Prepwise user account")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password")
    args = parser.parse_args()

    asyncio.run(create_user(email=args.email, password=args.password))