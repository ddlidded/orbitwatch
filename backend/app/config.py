from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    orbitwatch_env: str = 'development'
    secret_key: str = 'dev-secret-change-in-production'
    cookie_secure: bool = False
    cookie_samesite: str = 'lax'
    cors_origins: str = 'http://localhost:5173,http://localhost:3000,http://localhost,https://localhost'

    database_url: str = 'postgresql+psycopg2://orbitwatch:orbitwatch@localhost:5432/orbitwatch'
    redis_url: str = 'redis://localhost:6379/0'

    s3_endpoint: str = 'http://localhost:9000'
    s3_access_key: str = 'minioadmin'
    s3_secret_key: str = 'minioadmin'
    s3_bucket: str = 'orbitwatch'
    s3_secure: bool = False
    s3_region: str = 'us-east-1'

    agent_token_hash_salt: str = 'agent-salt'
    agent_message_max_bytes: int = 1_048_576

    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 7
    max_session_lifetime_days: int = 30
    inactivity_timeout_minutes: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(',') if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
