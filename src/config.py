from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "PyBank"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://pybank:pybank@localhost:5432/pybank"
    SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMIT_LOGIN: int = 10  # requisicoes/min por IP em /auth/login e /auth/refresh
    RATE_LIMIT_MUTATIONS: int = 100  # requisicoes/min por usuario em deposits/withdrawals/transfers
    CORS_ORIGINS: list[str] = ["http://localhost:8000"]

    def validate_security(self) -> None:
        if not self.SECRET_KEY or self.SECRET_KEY == "changeme":
            raise ValueError("SECRET_KEY ausente ou invalida: defina chave forte em .env")


settings = Settings()
