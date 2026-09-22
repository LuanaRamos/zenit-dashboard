import datetime
import logging
from typing import List

import streamlit as st
from api.instagram_client import InstagramClient
from api.meta_client import MetaAdsClient
from core.config import settings
from schemas.instagram import InstagramMedia
from schemas.meta import CampaignInsight, PageInsight

logger = logging.getLogger(__name__)


@st.cache_resource
def get_api_client(client_name: str) -> MetaAdsClient:
    clients = settings.get_clients()
    _cache_buster = 3
    client_config = next(c for c in clients if c.name == client_name)
    return MetaAdsClient(client_config)


@st.cache_data(ttl=86400)
def get_account_creation_date_cached(client_name: str) -> datetime.date:
    client = get_api_client(client_name)
    return client.get_account_created_time()


@st.cache_resource
def get_instagram_client(client_name: str) -> InstagramClient:
    clients = settings.get_clients()
    _cache_buster = 3
    client_config = next(c for c in clients if c.name == client_name)
    return InstagramClient(client_config)


@st.cache_data(ttl=3600)
def fetch_campaigns_v8(
    date_preset: str, time_range: dict | None, client_name: str
) -> List[CampaignInsight]:
    client = get_api_client(client_name)
    return client.get_campaign_insights(date_preset=date_preset, time_range=time_range)


@st.cache_data(ttl=3600)
def load_page_data(client_name: str) -> PageInsight:
    return PageInsight(followers=1250, reach=8450, engagement=340)


@st.cache_data(ttl=3600)
def fetch_organic_leads_cached(
    date_preset: str, time_range: dict | None, client_name: str
) -> int:
    client = get_api_client(client_name)
    return client.get_total_organic_leads(date_preset, time_range)


@st.cache_data(ttl=900)
def fetch_instagram_ads_mapping_cached(
    date_preset: str, time_range: dict | None, client_name: str
) -> dict:
    meta_client = get_api_client(client_name)
    return meta_client.get_ads_reach_mapping(date_preset, time_range)


@st.cache_data(ttl=900)
def fetch_instagram_paid_totals_cached(
    date_preset: str, time_range: dict | None, client_name: str
) -> dict:
    meta_client = get_api_client(client_name)
    return meta_client.get_instagram_paid_totals(date_preset, time_range)


@st.cache_data(ttl=3600)
def fetch_account_profile_cached(client_name: str) -> dict:
    """Busca informações de perfil do Instagram (avatar, bio, contadores) com cache de 1 hora."""
    try:
        ig_client = get_instagram_client(client_name)
        profile = ig_client.get_account_profile_info()
        if not profile or not isinstance(profile, dict):
            return {
                "id": "",
                "username": client_name.lower().replace(" ", "_"),
                "name": client_name,
                "biography": "",
                "profile_picture_url": "",
                "followers_count": 0,
                "follows_count": 0,
                "media_count": 0,
            }
        return profile
    except Exception as e:
        logger.warning(f"Erro ao carregar perfil em cache para {client_name}: {e}")
        return {
            "id": "",
            "username": client_name.lower().replace(" ", "_"),
            "name": client_name,
            "biography": "",
            "profile_picture_url": "",
            "followers_count": 0,
            "follows_count": 0,
            "media_count": 0,
        }


@st.cache_data(ttl=900)
def fetch_organic_media(
    date_preset: str, time_range: dict | None, client_name: str
) -> List[InstagramMedia]:
    """Fetch Media Insights without constructing or querying a paid Ads client."""
    ig_client = get_instagram_client(client_name)

    if time_range:
        since_dt = datetime.datetime.strptime(time_range["since"], "%Y-%m-%d")
        until_dt = (
            datetime.datetime.strptime(time_range["until"], "%Y-%m-%d")
            + datetime.timedelta(days=1)
            - datetime.timedelta(seconds=1)
        )
        since_timestamp = int(since_dt.timestamp())
        until_timestamp = int(until_dt.timestamp())
        return ig_client.get_recent_media(
            limit=100,
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
        )
    elif date_preset == "maximum":
        return ig_client.get_recent_media(limit=100)

    days = 90 if date_preset == "last_90d" else 30
    since_timestamp = int(
        (datetime.datetime.now() - datetime.timedelta(days=days)).timestamp()
    )
    return ig_client.get_recent_media(limit=100, since_timestamp=since_timestamp)


@st.cache_data(ttl=900)
def enrich_media_with_ads(
    media_list: List[InstagramMedia],
    date_preset: str,
    time_range: dict | None,
    client_name: str,
) -> List[InstagramMedia]:
    """Attach a separate paid comparison to already-fetched organic media."""
    ads_mapping = fetch_instagram_ads_mapping_cached(
        date_preset, time_range, client_name
    )

    updated_media_list = []
    for media in media_list:
        ig_id = media.id
        update_data = {}
        if ig_id in ads_mapping:
            metrics = ads_mapping[ig_id]

            update_data["paid_reach"] = metrics.get("reach", 0)
            update_data["paid_impressions"] = metrics.get("impressions", 0)
            update_data["paid_clicks"] = metrics.get("clicks", 0)
            update_data["paid_link_clicks"] = metrics.get("link_clicks", 0)
            update_data["paid_other_clicks"] = max(
                0, update_data["paid_clicks"] - update_data["paid_link_clicks"]
            )
            update_data["paid_likes"] = metrics.get("likes")
            update_data["paid_reactions"] = metrics.get("reactions")
            update_data["paid_shares"] = metrics.get("shares", 0)
            update_data["paid_saved"] = metrics.get("saved", 0)
            update_data["paid_comments"] = metrics.get("comments", 0)
            update_data["paid_views"] = metrics.get("views", 0)
            update_data["paid_destination"] = metrics.get("paid_destination")
            update_data["paid_spend"] = metrics.get("spend", 0.0)
            update_data["paid_cpm"] = metrics.get("cpm", 0.0)
            update_data["paid_cpc"] = metrics.get("cpc", 0.0)
            update_data["paid_cpp"] = metrics.get("cpp", 0.0)
            update_data["paid_ctr"] = metrics.get("ctr", 0.0)
            update_data["paid_cpa"] = metrics.get("cpa")
            update_data["paid_cost_per_outbound_click"] = metrics.get(
                "cost_per_outbound_click", 0.0
            )
            update_data["paid_frequency"] = metrics.get("frequency", 0.0)
            update_data["paid_video_avg_time"] = metrics.get("video_avg_time", 0.0)
            update_data["paid_video_p25"] = metrics.get("video_p25", 0)
            update_data["paid_video_p50"] = metrics.get("video_p50", 0)
            update_data["paid_video_p75"] = metrics.get("video_p75", 0)
            update_data["paid_action_values"] = metrics.get("action_values", 0.0)
            update_data["paid_roas"] = metrics.get("roas", 0.0)
            update_data["paid_objective"] = metrics.get("objective", "")
            update_data["paid_optimization_goal"] = metrics.get(
                "optimization_goal", ""
            )
            update_data["paid_date_start"] = metrics.get("date_start", "")
            update_data["paid_date_stop"] = metrics.get("date_stop", "")
            update_data["paid_ad_count"] = metrics.get("ad_count", 1)

        updated_media_list.append(media.model_copy(update=update_data))

    return updated_media_list


@st.cache_data(ttl=900)
def fetch_organic_v12(
    date_preset: str, time_range: dict | None, client_name: str
) -> List[InstagramMedia]:
    """Compatibility wrapper for callers that still use the old function name."""
    return fetch_organic_media(date_preset, time_range, client_name)


@st.cache_data(ttl=900)
def fetch_active_stories(client_name: str) -> list:
    ig_client = get_instagram_client(client_name)
    return ig_client.get_active_stories()


@st.cache_data(ttl=1800)
def fetch_recent_comments_cached(
    client_name: str, media_ids: tuple[str, ...]
) -> list:
    """Busca comentários das mídias passadas com cache de 30 minutos."""
    if not media_ids:
        return []
    try:
        ig_client = get_instagram_client(client_name)
        return ig_client.get_comments_for_media(list(media_ids))
    except Exception as e:
        logger.warning(
            f"Erro ao buscar comentários em cache para {client_name}: {e}"
        )
        return []


@st.cache_data(ttl=3600)
def fetch_all_historic_comments(
    client_name: str, media_ids: list[str] | None = None
) -> list:
    """
    Busca comentários para o cliente. Se media_ids não for fornecido,
    busca comentários dos posts mais recentes (sem paginação ilimitada que travava o dashboard).
    """
    try:
        ig_client = get_instagram_client(client_name)
        if media_ids is None:
            if hasattr(ig_client, "get_all_media_ids_since_beginning"):
                media_ids = ig_client.get_all_media_ids_since_beginning()[:30]
            else:
                media_ids = []
        if hasattr(ig_client, "get_all_comments_for_account"):
            return ig_client.get_all_comments_for_account(media_ids)
        return ig_client.get_comments_for_media(media_ids)
    except Exception as e:
        logger.warning(
            f"Erro ao buscar comentários históricos de {client_name}: {e}"
        )
        return []


@st.cache_data(ttl=3600)
def fetch_account_demographics(client_name: str):
    try:
        ig_client = get_instagram_client(client_name)
        return ig_client.get_account_demographics()
    except Exception as e:
        logger.warning(f"Erro ao buscar dados demográficos de {client_name}: {e}")
        return None


@st.cache_data(ttl=3600)
def fetch_account_insights_cached(
    client_name: str,
    date_preset: str = "last_30d",
    time_range: dict | None = None,
) -> dict:
    try:
        ig_client = get_instagram_client(client_name)
        return ig_client.get_account_insights(date_preset, time_range)
    except Exception as e:
        logger.warning(f"Erro ao buscar insights de conta de {client_name}: {e}")
        return {}


@st.cache_data(ttl=3600)
def fetch_followers_history_cached(client_name: str) -> list:
    try:
        from datetime import datetime

        ig_client = get_instagram_client(client_name)
        raw_history = ig_client.get_followers_history()

        clean_history = []
        for item in raw_history:
            end_time_str = item.get("end_time")
            val = item.get("value", 0)
            if end_time_str:
                try:
                    dt = datetime.strptime(end_time_str, "%Y-%m-%dT%H:%M:%S%z")
                    clean_history.append(
                        {"Data": dt.strftime("%d/%m"), "Novos Seguidores": val}
                    )
                except Exception:
                    pass

        return clean_history
    except Exception as e:
        logger.warning(f"Erro ao carregar histórico de seguidores de {client_name}: {e}")
        return []
