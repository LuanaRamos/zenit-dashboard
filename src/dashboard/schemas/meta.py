from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


class CampaignInsight(BaseModel):
    """
    Representa as métricas de performance de uma campanha no Meta Ads.
    Todos os campos possuem valores default para evitar crashes se a Meta não retornar a chave.
    """

    model_config = ConfigDict(frozen=True)
    OBJECTIVE_MAPPING: ClassVar[dict[str, str]] = {
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
        "LOCAL_AWARENESS": "Reconhecimento Local",
    }

    campaign_name: str = Field(default="Campanha Desconhecida", alias="campaign_name")
    campaign_id: str = Field(default="", alias="campaign_id")
    objective: str = Field(default="UNKNOWN", description="Objetivo ODAX da Campanha")
    daily_budget: float = Field(default=0.0)
    spend: float = Field(default=0.0)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cpc: float = Field(default=0.0)
    cpm: float = Field(default=0.0)

    # Métricas Específicas Dinâmicas
    leads: int = Field(default=0)
    site_leads: int = Field(default=0)
    native_leads: int = Field(default=0)
    cpl: float = Field(default=0.0)

    whatsapp_starts: int = Field(
        default=0, description="Conversas Iniciadas por Mensagem"
    )
    cost_per_whatsapp: float = Field(default=0.0)

    instagram_follows: int = Field(
        default=0, description="Seguidores no Instagram Gerados"
    )
    cost_per_follower: float = Field(default=0.0)

    profile_visits: int = Field(default=0, description="Visitas ao Perfil")
    cost_per_profile_visit: float = Field(default=0.0)

    roas: float = Field(default=0.0)

    @property
    def objective_friendly(self) -> str:
        """Retorna o nome do objetivo traduzido e amigável para a UI, baseado no comportamento real da campanha."""
        if self.whatsapp_starts > 0 or self.objective == "MESSAGES":
            return "Mensagens (WhatsApp/Direct)"
        if self.profile_visits > 0 or self.instagram_follows > 0:
            return "Visitas ao Perfil / Seguidores"
        if self.objective == "OUTCOME_ENGAGEMENT":
            return "Mensagens / Engajamento"
        if self.objective in ["OUTCOME_TRAFFIC", "LINK_CLICKS"]:
            return "Tráfego no Perfil"
            
        return self.OBJECTIVE_MAPPING.get(self.objective, self.objective)

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "CampaignInsight":
        """
        Gera um insight a partir de um dicionário retornado pela API da Meta,
        fazendo o parse correto de valores aninhados (como actions e action_values).
        """
        # Extrair dados básicos que já vem na raiz
        parsed_data = {
            "campaign_name": data.get("campaign_name") or "Campanha Desconhecida",
            "campaign_id": data.get("campaign_id") or "",
            "objective": data.get("objective") or "UNKNOWN",
            "daily_budget": float(data.get("daily_budget") or 0.0) / 100.0,
            "spend": float(data.get("spend") or 0.0),
            "impressions": int(data.get("impressions") or 0),
            "clicks": int(data.get("clicks") or 0),
            "cpc": float(data.get("cpc") or 0.0),
            "cpm": float(data.get("cpm") or 0.0),
        }

        # Analisar o array de 'actions' para buscar eventos específicos
        actions = data.get("actions") or []

        site_leads = 0
        native_leads = 0
        whatsapp_starts = 0
        instagram_follows = 0
        profile_visits = 0

        for action in actions:
            act_type = action.get("action_type", "")
            val = int(action.get("value", 0))

            if act_type == "lead":
                site_leads += val
            elif act_type == "leadgen":
                native_leads += val
            elif act_type in [
                "onsite_conversion.messaging_conversation_started_7d",
                "onsite_conversion.messaging_first_reply",
                "onsite_conversion.messaging_connections"
            ]:
                whatsapp_starts += val
            elif act_type == "instagram_follows":
                instagram_follows += val
            elif act_type in [
                "onsite_conversion.post_engagement",
                "profile_visit",
                "instagram_profile_views"
            ]:
                profile_visits += val

        # Fallback para instagram_follows caso a Meta retorne apenas na raiz
        if instagram_follows == 0:
            instagram_follows = int(data.get("instagram_follows", 0))

        leads = site_leads + native_leads
        parsed_data["leads"] = leads
        parsed_data["site_leads"] = site_leads
        parsed_data["native_leads"] = native_leads
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

    model_config = ConfigDict(frozen=True)
    followers: int = Field(default=0)
    reach: int = Field(default=0)
    engagement: int = Field(default=0)

class DemographicsInsight(BaseModel):
    """Métricas quebradas por público (Idade e Gênero)"""
    model_config = ConfigDict(frozen=True)
    age: str = Field(default="Unknown")
    gender: str = Field(default="Unknown")
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    spend: float = Field(default=0.0)

class CreativePerformance(BaseModel):
    """Performance individual de um anúncio focado no Criativo"""
    model_config = ConfigDict(frozen=True)
    ad_id: str = Field(default="")
    ad_name: str = Field(default="Unknown")
    image_url: str | None = Field(default=None)
    thumbnail_url: str | None = Field(default=None)
    body: str | None = Field(default=None)
    spend: float = Field(default=0.0)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    leads: int = Field(default=0)
    whatsapp_starts: int = Field(default=0)
    cpa: float = Field(default=0.0)
    cpc: float = Field(default=0.0)

class CatalogData(BaseModel):
    """Dados sobre Catálogo e E-commerce"""
    model_config = ConfigDict(frozen=True)
    catalog_id: str
    name: str
    product_count: int = Field(default=0)
    roas: float = Field(default=0.0)
    spend: float = Field(default=0.0)
    purchases: int = Field(default=0)
