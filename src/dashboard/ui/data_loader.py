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
    """Busca insights de campanhas com cache de 1 hora."""
    client = get_api_client()
    return client.get_campaign_insights(date_preset=date_preset)

@st.cache_data(ttl=3600)
def load_page_data() -> PageInsight:
    """Retorna métricas básicas da página com cache de 1 hora."""
    return PageInsight(followers=1250, reach=8450, engagement=340)

@st.cache_resource(ttl=900)
def fetch_organic_v12(date_preset: str) -> List[InstagramMedia]:
    """
    Busca as publicações orgânicas e cruza com os anúncios ativos.
    Tempo de cache (TTL): 900s (15 minutos) para evitar Rate Limit.
    Respeita imutabilidade Pydantic (frozen=True) usando model_copy.
    """
    ig_client = get_instagram_client()
    meta_client = get_api_client()
    
    # 1. Puxar as mídias recentes usando paginação real baseada em data
    if date_preset == "maximum":
        one_year_ago = int((datetime.datetime.now() - datetime.timedelta(days=365)).timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=one_year_ago)
    else:
        thirty_days_ago = int((datetime.datetime.now() - datetime.timedelta(days=30)).timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=thirty_days_ago)
    
    # 2. Puxar o dicionário unificado de anúncios (sem N+1 queries)
    ads_mapping = meta_client.get_ads_reach_mapping()
    
    # 3. Cruzamento e Matemática
    # Usa model_copy() pois InstagramMedia é frozen (imutável por Pydantic).
    # Jamais mutar diretamente: media.campo = valor vai lancar ValidationError.
    updated_media_list = []
    for media in media_list:
        ig_id = media.id
        update_data = {}

        if ig_id in ads_mapping:
            metrics = ads_mapping[ig_id]
            update_data["paid_reach"] = metrics["reach"]
            update_data["paid_impressions"] = metrics["impressions"]
            update_data["paid_clicks"] = metrics["clicks"]
            update_data["paid_likes"] = metrics["likes"]
            update_data["paid_shares"] = metrics.get("shares", 0)
            update_data["paid_saved"] = metrics.get("saved", 0)
            
            if update_data["paid_impressions"] > 0:
                update_data["paid_ctr"] = (update_data["paid_clicks"] / update_data["paid_impressions"]) * 100
            if update_data["paid_reach"] > 0:
                update_data["paid_frequency"] = update_data["paid_impressions"] / update_data["paid_reach"]
            
            update_data["organic_reach"] = media.reach
        else:
            # 100% orgânico se não houver anuncio vinculado
            update_data["organic_reach"] = media.reach

        updated_media_list.append(media.model_copy(update=update_data))

    return updated_media_list

@st.cache_resource(ttl=900)
def fetch_active_stories() -> list:
    """Busca stories ativos com cache local."""
    ig_client = get_instagram_client()
    return ig_client.get_active_stories()
