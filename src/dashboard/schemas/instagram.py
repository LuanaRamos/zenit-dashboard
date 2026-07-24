from pydantic import BaseModel, Field
from typing import Optional

class InstagramInsights(BaseModel):
    reach: int = Field(default=0, description="Alcance Orgânico + Pago puxado do Insights")

class InstagramStory(BaseModel):
    id: str
    media_url: Optional[str] = None
    permalink: str = ""
    timestamp: str = ""
    caption: str = ""
    reach: int = Field(default=0, description="Alcance total da Graph API (Story)")
    exits: int = Field(default=0, description="Saídas do Story")
    replies: int = Field(default=0, description="Respostas (Replies)")
    taps_forward: int = Field(default=0, description="Toques para avançar")
    taps_back: int = Field(default=0, description="Toques para voltar")

class InstagramMedia(BaseModel):
    id: str
    caption: str = ""
    media_url: Optional[str] = None
    media_type: str = ""
    media_product_type: str = ""
    like_count: int = 0
    comments_count: int = 0
    permalink: str = ""
    timestamp: str = ""
    reach: int = Field(default=0, description="Alcance total da Graph API (Orgânico + Pago)")
    
    # Métricas Orgânicas (variam por tipo)
    shares: int = Field(default=0)
    saved: int = Field(default=0)
    ig_reels_video_view_total_time: float = Field(default=0.0) # Ms to Seconds later
    ig_reels_avg_watch_time: float = Field(default=0.0)
    profile_activity: int = Field(default=0)
    profile_visits: int = Field(default=0)
    follows: int = Field(default=0)

    # Dados de Mapeamento de Ads (Calculados posteriormente)
    paid_reach: int = Field(default=0, description="Soma do alcance pago (Ads)")
    paid_impressions: int = Field(default=0, description="Soma das impressões pagas (Ads)")
    paid_clicks: int = Field(default=0, description="Soma de cliques no link (Ads)")
    paid_ctr: float = Field(default=0.0, description="CTR Ponderado Pago (%)")
    paid_frequency: float = Field(default=0.0, description="Frequência Ponderada Paga")
    paid_likes: int = Field(default=0, description="Soma de curtidas pagas nos anúncios (Dark Posts)")
    paid_shares: int = Field(default=0, description="Shares via Ads")
    paid_saved: int = Field(default=0, description="Saves via Ads")
    organic_reach: int = Field(default=0, description="Alcance puramente orgânico (Total - Pago)")

    @property
    def total_likes(self) -> int:
        return self.like_count + self.paid_likes
    
    @property
    def total_shares(self) -> int:
        return self.shares + self.paid_shares
    
    @property
    def total_saved(self) -> int:
        return self.saved + self.paid_saved
