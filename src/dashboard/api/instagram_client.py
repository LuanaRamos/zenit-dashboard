import requests
import logging
from typing import List
from core.config import settings
from schemas.instagram import InstagramMedia
from api.exceptions import InstagramAPIError

logger = logging.getLogger(__name__)

class InstagramClient:
    """
    Cliente para comunicação direta com a Graph API do Instagram.
    Responsável por fazer o fetch de publicações orgânicas e seus insights.
    """
    BASE_URL = "https://graph.facebook.com/v20.0"

    def __init__(self):
        self.token = settings.meta_master_token
        # O ID do Instagram é vinculado à página (obtido anteriormente na auditoria)
        # Em um app complexo isso viria do banco, mas aqui estamos usando direto o da MS Consultoria.
        self.instagram_account_id = "17841449425333311"

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Método base para fazer requisições à Graph API.
        Trata erros e early returns.
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
            logger.error(f"Erro na API do Instagram: {error_msg}")
            
            if "Session has expired" in error_msg or "Error validating access token" in error_msg:
                raise InstagramAPIError("O seu Token de Acesso expirou ou é inválido. Atualize o .env com um novo token.")
            
            raise InstagramAPIError(f"Erro ao consultar o Instagram: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar o Instagram: {e}")
            raise InstagramAPIError("Não foi possível conectar aos servidores do Instagram. Verifique sua conexão.")

    def get_recent_media(self, limit: int = 50) -> List[InstagramMedia]:
        """
        Busca as publicações recentes da conta do Instagram e seus insights agregados.
        
        Args:
            limit (int): Número máximo de posts a retornar.
            
        Returns:
            List[InstagramMedia]: Lista com as publicações parseadas e tipadas rigorosamente.
        """
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            "fields": "id,caption,media_url,permalink,timestamp,like_count,comments_count,insights.metric(reach)",
            "limit": str(limit)
        }

        data = self._make_request(endpoint, params)
        media_items_data = data.get("data", [])
        
        media_list = []
        for item in media_items_data:
            # Tratamento de segurança para insights que podem vir vazios (ex: Collabs ou Reels não suportados)
            reach_value = 0
            insights_data = item.get("insights", {}).get("data", [])
            
            for insight in insights_data:
                if insight.get("name") == "reach":
                    # Os valores vêm dentro do array 'values'
                    values = insight.get("values", [])
                    if values:
                        reach_value = int(values[0].get("value", 0))
                        
            # Construir o modelo Pydantic rigoroso
            try:
                media = InstagramMedia(
                    id=item.get("id"),
                    caption=item.get("caption", ""),
                    media_url=item.get("media_url"),
                    permalink=item.get("permalink", ""),
                    timestamp=item.get("timestamp", ""),
                    like_count=int(item.get("like_count", 0)),
                    comments_count=int(item.get("comments_count", 0)),
                    reach=reach_value
                )
                media_list.append(media)
            except Exception as e:
                logger.warning(f"Erro ao parsear a mídia do Instagram {item.get('id')}: {e}")
                
        return media_list