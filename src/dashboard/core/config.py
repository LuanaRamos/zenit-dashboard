import json
from typing import List, Optional
from pydantic import Field, SecretStr, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientConfig(BaseModel):
    name: str
    ad_account_id: str
    page_id: str
    token: Optional[str] = None


class Settings(BaseSettings):
    """
    Configurações globais do Dashboard.
    Carrega variáveis do ambiente ou do arquivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    # Token Master e Clientes
    meta_master_token: SecretStr = Field(
        ...,
        alias="META_MASTER_TOKEN",
        description="Token de Acesso do Usuário (User Token)",
    )
    clients_json: str = Field(
        ...,
        alias="CLIENTS_JSON",
        description="Lista JSON de clientes configurados",
    )

    # Sentry Configuration
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    sentry_environment: str = Field("development", alias="SENTRY_ENVIRONMENT")
    sentry_release: str = Field("unknown", alias="SENTRY_RELEASE")
    sentry_traces_sample_rate: float = Field(0.0, alias="SENTRY_TRACES_SAMPLE_RATE")

    def get_clients(self) -> List[ClientConfig]:
        """Parse da string JSON em uma lista de objetos ClientConfig."""
        try:
            raw_list = json.loads(self.clients_json)
            return [ClientConfig(**c) for c in raw_list]
        except Exception as e:
            return []


# Instância global das configurações (Single Source of Truth)
settings = Settings()
