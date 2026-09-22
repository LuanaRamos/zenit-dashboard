from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field


CANONICAL_MESSAGING_ACTION = "onsite_conversion.messaging_conversation_started_7d"
LEGACY_MESSAGING_ACTION = "onsite_conversion.messaging_conversation_started"


def _action_values(actions: list[dict[str, Any]] | None) -> dict[str, int]:
    """Index Ads action rows without merging different action types."""
    values: dict[str, int] = {}
    for action in actions or []:
        action_type = action.get("action_type")
        if not action_type:
            continue
        values[action_type] = values.get(action_type, 0) + int(action.get("value") or 0)
    return values


def parse_paid_actions(actions: list[dict[str, Any]] | None) -> dict[str, int | None]:
    """Normalize only the canonical Ads actions used by both paid views."""
    values = _action_values(actions)
    site_leads = values.get("offsite_conversion.fb_pixel_lead")
    native_leads = values.get("leadgen")

    # `lead` is Meta's aggregate. Its presence, including an explicit zero, wins
    # over source subtypes so the same conversion is never counted twice.
    leads = values["lead"] if "lead" in values else (site_leads or 0) + (native_leads or 0)

    # The 7d event is canonical for this dashboard. Accept the one exact legacy
    # event only when the canonical row is absent; prefix variants are ignored.
    if CANONICAL_MESSAGING_ACTION in values:
        messaging_conversations = values[CANONICAL_MESSAGING_ACTION]
    else:
        messaging_conversations = values.get(LEGACY_MESSAGING_ACTION, 0)

    return {
        "leads": leads,
        "site_leads": site_leads,
        "native_leads": native_leads,
        "messaging_conversations": messaging_conversations,
        "link_clicks_action": values.get("link_click", 0),
        "instagram_follows": values.get("instagram_follows", 0),
        "profile_visits": values.get("profile_visit", 0)
        + values.get("instagram_profile_views", 0),
        "post_reactions": values.get("post_reaction", 0),
        "post_shares": values.get("post", 0),
        "post_saves": values.get("onsite_conversion.post_save", 0),
        "post_comments": values.get("comment", 0),
    }


def parse_outbound_clicks(rows: list[dict[str, Any]] | None) -> int:
    """Read outbound clicks without treating link clicks as an alias."""
    return _action_values(rows).get("outbound_click", 0)


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
    link_clicks: int = Field(default=0)
    inline_link_clicks: int = Field(default=0)
    outbound_clicks: int = Field(default=0)
    other_clicks: int = Field(default=0)
    cpc: float = Field(default=0.0)
    cpm: float = Field(default=0.0)
    
    post_reactions: int = Field(default=0)
    post_shares: int = Field(default=0)
    post_saves: int = Field(default=0)
    post_comments: int = Field(default=0)

    # Métricas Específicas Dinâmicas
    leads: int = Field(default=0)
    site_leads: int | None = Field(default=None)
    native_leads: int | None = Field(default=None)
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
            return "Mensagens"
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
        action_metrics = parse_paid_actions(actions)
        site_leads = action_metrics["site_leads"]
        native_leads = action_metrics["native_leads"]
        leads = action_metrics["leads"]
        whatsapp_starts = action_metrics["messaging_conversations"]
        instagram_follows = action_metrics["instagram_follows"]
        profile_visits = action_metrics["profile_visits"]
        inline_link_clicks = int(data.get("inline_link_clicks") or 0) if "inline_link_clicks" in data else action_metrics["link_clicks_action"]
        outbound_clicks = parse_outbound_clicks(data.get("outbound_clicks"))

        post_reactions = action_metrics["post_reactions"]
        post_shares = action_metrics["post_shares"]
        post_saves = action_metrics["post_saves"]
        post_comments = action_metrics["post_comments"]

        # Fallback para instagram_follows caso a Meta retorne apenas na raiz
        if instagram_follows == 0:
            instagram_follows = int(data.get("instagram_follows", 0))

        parsed_data["leads"] = leads
        parsed_data["site_leads"] = site_leads
        parsed_data["native_leads"] = native_leads
        parsed_data["whatsapp_starts"] = whatsapp_starts
        parsed_data["instagram_follows"] = instagram_follows
        parsed_data["profile_visits"] = profile_visits
        parsed_data["link_clicks"] = inline_link_clicks
        parsed_data["inline_link_clicks"] = inline_link_clicks
        parsed_data["outbound_clicks"] = outbound_clicks
        parsed_data["other_clicks"] = max(0, parsed_data["clicks"] - inline_link_clicks)
        parsed_data["post_reactions"] = post_reactions
        parsed_data["post_shares"] = post_shares
        parsed_data["post_saves"] = post_saves
        parsed_data["post_comments"] = post_comments
        
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
    objective: str = Field(default="UNKNOWN")
    image_url: str | None = Field(default=None)
    thumbnail_url: str | None = Field(default=None)
    body: str | None = Field(default=None)
    spend: float = Field(default=0.0)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    link_clicks: int = Field(default=0)
    inline_link_clicks: int = Field(default=0)
    outbound_clicks: int = Field(default=0)
    other_clicks: int = Field(default=0)
    
    post_reactions: int = Field(default=0)
    post_shares: int = Field(default=0)
    post_saves: int = Field(default=0)
    post_comments: int = Field(default=0)

    leads: int = Field(default=0)
    whatsapp_starts: int = Field(default=0)
    instagram_follows: int = Field(default=0)
    profile_visits: int = Field(default=0)
    cpa: float = Field(default=0.0)
    cpc: float = Field(default=0.0)
    traffic_destination: str = Field(default="Não Identificado")
    # Público-alvo e agendamento
    ad_status: str = Field(default="")
    adset_name: str = Field(default="")
    start_time: str | None = Field(default=None)
    end_time: str | None = Field(default=None)
    adset_status: str = Field(default="")
    age_min: int | None = Field(default=None)
    age_max: int | None = Field(default=None)
    genders: list[str] = Field(default_factory=list)
    target_cities: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    target_regions: list[str] = Field(default_factory=list)

    @property
    def objective_friendly(self) -> str:
        if self.whatsapp_starts > 0 or self.objective == "MESSAGES":
            return "Mensagens"
        if self.objective == "OUTCOME_ENGAGEMENT":
            return "Mensagens / Engajamento"
        if self.objective in ["OUTCOME_TRAFFIC", "LINK_CLICKS"]:
            return "Tráfego"
        from schemas.meta import CampaignInsight
        return CampaignInsight.OBJECTIVE_MAPPING.get(self.objective, self.objective)


class CatalogData(BaseModel):
    """Dados sobre Catálogo e E-commerce"""
    model_config = ConfigDict(frozen=True)
    catalog_id: str
    name: str
    product_count: int = Field(default=0)
    roas: float = Field(default=0.0)
    spend: float = Field(default=0.0)
    purchases: int = Field(default=0)
