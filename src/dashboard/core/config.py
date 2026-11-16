import json
from typing import List, Optional
from pydantic import Field, SecretStr, BaseModel, ValidationError
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
    meta_master_token: SecretStr | None = Field(
        default=None,
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
        """Valida cada configuração, sem mascarar erros como 'sem clientes'."""
        try:
            raw_list = json.loads(self.clients_json)
        except json.JSONDecodeError as exc:
            raise ValueError("CLIENTS_JSON não é um JSON válido.") from exc

        if not isinstance(raw_list, list) or not raw_list:
            raise ValueError("CLIENTS_JSON deve conter uma lista não vazia de clientes.")

        clients: List[ClientConfig] = []
        names: set[str] = set()
        account_ids: set[str] = set()
        for index, item in enumerate(raw_list, 1):
            if not isinstance(item, dict):
                raise ValueError(f"CLIENTS_JSON: cliente {index} deve ser um objeto.")
            try:
                client = ClientConfig.model_validate(item)
            except ValidationError as exc:
                fields = ", ".join(
                    ".".join(str(k) for k in err["loc"]) for err in exc.errors()
                )
                raise ValueError(
                    f"CLIENTS_JSON: cliente {index} contém campos inválidos: {fields}."
                ) from None

            name_key = client.name.strip().casefold()
            account_key = client.ad_account_id.removeprefix("act_")
            if not name_key or not account_key or not client.page_id.strip():
                raise ValueError(
                    f"CLIENTS_JSON: cliente {index} possui nome ou IDs vazios."
                )
            if name_key in names:
                raise ValueError(f"CLIENTS_JSON: nome de cliente duplicado na entrada {index}.")
            if account_key in account_ids:
                raise ValueError(f"CLIENTS_JSON: conta de anúncios duplicada na entrada {index}.")
            if not client.token and not self.meta_master_token:
                raise ValueError(
                    f"CLIENTS_JSON: cliente {index} sem token próprio ou META_MASTER_TOKEN."
                )
            names.add(name_key)
            account_ids.add(account_key)
            clients.append(client)
        return clients


# Instância global das configurações (Single Source of Truth)
settings = Settings()
