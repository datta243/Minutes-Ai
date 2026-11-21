from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    colab_inference_url: str = ""
    colab_api_key: str = ""
    max_upload_mb: int = 200
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
