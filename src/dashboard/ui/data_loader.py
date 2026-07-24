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

@st.cache_data(ttl=86400)
def get_account_creation_date_cached() -> datetime.date:
    client = get_api_client()
    return client.get_account_created_time()

@st.cache_resource
def get_instagram_client() -> InstagramClient:
    """Inicializa o cliente do Instagram apenas uma vez."""
    return InstagramClient()

@st.cache_data(ttl=3600)
def fetch_campaigns_v8(date_preset: str, time_range: dict = None) -> List[CampaignInsight]:
    client = get_api_client()
    return client.get_campaign_insights(date_preset=date_preset, time_range=time_range)

@st.cache_data(ttl=3600)
def load_page_data() -> PageInsight:
    return PageInsight(followers=1250, reach=8450, engagement=340)

@st.cache_data(ttl=900)
def fetch_organic_v12(date_preset: str, time_range: dict = None) -> List[InstagramMedia]:
    """
    Busca as publicações orgânicas e cruza com os anúncios ativos.
    Tempo de cache (TTL): 900s (15 minutos) para evitar Rate Limit.
    """
    ig_client = get_instagram_client()
    meta_client = get_api_client()
    
    # 1. Puxar as mídias recentes usando paginação real baseada em data
    if time_range:
        since_dt = datetime.datetime.strptime(time_range["since"], "%Y-%m-%d")
        until_dt = datetime.datetime.strptime(time_range["until"], "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
        
        since_timestamp = int(since_dt.timestamp())
        until_timestamp = int(until_dt.timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=since_timestamp, until_timestamp=until_timestamp)
        
    elif date_preset == "maximum":
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
            
            # Cálculos Ponderados para evitar distorção matemática
            if update_data["paid_impressions"] > 0:
                update_data["paid_ctr"] = (update_data["paid_clicks"] / update_data["paid_impressions"]) * 100
                
            if update_data["paid_reach"] > 0:
                update_data["paid_frequency"] = update_data["paid_impressions"] / update_data["paid_reach"]
                
            # O Alcance puramente orgânico (A API do IG não contabiliza Ads aqui para Dark Posts de Reels)
            update_data["organic_reach"] = media.reach
        else:
            # Se não teve anúncio, 100% do alcance é orgânico
            update_data["organic_reach"] = media.reach
            
        updated_media_list.append(media.model_copy(update=update_data))
            
    return updated_media_list

@st.cache_data(ttl=900)
def fetch_active_stories() -> list:
    """Busca stories ativos com cache local."""
    ig_client = get_instagram_client()
    return ig_client.get_active_stories()
