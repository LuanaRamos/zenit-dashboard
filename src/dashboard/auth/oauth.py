import streamlit as st
import urllib.parse
from core.config import settings
import httpx

def get_login_url() -> str:
    """Gera a URL oficial de Login do Facebook."""
    # Permissões necessárias (Scopes)
    scopes = [
        "public_profile",
        "email",
        "pages_show_list",
        "pages_read_engagement",
        "instagram_basic",
        "instagram_manage_insights"
    ]
    
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "state": "zenit_auth_state",
        "scope": ",".join(scopes),
        "response_type": "code",
        "auth_type": "rerequest"
    }
    
    query_string = urllib.parse.urlencode(params)
    return f"https://www.facebook.com/v19.0/dialog/oauth?{query_string}"

async def exchange_code_for_token(code: str) -> str:
    """Troca o código temporário por um Access Token oficial da Meta."""
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "redirect_uri": settings.META_REDIRECT_URI,
        "code": code
    }
    
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data["access_token"]
