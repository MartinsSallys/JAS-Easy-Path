from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "JAS Easy Path API"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rotacerta"
    database_echo: bool = False

    # Geocoding - Nominatim
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "jas-easy-path/1.0"
    nominatim_rate_limit: float = 1.0  # requests per second

    # Matrix - OpenRouteService
    ors_base_url: str = "https://api.openrouteservice.org"
    ors_api_key: str = ""  # Set in .env
    ors_rate_limit: int = 40  # requests per minute
    ors_max_locations: int = 50

    # Optimization
    ortools_time_limit_seconds: int = 30
    ortools_first_solution_strategy: str = "PATH_CHEAPEST_ARC"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


settings = Settings()