import streamlit as st
from typing import List
from api.meta_client import MetaAdsClient
from api.instagram_client import InstagramClient
from schemas.meta import CampaignInsight, PageInsight
from schemas.instagram import InstagramMedia
import datetime

@st.cache_resource
def get_api_client() -> MetaAdsClient:
    return MetaAdsClient()

@st.cache_data(ttl=86400)
def get_account_creation_date_cached() -> datetime.date:
    client = get_api_client()
    return client.get_account_created_time()

@st.cache_resource
def get_instagram_client() -> InstagramClient:
    return InstagramClient()

@st.cache_data(ttl=3600)
def fetch_campaigns_v8(date_preset: str, time_range: dict = None) -> List[CampaignInsight]:
    client = get_api_client()
    return client.get_campaign_insights(date_preset=date_preset, time_range=time_range)

@st.cache_data(ttl=3600)
def load_page_data() -> PageInsight:
    return PageInsight(followers=1250, reach=8450, engagement=340)

@st.cache_data(ttl=3600)
def fetch_organic_leads_cached(date_preset: str, time_range: dict = None) -> int:
    client = get_api_client()
    return client.get_total_organic_leads(date_preset, time_range)

@st.cache_data(ttl=900)
def fetch_organic_v12(date_preset: str, time_range: dict = None) -> List[InstagramMedia]:
    ig_client = get_instagram_client()
    meta_client = get_api_client()
    
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
    
    ads_mapping = meta_client.get_ads_reach_mapping(date_preset, time_range)
    
    updated_media_list = []
    for media in media_list:
        ig_id = media.id
        update_data = {}
        if ig_id in ads_mapping:
            metrics = ads_mapping[ig_id]
            
            update_data['paid_reach'] = metrics['reach']
            update_data['paid_impressions'] = metrics['impressions']
            update_data['paid_clicks'] = metrics['clicks']
            update_data['paid_likes'] = metrics['likes']
            update_data['paid_shares'] = metrics.get('shares', 0)
            update_data['paid_saved'] = metrics.get('saved', 0)
            
            if update_data['paid_impressions'] > 0:
                update_data['paid_ctr'] = (update_data['paid_clicks'] / update_data['paid_impressions']) * 100
                
            if update_data['paid_reach'] > 0:
                update_data['paid_frequency'] = update_data['paid_impressions'] / update_data['paid_reach']
                
            organic_likes = max(0, media.like_count - update_data['paid_likes'])
            if media.like_count > 0 and update_data['paid_likes'] > 0 and organic_likes > 0:
                organic_ratio = organic_likes / media.like_count
                update_data['organic_reach'] = int(media.reach * organic_ratio)
            else:
                update_data['organic_reach'] = max(0, media.reach - update_data['paid_reach'])
        else:
            update_data['organic_reach'] = media.reach
            
        updated_media_list.append(media.model_copy(update=update_data))
        
    return updated_media_list

@st.cache_data(ttl=900)
def fetch_active_stories() -> list:
    ig_client = get_instagram_client()
    return ig_client.get_active_stories()

@st.cache_data(ttl=86400)
def fetch_best_historic_comment() -> dict:
    ig_client = get_instagram_client()
    all_media_ids = ig_client.get_all_media_ids_since_beginning()
    best_comment = ig_client.get_top_comment_for_account(all_media_ids)
    return best_comment or {}

@st.cache_data(ttl=3600)
def fetch_account_demographics():
    ig_client = get_instagram_client()
    return ig_client.get_account_demographics()
