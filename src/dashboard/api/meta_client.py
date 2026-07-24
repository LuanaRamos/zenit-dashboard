import requests
import logging
from typing import List, Dict, Any
from core.config import settings
from schemas.meta import CampaignInsight
from api.exceptions import MetaAPIError

logger = logging.getLogger(__name__)

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

    def get_campaign_insights(self, date_preset: str = "last_30d") -> List[CampaignInsight]:
        """
        Busca os insights a nível de campanha com base no período selecionado.
        Inclui o objetivo da campanha para renderização dinâmica (ODAX).
        """
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "campaign",
            "fields": "campaign_name,campaign_id,objective,spend,impressions,clicks,cpc,cpm,actions",
            "date_preset": date_preset
        }

        data = self._make_request(endpoint, params)
        insights_data = data.get("data", [])
        
        insights = []
        for item in insights_data:
            insights.append(CampaignInsight.from_api_response(item))
            
        return insights

    def get_ads_reach_mapping(self) -> Dict[str, Dict[str, int]]:
        """
        Busca insights de todos os anúncios e agrupa pelo ID do post do Instagram
        para cálculo do tráfego pago vs orgânico. Alta performance: Sem N+1 queries.
        
        Returns:
            Dict[str, Dict[str, int]]: Mapa com a chave sendo o 'effective_instagram_story_id' e o 
                                       valor sendo a soma de reach, impressions e clicks.
        """
        # Passo 1: Buscar insights de todos os ads na conta de uma vez (evita bater na API 50 vezes)
        insights_endpoint = f"{self.ad_account_id}/insights"
        insights_params = {
            "level": "ad",
            "fields": "ad_id,reach,impressions,clicks,actions",
            "date_preset": "maximum",
            "limit": "1000"
        }
        
        # Usamos uma lista para pegar todos os dados caso tenha paginação (aqui focamos nos primeiros 1000 ads)
        try:
            insights_data = self._make_request(insights_endpoint, insights_params).get("data", [])
        except MetaAPIError as e:
            logger.warning(f"Erro ao buscar insights de anúncios (Organic mapping): {e}")
            return {}

        # Mapeia ad_id -> métricas
        ad_metrics_map = {}
        for item in insights_data:
            ad_id = item.get("ad_id")
            if ad_id:
                ad_metrics_map[ad_id] = {
                    "reach": int(item.get("reach", 0)),
                    "impressions": int(item.get("impressions", 0)),
                    "clicks": int(item.get("clicks", 0)),
                    "likes": 0
                }
                
                # Procura interações pagas (curtidas feitas no dark post)
                for action in item.get("actions", []):
                    if action.get("action_type") in ["post_reaction", "onsite_conversion.post_net_like"]:
                        ad_metrics_map[ad_id]["likes"] = max(ad_metrics_map[ad_id]["likes"], int(action.get("value", 0)))
                
        # Passo 2: Buscar a ligação entre o Ad e o Instagram Post (Feed, Reels, Stories)
        ads_endpoint = f"{self.ad_account_id}/ads"
        ads_params = {
            "fields": "id,creative{effective_instagram_story_id,effective_instagram_media_id,source_instagram_media_id}",
            "limit": "1000"
        }
        
        try:
            ads_data = self._make_request(ads_endpoint, ads_params).get("data", [])
        except MetaAPIError as e:
            logger.warning(f"Erro ao buscar lista de anúncios (Organic mapping): {e}")
            return {}
            
        # Passo 3: Agrupar as métricas baseadas no Instagram Post ID
        ig_mapping = {}
        for ad in ads_data:
            ad_id = ad.get("id")
            creative = ad.get("creative", {})
            
            # 1. source_instagram_media_id = Post original que deu origem ao anúncio (prioridade máxima)
            # 2. effective_instagram_media_id = Feed, Reels, Carousel (Ads nativos)
            # 3. effective_instagram_story_id = Stories
            ig_id = creative.get("source_instagram_media_id") or creative.get("effective_instagram_media_id") or creative.get("effective_instagram_story_id")
            
            # Se esse anúncio está atrelado a um post do IG e possui métricas registradas
            if ig_id and ad_id in ad_metrics_map:
                metrics = ad_metrics_map[ad_id]
                
                if ig_id not in ig_mapping:
                    ig_mapping[ig_id] = {"reach": 0, "impressions": 0, "clicks": 0, "likes": 0}
                    
                ig_mapping[ig_id]["reach"] += metrics["reach"]
                ig_mapping[ig_id]["impressions"] += metrics["impressions"]
                ig_mapping[ig_id]["clicks"] += metrics["clicks"]
                ig_mapping[ig_id]["likes"] += metrics["likes"]
                
        return ig_mapping
