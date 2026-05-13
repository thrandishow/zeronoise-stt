from pydantic_settings import SettingsConfigDict, BaseSettings
import logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    broker_url: str = ""
    broker_port: int = 0


settings = Settings()
logger = logging.getLogger(__name__)
