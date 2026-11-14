"""
Create the administrator account, or reset its password.

The credentials come from environment variables, so no password is stored in
the code:

    ADMIN_USERNAME  login name, "admin" by default
    ADMIN_PASSWORD  password, at least 6 characters (required)

Both can be set in the .env file in the project root.
If the user already exists, its password is replaced with ADMIN_PASSWORD,
its role is set to admin and the account is activated.
"""
import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to sys.path to resolve imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

# Variables already set in the environment (e.g. by docker compose) win over .env
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.core.db import async_session
from app.core.security import hash_password
from app.repo.crud import create_user, get_user_by_username

MIN_PASSWORD_LENGTH = 6


async def init_admin(username: str, password: str) -> None:
    async with async_session() as db:
        user = await get_user_by_username(db, username)
        if user:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
            await db.commit()
            print(f"Пароль администратора '{username}' обновлён.")
            return

        await create_user(db=db, username=username, role="admin", plain_password=password)
        print(f"Администратор '{username}' создан.")


def main() -> None:
    username = os.getenv("ADMIN_USERNAME") or "admin"
    password = os.getenv("ADMIN_PASSWORD") or ""

    if not password:
        sys.exit("Не задан ADMIN_PASSWORD. Добавьте его в файл .env и запустите скрипт снова.")
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(f"ADMIN_PASSWORD должен быть не короче {MIN_PASSWORD_LENGTH} символов.")

    asyncio.run(init_admin(username, password))


if __name__ == "__main__":
    main()
