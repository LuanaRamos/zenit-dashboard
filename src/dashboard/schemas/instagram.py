from pydantic import BaseModel, ConfigDict, Field


class InstagramInsights(BaseModel):
    model_config = ConfigDict(frozen=True)
    reach: int = Field(
        default=0, description="Alcance Orgânico + Pago puxado do Insights"
    )


class InstagramStory(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    media_url: str | None = None
    permalink: str = ""
    timestamp: str = ""
    caption: str = ""
    reach: int = Field(default=0, description="Alcance total da Graph API (Story)")
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
    paid_likes: int = 0
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
    paid_cpa: float = 0.0
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
    thumbnail_url: str | None = None
    media_type: str = ""
    media_product_type: str = ""
    like_count: int = 0
    comments_count: int = 0
    saved_count: int = 0
    shares_count: int = 0
    reposts_count: int = 0
    permalink: str = ""
    timestamp: str = ""
    reach: int = Field(
        default=0, description="Alcance total da Graph API (Orgânico + Pago)"
    )

    # Métricas Orgânicas (variam por tipo)
    shares: int = Field(default=0)
    saved: int = Field(default=0)
    organic_views: int = Field(default=0)
    ig_reels_video_view_total_time: float = Field(default=0.0)  # Ms to Seconds later
    ig_reels_avg_watch_time: float = Field(default=0.0)
    profile_activity: int = Field(default=0)
    profile_visits: int = Field(default=0)
    follows: int = Field(default=0)

    # Dados de Mapeamento de Ads (Calculados posteriormente)
    paid_reach: int = Field(default=0, description="Soma do alcance pago (Ads)")
    paid_impressions: int = Field(
        default=0, description="Soma das impressões pagas (Ads)"
    )
    paid_clicks: int = Field(default=0, description="Soma de cliques no total (Ads)")
    paid_link_clicks: int = Field(default=0, description="Soma de cliques no link (Ads)")
    paid_other_clicks: int = Field(default=0, description="Soma de outros cliques (Ads)")
    paid_ctr: float = Field(default=0.0, description="CTR Ponderado Pago (%)")
    paid_frequency: float = Field(default=0.0, description="Frequência Ponderada Paga")
    paid_destination: str = Field(default="N/A", description="Destino do Tráfego (Ads)")
    paid_likes: int = Field(
        default=0, description="Soma de curtidas pagas nos anúncios (Dark Posts)"
    )
    paid_shares: int = Field(default=0, description="Shares via Ads")
    paid_saved: int = Field(default=0, description="Saves via Ads")
    paid_views: int = Field(default=0, description="Views via Ads (video_view)")
    organic_reach: int = Field(
        default=0, description="Alcance puramente orgânico (Total - Pago)"
    )

    @property
    def total_likes(self) -> int:
        return self.like_count + self.paid_likes

    @property
    def total_shares(self) -> int:
        return self.shares_count + self.paid_shares

    @property
    def total_saved(self) -> int:
        return self.saved_count + self.paid_saved


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
