from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any

# ==========================================
# REGRAS DO ULTIMATE MARKETING BUNDLE (META)
# ==========================================

class MetaPage(BaseModel):
    """Representa uma Página do Facebook vinculada ao App."""
    id: str = Field(..., description="O Page ID obrigatório (Facebook Page ID)")
    name: str = Field(..., description="Nome da Página")
    access_token: str = Field(..., description="Token de acesso específico da página")

class InstagramAccount(BaseModel):
    """Representa uma Conta Profissional do Instagram vinculada à Página."""
    id: str = Field(..., description="O Instagram Business Account ID")
    username: str = Field(..., description="O @username do Instagram")
    profile_picture_url: Optional[str] = None

class AdAccount(BaseModel):
    """Representa uma Conta de Anúncios vinculada."""
    account_id: str = Field(..., description="O Ad Account ID (sem o prefixo act_)")
    name: str = Field(..., description="Nome da Conta de Anúncios")

    @field_validator("account_id", mode="before")
    def strip_act_prefix(cls, value: str) -> str:
        """A Meta sempre manda 'act_' na frente do ID. Essa regra de ML limpa isso."""
        if value.startswith("act_"):
            return value[4:]
        return value

class CampaignPerformance(BaseModel):
    """Validação rigorosa de Cents-not-Dollars e ODAX (Marketing Bundle)."""
    campaign_id: str
    campaign_name: str
    objective: str = Field(..., description="ODAX Objective (ex: OUTCOME_LEADS)")
    spend_cents: int = Field(0, alias="spend", description="Gasto sempre em centavos")
    
    @field_validator("spend_cents", mode="before")
    def convert_spend_to_cents(cls, value: Any) -> int:
        """A API da Meta às vezes retorna string float. Converte tudo para INT (centavos)."""
        if isinstance(value, str):
            return int(float(value) * 100)
        elif isinstance(value, (int, float)):
            return int(value * 100)
        return 0

    @property
    def spend_brl(self) -> str:
        """Formata para exibição na UI."""
        return f"R$ {self.spend_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
