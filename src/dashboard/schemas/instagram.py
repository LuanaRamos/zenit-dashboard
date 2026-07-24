from pydantic import BaseModel, Field
from typing import Optional

class InstagramInsights(BaseModel):
    reach: int = Field(default=0, description="Alcance Orgânico + Pago puxado do Insights")

class InstagramMedia(BaseModel):
    id: str
    caption: str = ""
    media_url: Optional[str] = None
    like_count: int = 0
    comments_count: int = 0
    permalink: str = ""
    timestamp: str = ""
    reach: int = Field(default=0, description="Alcance total da Graph API (Orgânico + Pago)")
    
    # Dados de Mapeamento de Ads (Calculados posteriormente)
    paid_reach: int = Field(default=0, description="Soma do alcance pago (Ads)")
    paid_impressions: int = Field(default=0, description="Soma das impressões pagas (Ads)")
    paid_clicks: int = Field(default=0, description="Soma de cliques no link (Ads)")
    paid_ctr: float = Field(default=0.0, description="CTR Ponderado Pago (%)")
    paid_frequency: float = Field(default=0.0, description="Frequência Ponderada Paga")
    paid_likes: int = Field(default=0, description="Soma de curtidas pagas nos anúncios (Dark Posts)")
    organic_reach: int = Field(default=0, description="Alcance puramente orgânico (Total - Pago)")

    @property
    def total_likes(self) -> int:
        return self.like_count + self.paid_likes
