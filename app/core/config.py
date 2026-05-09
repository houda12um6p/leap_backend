from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./app.db"

    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    @field_validator("secret_key")
    @classmethod
    def _require_real_secret(cls, v: str) -> str:
        placeholders = {"", "your-secret-key-here", "your-super-secret-key-here-change-in-production", "your-secret-key-change-this"}
        if v in placeholders:
            raise ValueError(
                "SECRET_KEY is missing or set to a placeholder. "
                "Set a strong SECRET_KEY in the environment (.env) before starting."
            )
        return v
    
    api_v1_str: str = "/api/v1"
    project_name: str = "FastAPI Backend"
    
    github_api_url: str = "https://api.github.com"
    github_token: str = ""
    github_webhook_secret: str = ""
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = "LEAP"

    openrouter_api_key: str = ""
    llm_max_concurrency: int = 4

    class Config:
        env_file = ".env"

settings = Settings()
