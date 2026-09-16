import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings configuration using pydantic-settings.
    Environment variables are automatically loaded from a .env file.
    """
    DATABASE_URL: str
    JWT_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Configure Pydantic to look for .env file and ignore extra variables
    model_config = SettingsConfigDict(env_file=".env", extra='ignore')

# Global settings instance for application-wide access
settings = Settings()
