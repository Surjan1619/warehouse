import asyncio
import sys
import os

# Add project root to sys.path to resolve imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import async_session
from app.repo.crud import create_user, get_user_by_username

async def init_admin():
    async with async_session() as db:
        existing_user = await get_user_by_username(db, "admin")
        if existing_user:
            print("Пользователь 'admin' уже существует!")
            return
        
        await create_user(
            db=db,
            username="admin",
            role="admin",
            plain_password="changeme123"
        )
        print("Администратор 'admin' успешно создан с паролем 'changeme123'!")

if __name__ == "__main__":
    asyncio.run(init_admin())
