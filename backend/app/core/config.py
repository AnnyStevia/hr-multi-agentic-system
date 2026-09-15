from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "HR Multi-Agentic System"
    app_env: str = "development"
    debug: bool = True

    database_url: str = "postgresql://hr_user:hr_password@localhost:5432/hr_platform"

    secret_key: str = "change-me-to-a-random-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: str = "http://localhost:3000"

    seed_admin_email: str = "admin@hr-platform.local"
    seed_admin_password: str = "admin123"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "eu-north-1"
    aws_s3_bucket_name: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
