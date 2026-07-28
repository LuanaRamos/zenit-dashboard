import streamlit as st
from typing import List
from api.meta_client import MetaAdsClient
from api.instagram_client import InstagramClient
from schemas.meta import CampaignInsight, PageInsight
from schemas.instagram import InstagramMedia
import datetime
from core.config import settings

@st.cache_resource
def get_api_client(client_name: str) -> MetaAdsClient:
    clients = settings.get_clients()
    _cache_buster = 2
    client_config = next(c for c in clients if c.name == client_name)
    return MetaAdsClient(client_config)

@st.cache_data(ttl=86400)
def get_account_creation_date_cached(client_name: str) -> datetime.date:
    client = get_api_client(client_name)
    return client.get_account_created_time()

@st.cache_resource
def get_instagram_client(client_name: str) -> InstagramClient:
    clients = settings.get_clients()
    _cache_buster = 2
    client_config = next(c for c in clients if c.name == client_name)
    return InstagramClient(client_config)

@st.cache_data(ttl=3600)
def fetch_campaigns_v8(date_preset: str, time_range: dict | None, client_name: str) -> List[CampaignInsight]:
    client = get_api_client(client_name)
    return client.get_campaign_insights(date_preset=date_preset, time_range=time_range)

@st.cache_data(ttl=3600)
def load_page_data(client_name: str) -> PageInsight:
    return PageInsight(followers=1250, reach=8450, engagement=340)

@st.cache_data(ttl=3600)
def fetch_organic_leads_cached(date_preset: str, time_range: dict | None, client_name: str) -> int:
    client = get_api_client(client_name)
    return client.get_total_organic_leads(date_preset, time_range)

@st.cache_data(ttl=900)
def fetch_instagram_ads_mapping_cached(date_preset: str, time_range: dict | None, client_name: str) -> dict:
    meta_client = get_api_client(client_name)
    return meta_client.get_ads_reach_mapping(date_preset, time_range)

@st.cache_data(ttl=900)
def fetch_instagram_paid_totals_cached(date_preset: str, time_range: dict | None, client_name: str) -> dict:
    meta_client = get_api_client(client_name)
    return meta_client.get_instagram_paid_totals(date_preset, time_range)

@st.cache_data(ttl=900)
def fetch_organic_v12(date_preset: str, time_range: dict | None, client_name: str) -> List[InstagramMedia]:
    ig_client = get_instagram_client(client_name)
    meta_client = get_api_client(client_name)
    
    if time_range:
        since_dt = datetime.datetime.strptime(time_range['since'], '%Y-%m-%d')
        until_dt = datetime.datetime.strptime(time_range['until'], '%Y-%m-%d') + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
        since_timestamp = int(since_dt.timestamp())
        until_timestamp = int(until_dt.timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=since_timestamp, until_timestamp=until_timestamp)
    elif date_preset == 'maximum':
        media_list = ig_client.get_recent_media(limit=100)
    else:
        thirty_days_ago = int((datetime.datetime.now() - datetime.timedelta(days=30)).timestamp())
        media_list = ig_client.get_recent_media(limit=100, since_timestamp=thirty_days_ago)
    
    ads_mapping = fetch_instagram_ads_mapping_cached(date_preset, time_range, client_name)
    
    
    updated_media_list = []
    for media in media_list:
        ig_id = media.id
        update_data = {}
        if ig_id in ads_mapping:
            metrics = ads_mapping[ig_id]
            
            update_data['paid_reach'] = metrics["reach"]
            update_data['paid_impressions'] = metrics["impressions"]
            update_data['paid_clicks'] = metrics["clicks"]
            update_data['paid_link_clicks'] = metrics["link_clicks"]
            update_data['paid_other_clicks'] = max(0, update_data['paid_clicks'] - update_data['paid_link_clicks'])
            update_data['paid_likes'] = metrics["likes"]
            update_data['paid_shares'] = metrics["shares"]
            update_data['paid_saved'] = metrics["saved"]
            update_data['paid_comments'] = metrics.get("comments", 0)
            update_data['paid_views'] = metrics["views"]
            update_data['paid_destination'] = metrics.get("paid_destination")
            update_data['paid_spend'] = metrics.get("spend", 0.0)
            update_data['paid_cpm'] = metrics.get("cpm", 0.0)
            update_data['paid_cpc'] = metrics.get("cpc", 0.0)
            update_data['paid_cpp'] = metrics.get("cpp", 0.0)
            update_data['paid_ctr'] = metrics.get("ctr", 0.0)
            update_data['paid_cpa'] = metrics.get("cpa", 0.0)
            update_data['paid_cost_per_outbound_click'] = metrics.get("cost_per_outbound_click", 0.0)
            update_data['paid_frequency'] = metrics.get("frequency", 0.0)
            update_data['paid_video_avg_time'] = metrics.get("video_avg_time", 0.0)
            update_data['paid_video_p25'] = metrics.get("video_p25", 0)
            update_data['paid_video_p50'] = metrics.get("video_p50", 0)
            update_data['paid_video_p75'] = metrics.get("video_p75", 0)
            update_data['paid_action_values'] = metrics.get("action_values", 0.0)
            update_data['paid_roas'] = metrics.get("roas", 0.0)
            update_data['paid_objective'] = metrics.get("objective", "")
            update_data['paid_optimization_goal'] = metrics.get("optimization_goal", "")
            update_data['paid_date_start'] = metrics.get("date_start", "")
            update_data['paid_date_stop'] = metrics.get("date_stop", "")
            
            if update_data['paid_impressions'] > 0:
                update_data['paid_ctr'] = (update_data['paid_clicks'] / update_data['paid_impressions']) * 100
                
            if update_data['paid_reach'] > 0:
                update_data['paid_frequency'] = update_data['paid_impressions'] / update_data['paid_reach']
                
            # A API Graph do Instagram (media/{id}/insights) já retorna APENAS o alcance orgânico
            # Métricas de anúncios NÃO estão inclusas nesse número, logo não devemos subtrair.
            update_data['organic_reach'] = media.reach
        else:
            update_data['organic_reach'] = media.reach
            
        updated_media_list.append(media.model_copy(update=update_data))
        
    return updated_media_list

@st.cache_data(ttl=900)
def fetch_active_stories(client_name: str) -> list:
    ig_client = get_instagram_client(client_name)
    return ig_client.get_active_stories()

@st.cache_data(ttl=86400)
def fetch_all_historic_comments(client_name: str) -> list:
    ig_client = get_instagram_client(client_name)
    all_media_ids = ig_client.get_all_media_ids_since_beginning()
    all_comments = ig_client.get_all_comments_for_account(all_media_ids)
    return all_comments

@st.cache_data(ttl=3600)
def fetch_account_demographics(client_name: str):
    ig_client = get_instagram_client(client_name)
    return ig_client.get_account_demographics()

@st.cache_data(ttl=3600)
def fetch_account_insights_cached(client_name: str, date_preset: str = "last_30d", time_range: dict | None = None) -> dict:
    ig_client = get_instagram_client(client_name)
    return ig_client.get_account_insights(date_preset, time_range)

@st.cache_data(ttl=3600)
def fetch_followers_history_cached(client_name: str) -> list:
    from datetime import datetime
    ig_client = get_instagram_client(client_name)
    raw_history = ig_client.get_followers_history()
    
    clean_history = []
    for item in raw_history:
        end_time_str = item.get("end_time")
        val = item.get("value", 0)
        if end_time_str:
            try:
                # '2026-07-04T07:00:00+0000'
                dt = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%S%z")
                clean_history.append({"Data": dt.strftime("%d/%m"), "Novos Seguidores": val})
            except Exception:
                pass
                
    return clean_history
