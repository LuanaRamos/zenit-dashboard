import streamlit as st
from typing import List
from api.meta_client import MetaAdsClient
from api.instagram_client import InstagramClient
from schemas.meta import CampaignInsight, PageInsight
from schemas.instagram import InstagramMedia
import datetime

@st.cache_resource
def get_api_client() -> MetaAdsClient:
    """Inicializa o cliente de Ads apenas uma vez."""
    return MetaAdsClient()

@st.cache_resource
def get_instagram_client() -> InstagramClient:
    """Inicializa o cliente do Instagram apenas uma vez."""
    return InstagramClient()

@st.cache_resource(ttl=3600)
def fetch_campaigns_v8(date_preset: str) -> List[CampaignInsight]:
    client = get_api_client()
    return client.get_campaign_insights(date_preset=date_preset)

@st.cache_data(ttl=3600)
def load_page_data() -> PageInsight:
    return PageInsight(followers=1250, reach=8450, engagement=340)

@st.cache_resource(ttl=900)
def fetch_organic_v11(date_preset: str) -> List[InstagramMedia]:
    """
    Busca as publicações orgânicas e cruza com os anúncios ativos.
    Tempo de cache (TTL): 900s (15 minutos) para evitar Rate Limit.
    """
    ig_client = get_instagram_client()
    meta_client = get_api_client()
    
    # 1. Puxar as mídias recentes usando paginação real baseada em data
    if date_preset == "maximum":
        # 1 ano exato para trás em Unix Timestamp
        one_year_ago = int((datetime.datetime.now() - datetime.timedelta(days=365)).timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=one_year_ago)
    else:
        # 30 dias exatos para trás em Unix Timestamp
        thirty_days_ago = int((datetime.datetime.now() - datetime.timedelta(days=30)).timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=thirty_days_ago)
    
    # 2. Puxar o dicionário unificado de anúncios (sem N+1 queries)
    ads_mapping = meta_client.get_ads_reach_mapping()
    
    # 3. Cruzamento e Matemática
    for media in media_list:
        ig_id = media.id
        if ig_id in ads_mapping:
            metrics = ads_mapping[ig_id]
            
            media.paid_reach = metrics["reach"]
            media.paid_impressions = metrics["impressions"]
            media.paid_clicks = metrics["clicks"]
            media.paid_likes = metrics["likes"]
            
            # Cálculos Ponderados para evitar distorção matemática
            if media.paid_impressions > 0:
                media.paid_ctr = (media.paid_clicks / media.paid_impressions) * 100
                
            if media.paid_reach > 0:
                media.paid_frequency = media.paid_impressions / media.paid_reach
                
            # O Alcance puramente orgânico
            media.organic_reach = max(0, media.reach - media.paid_reach)
        else:
            # Se não teve anúncio, 100% do alcance é orgânico
            media.organic_reach = media.reach
            
    return media_list
