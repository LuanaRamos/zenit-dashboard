from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações globais do Dashboard.
    Carrega variáveis do ambiente ou do arquivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    # Configurações do App na Meta
    meta_app_id: str | None = Field(
        None, alias="META_APP_ID", description="ID do Aplicativo na Meta"
    )
    meta_app_secret: SecretStr | None = Field(
        None, alias="META_APP_SECRET", description="Secret do Aplicativo na Meta"
    )
    meta_redirect_uri: str | None = Field(
        None,
        alias="META_REDIRECT_URI",
        description="URI de Redirecionamento configurada no App",
    )

    # Tokens e IDs Principais
    meta_master_token: SecretStr = Field(
        ...,
        alias="META_MASTER_TOKEN",
        description="Token de Acesso do Usuário (User Token)",
    )
    ad_account_id: str = Field(
        ...,
        alias="AD_ACCOUNT_ID",
        description="ID da Conta de Anúncios (ex: act_12345)",
    )
    page_id: str = Field(..., alias="PAGE_ID", description="ID da Página do Facebook")

    # Sentry Configuration
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    sentry_environment: str = Field("development", alias="SENTRY_ENVIRONMENT")
    sentry_release: str = Field("unknown", alias="SENTRY_RELEASE")
    sentry_traces_sample_rate: float = Field(0.0, alias="SENTRY_TRACES_SAMPLE_RATE")


# Instância global das configurações (Single Source of Truth)
settings = Settings()
