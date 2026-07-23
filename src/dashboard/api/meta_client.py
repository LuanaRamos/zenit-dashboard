import httpx
import logging
import asyncio
from typing import Optional, List, Dict, Any
from core.config import settings

# Logger oficial para ML/Production Workflow
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MetaAPIClient:
    """Cliente Assíncrono da Meta Graph API com Exponential Backoff."""
    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, access_token: str):
        self.access_token = access_token

    async def _request(self, method: str, endpoint: str, params: dict = None, retries: int = 3) -> Dict[str, Any]:
        """Faz a requisição HTTP com tratamento de Rate Limit (HTTP 429)."""
        if params is None:
            params = {}
        params['access_token'] = self.access_token

        url = f"{self.BASE_URL}/{endpoint}"
        
        async with httpx.AsyncClient(verify=False) as client:
            for attempt in range(retries):
                try:
                    response = await client.request(method, url, params=params)
                    
                    if response.status_code == 200:
                        return response.json()
                    
                    # Rate Limit Hit (Exponential Backoff)
                    if response.status_code == 429:
                        wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s...
                        logger.warning(f"[Rate Limit] Meta bloqueou. Aguardando {wait_time}s... (Tentativa {attempt+1})")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    # Outros Erros da Meta
                    logger.error(f"Erro na Meta API: {response.status_code} - {response.text}")
                    response.raise_for_status()

                except httpx.RequestError as exc:
                    logger.error(f"Erro de conexão com a Meta: {exc}")
                    if attempt == retries - 1:
                        raise

            raise Exception("Máximo de tentativas excedido (Rate Limit).")

    async def get_user_pages(self) -> List[Dict[str, Any]]:
        """Busca todas as páginas do Facebook que o usuário gerencia."""
        response = await self._request("GET", "me/accounts", params={"fields": "id,name,access_token"})
        return response.get("data", [])

    async def get_instagram_account(self, page_id: str, page_token: str) -> Optional[Dict[str, Any]]:
        """Busca a Conta Profissional do Instagram conectada à Página."""
        page_client = MetaAPIClient(access_token=page_token)
        response = await page_client._request(
            "GET", 
            page_id, 
            params={"fields": "instagram_business_account{id,username,profile_picture_url}"}
        )
        return response.get("instagram_business_account")

    async def get_instagram_details(self, ig_id: str) -> Dict[str, Any]:
        """Busca detalhes da conta do Instagram (seguidores, mídia, nome)."""
        return await self._request("GET", ig_id, params={
            "fields": "id,username,name,followers_count,follows_count,media_count,profile_picture_url"
        })

    async def get_instagram_insights(self, ig_id: str) -> Dict[str, Any]:
        """Busca métricas de alcance e impressões do Instagram."""
        return await self._request("GET", f"{ig_id}/insights", params={
            "metric": "impressions,reach,profile_views",
            "period": "day"
        })

    async def get_top_media(self, ig_id: str) -> List[Dict[str, Any]]:
        """Busca as publicações mais recentes do Instagram."""
        response = await self._request("GET", f"{ig_id}/media", params={
            "fields": "id,caption,media_type,like_count,comments_count,permalink,timestamp",
            "limit": 10
        })
        return response.get("data", [])

    async def get_ad_accounts(self) -> List[Dict[str, Any]]:
        """Busca as contas de anúncios (Meta Ads) do usuário."""
        response = await self._request("GET", "me/adaccounts", params={
            "fields": "id,name,account_status,currency"
        })
        return response.get("data", [])

    async def get_ad_account_insights(self, ad_account_id: str) -> List[Dict[str, Any]]:
        """Busca dados de desempenho das campanhas pagas."""
        response = await self._request("GET", f"{ad_account_id}/insights", params={
            "date_preset": "last_30d",
            "fields": "spend,impressions,clicks,cpc,cpm,actions"
        })
        return response.get("data", [])
