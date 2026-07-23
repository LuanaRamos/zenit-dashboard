import requests
import logging
from typing import List
from core.config import settings
from schemas.meta import CampaignInsight

logger = logging.getLogger(__name__)

class MetaAPIError(Exception):
    """Exceção customizada para erros da API da Meta."""
    pass

class MetaAdsClient:
    """
    Cliente para comunicação direta com a Graph API da Meta.
    Responsável por fazer o fetch de insights das campanhas e páginas.
    """
    BASE_URL = "https://graph.facebook.com/v20.0"

    def __init__(self):
        self.token = settings.meta_master_token
        self.ad_account_id = settings.ad_account_id
        self.page_id = settings.page_id

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Método base para fazer requisições à Graph API.
        Trata erros e token expirado de forma robusta.
        """
        if params is None:
            params = {}
        
        params["access_token"] = self.token
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json() if e.response else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            
            logger.error(f"Erro na API da Meta: {error_msg}")
            
            if "Session has expired" in error_msg or "Error validating access token" in error_msg:
                raise MetaAPIError("O seu Token expirou ou é inválido. Por favor, gere um novo no portal de desenvolvedores e atualize o arquivo .env.")
            
            raise MetaAPIError(f"Erro ao consultar o Meta Ads: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar a Meta: {e}")
            raise MetaAPIError("Não foi possível conectar aos servidores da Meta. Verifique sua conexão.")

    def get_campaign_insights(self) -> List[CampaignInsight]:
        """
        Busca os insights a nível de campanha dos últimos 30 dias.
        """
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "campaign",
            "fields": "campaign_name,campaign_id,spend,impressions,clicks,cpc,cpm,actions",
            "date_preset": "last_30d"
        }

        data = self._make_request(endpoint, params)
        insights_data = data.get("data", [])
        
        insights = []
        for item in insights_data:
            insights.append(CampaignInsight.from_api_response(item))
            
        return insights