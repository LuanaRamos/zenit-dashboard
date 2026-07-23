from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    """
    Configurações globais do Dashboard.
    Carrega variáveis do ambiente ou do arquivo .env.
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Configurações do App na Meta (Opcional por enquanto, se usarmos só o token gerado)
    meta_app_id: str | None = Field(None, alias="META_APP_ID")
    meta_app_secret: str | None = Field(None, alias="META_APP_SECRET")
    
    # Tokens e IDs Principais
    meta_master_token: str = Field(..., alias="META_MASTER_TOKEN", description="Token de Acesso do Usuário (User Token)")
    ad_account_id: str = Field(..., alias="AD_ACCOUNT_ID", description="ID da Conta de Anúncios (ex: act_12345)")
    page_id: str = Field(..., alias="PAGE_ID", description="ID da Página do Facebook")

# Instância global das configurações (Single Source of Truth)
settings = Settings()