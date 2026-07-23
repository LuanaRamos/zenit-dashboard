from typing import Any
from pydantic import BaseModel, Field

class CampaignInsight(BaseModel):
    """
    Representa as métricas de performance de uma campanha no Meta Ads.
    Todos os campos possuem valores default para evitar crashes se a Meta não retornar a chave.
    """
    campaign_name: str = Field(default="Campanha Desconhecida", alias="campaign_name")
    campaign_id: str = Field(default="", alias="campaign_id")
    spend: float = Field(default=0.0)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cpc: float = Field(default=0.0)
    cpm: float = Field(default=0.0)
    leads: int = Field(default=0)
    cpl: float = Field(default=0.0)
    roas: float = Field(default=0.0)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "CampaignInsight":
        """
        Gera um insight a partir de um dicionário retornado pela API da Meta,
        fazendo o parse correto de valores aninhados (como actions e action_values).
        """
        # Extrair dados básicos que já vem na raiz
        parsed_data = {
            "campaign_name": data.get("campaign_name", "Campanha Desconhecida"),
            "campaign_id": data.get("campaign_id", ""),
            "spend": float(data.get("spend", 0.0)),
            "impressions": int(data.get("impressions", 0)),
            "clicks": int(data.get("clicks", 0)),
            "cpc": float(data.get("cpc", 0.0)),
            "cpm": float(data.get("cpm", 0.0))
        }

        # Extrair leads (actions -> action_type == 'lead')
        actions = data.get("actions", [])
        leads = 0
        for action in actions:
            if action.get("action_type") == "lead":
                leads = int(action.get("value", 0))
                break
        parsed_data["leads"] = leads

        # Calcular CPL se houver leads
        if leads > 0:
            parsed_data["cpl"] = parsed_data["spend"] / leads
        
        # O ROAS exigiria extrair do purchase_roas, vamos deixar 0.0 se não for e-commerce
        # ou se não estiver no dict de action_values
        
        return cls(**parsed_data)

class PageInsight(BaseModel):
    """
    Métricas da página/Instagram orgânico.
    """
    followers: int = Field(default=0)
    reach: int = Field(default=0)
    engagement: int = Field(default=0)