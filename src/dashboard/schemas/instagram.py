from pydantic import BaseModel, ConfigDict, Field


class InstagramInsights(BaseModel):
    model_config = ConfigDict(frozen=True)
    reach: int = Field(
        default=0, description="Alcance retornado pelos Insights do Instagram"
    )


class InstagramStory(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    media_url: str | None = None
    permalink: str = ""
    timestamp: str = ""
    caption: str = ""
    reach: int = Field(default=0, description="Alcance orgânico do Story")
    exits: int = Field(default=0, description="Saídas do Story")
    replies: int = Field(default=0, description="Respostas (Replies)")
    taps_forward: int = Field(default=0, description="Toques para avançar")
    taps_back: int = Field(default=0, description="Toques para voltar")


class InstagramMedia(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    caption: str = ""
    media_url: str | None = None
    # Tráfego Pago & Dark Post mapping
    paid_reach: int = 0
    paid_impressions: int = 0
    paid_clicks: int = 0
    paid_link_clicks: int = 0
    paid_other_clicks: int = 0
    paid_likes: int | None = None
    paid_reactions: int | None = None
    paid_shares: int = 0
    paid_saved: int = 0
    paid_comments: int = 0
    paid_views: int = 0
    paid_destination: str | None = None
    paid_spend: float = 0.0
    paid_cpm: float = 0.0
    paid_cpc: float = 0.0
    paid_cpp: float = 0.0
    paid_ctr: float = 0.0
    paid_cpa: float | None = None
    paid_cost_per_outbound_click: float = 0.0
    paid_frequency: float = 0.0
    paid_video_avg_time: float = 0.0
    paid_video_p25: int = 0
    paid_video_p50: int = 0
    paid_video_p75: int = 0
    paid_roas: float = 0.0
    paid_action_values: float = 0.0
    paid_objective: str = ""
    paid_optimization_goal: str = ""
    paid_date_start: str = ""
    paid_date_stop: str = ""
    paid_ad_count: int = Field(default=0, description="Qtd de anúncios promovendo este post")
    thumbnail_url: str | None = None
    media_type: str = ""
    media_product_type: str = ""
    # Métricas orgânicas confirmadas pelo endpoint Media Insights.
    # None significa ausente/indisponível; zero é um valor real retornado pela API.
    like_count: int | None = None
    comments_count: int | None = None
    # Contadores públicos do objeto são preservados sem substituir Media Insights.
    visible_like_count: int | None = None
    visible_comments_count: int | None = None
    permalink: str = ""
    timestamp: str = ""
    reach: int | None = Field(
        default=None, description="Alcance retornado por Media Insights"
    )

    # Métricas de Media Insights (variam por tipo de mídia).
    shares: int | None = Field(default=None)
    saved: int | None = Field(default=None)
    total_interactions: int | None = Field(default=None)
    organic_views: int | None = Field(default=None)
    ig_reels_video_view_total_time: float | None = Field(default=None)
    ig_reels_avg_watch_time: float | None = Field(default=None)
    profile_activity: int | None = Field(default=None)
    profile_visits: int | None = Field(default=None)
    follows: int | None = Field(default=None)



class InstagramDemographics(BaseModel):
    model_config = ConfigDict(frozen=True)
    age_gender: dict[str, int] = Field(default_factory=dict, description="Distribuição Idade/Gênero")
    cities: dict[str, int] = Field(default_factory=dict, description="Distribuição por Cidades")
    countries: dict[str, int] = Field(default_factory=dict, description="Distribuição por Países")


class AccountDemographics(BaseModel):
    model_config = ConfigDict(frozen=True)
    followers: InstagramDemographics = Field(default_factory=InstagramDemographics)
    engaged: InstagramDemographics = Field(default_factory=InstagramDemographics)
    reached: InstagramDemographics = Field(default_factory=InstagramDemographics)
