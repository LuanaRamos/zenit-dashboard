from typing import Any
from pydantic import BaseModel, Field

class CampaignInsight(BaseModel):
    """
    Representa as métricas de performance de uma campanha no Meta Ads.
    Todos os campos possuem valores default para evitar crashes se a Meta não retornar a chave.
    """
    OBJECTIVE_MAPPING = {
        "OUTCOME_AWARENESS": "Reconhecimento",
        "OUTCOME_TRAFFIC": "Tráfego",
        "OUTCOME_ENGAGEMENT": "Engajamento",
        "OUTCOME_LEADS": "Cadastros",
        "OUTCOME_APP_PROMOTION": "Promoção de App",
        "OUTCOME_SALES": "Vendas",
        "LINK_CLICKS": "Tráfego (Cliques no Link)",
        "POST_ENGAGEMENT": "Engajamento",
        "PAGE_LIKES": "Curtidas na Página",
        "EVENT_RESPONSES": "Resposta a Eventos",
        "MESSAGES": "Mensagens",
        "VIDEO_VIEWS": "Visualizações de Vídeo",
        "LEAD_GENERATION": "Geração de Cadastros",
        "APP_INSTALLS": "Instalações do App",
        "CONVERSIONS": "Conversões",
        "PRODUCT_CATALOG_SALES": "Vendas do Catálogo",
        "STORE_VISITS": "Visitas à Loja",
        "BRAND_AWARENESS": "Reconhecimento de Marca",
        "REACH": "Alcance",
        "LOCAL_AWARENESS": "Reconhecimento Local"
    }

    campaign_name: str = Field(default="Campanha Desconhecida", alias="campaign_name")
    campaign_id: str = Field(default="", alias="campaign_id")
    objective: str = Field(default="UNKNOWN", description="Objetivo ODAX da Campanha")
    spend: float = Field(default=0.0)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cpc: float = Field(default=0.0)
    cpm: float = Field(default=0.0)
    
    # Métricas Específicas Dinâmicas
    leads: int = Field(default=0)
    cpl: float = Field(default=0.0)
    
    whatsapp_starts: int = Field(default=0, description="Conversas Iniciadas por Mensagem")
    cost_per_whatsapp: float = Field(default=0.0)
    
    instagram_follows: int = Field(default=0, description="Seguidores no Instagram Gerados")
    cost_per_follower: float = Field(default=0.0)
    
    profile_visits: int = Field(default=0, description="Visitas ao Perfil")
    cost_per_profile_visit: float = Field(default=0.0)
    
    roas: float = Field(default=0.0)

    @property
    def objective_friendly(self) -> str:
        """Retorna o nome do objetivo traduzido e amigável para a UI."""
        return self.OBJECTIVE_MAPPING.get(self.objective, self.objective)

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
            "objective": data.get("objective", "UNKNOWN"),
            "spend": float(data.get("spend", 0.0)),
            "impressions": int(data.get("impressions", 0)),
            "clicks": int(data.get("clicks", 0)),
            "cpc": float(data.get("cpc", 0.0)),
            "cpm": float(data.get("cpm", 0.0))
        }

        # Analisar o array de 'actions' para buscar eventos específicos
        actions = data.get("actions", [])
        
        leads = 0
        whatsapp_starts = 0
        instagram_follows = int(data.get("instagram_follows", 0)) # Pode vir na raiz na API nova
        profile_visits = 0
        
        for action in actions:
            act_type = action.get("action_type", "")
            val = int(action.get("value", 0))
            
            if act_type == "lead":
                leads += val
            elif act_type == "onsite_conversion.messaging_conversation_started_7d" or "message" in act_type:
                whatsapp_starts += val
            elif act_type == "instagram_follows":
                instagram_follows += val
            elif act_type == "onsite_conversion.post_engagement" or "profile" in act_type:
                profile_visits += val

        parsed_data["leads"] = leads
        parsed_data["whatsapp_starts"] = whatsapp_starts
        parsed_data["instagram_follows"] = instagram_follows
        parsed_data["profile_visits"] = profile_visits

        # Calcular Custos
        spend = parsed_data["spend"]
        if leads > 0:
            parsed_data["cpl"] = spend / leads
        if whatsapp_starts > 0:
            parsed_data["cost_per_whatsapp"] = spend / whatsapp_starts
        if instagram_follows > 0:
            parsed_data["cost_per_follower"] = spend / instagram_follows
        if profile_visits > 0:
            parsed_data["cost_per_profile_visit"] = spend / profile_visits
            
        return cls(**parsed_data)

class PageInsight(BaseModel):
    """
    Métricas da página/Instagram orgânico.
    """
    followers: int = Field(default=0)
    reach: int = Field(default=0)
    engagement: int = Field(default=0)