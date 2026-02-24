from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Notion
    notion_api_key: str
    notion_database_id: str
    notion_webhook_secret: str

    # Zotero
    zotero_api_key: str

    # Database
    database_url: str = "sqlite+aiosqlite:///./notero_sync.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    # Feature flags
    delete_orphaned_notes: bool = False
