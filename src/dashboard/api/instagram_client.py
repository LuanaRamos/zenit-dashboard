import json
import logging
import sentry_sdk

from typing import Any
import requests
from api.exceptions import InstagramAPIError
from core.config import settings
from schemas.instagram import InstagramMedia, InstagramStory

logger = logging.getLogger(__name__)


class InstagramClient:
    """
    Cliente para comunicação direta com a Graph API do Instagram.
    Responsável por fazer o fetch de publicações orgânicas e seus insights.
    """

    # URL base para requests normais (versionada)
    BASE_URL = "https://graph.facebook.com/v22.0"
    # URL para Batch Requests (SEM versão — exigência da Graph API)
    BATCH_URL = "https://graph.facebook.com"

    def __init__(self) -> None:
        self.token = settings.meta_master_token.get_secret_value()
        self.page_id = settings.page_id
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.instagram_account_id = self._fetch_instagram_account_id()

    def _fetch_instagram_account_id(self) -> str:
        """Busca o ID do Instagram vinculado à página dinamicamente."""
        url = f"{self.BASE_URL}/{self.page_id}"
        params = {
            "fields": "instagram_business_account"
        }
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "instagram_business_account" in data:
                return str(data["instagram_business_account"]["id"])
            else:
                logger.error(f"Nenhum Instagram vinculado à Página {self.page_id}.")
                raise InstagramAPIError("Nenhum Instagram Comercial vinculado à Página do Facebook. Verifique as configurações na Meta.")
        except Exception as e:
            if isinstance(e, InstagramAPIError):
                raise
            logger.error(f"Erro ao buscar instagram_business_account: {e}")
            sentry_sdk.capture_exception(e)
            raise InstagramAPIError("Falha de conexão ao tentar validar o Instagram vinculado à conta.")

    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Método base para fazer requisições GET simples à Graph API.
        Trata erros e early returns.
        """
        if params is None:
            params = {}

        url = f"{self.BASE_URL}/{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()  # type: ignore
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json() if e.response else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            logger.error(f"Erro na API do Instagram: {error_msg}")

            if (
                "Session has expired" in error_msg
                or "Error validating access token" in error_msg
            ):
                raise InstagramAPIError(
                    "O seu Token de Acesso expirou ou é inválido. Atualize o .env com um novo token."
                )

            raise InstagramAPIError(f"Erro ao consultar o Instagram: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar o Instagram: {e}")
            raise InstagramAPIError(
                "Não foi possível conectar aos servidores do Instagram. Verifique sua conexão."
            )

    def get_recent_media(  # noqa: C901
        self,
        limit: int = 50,
        since_timestamp: int | None = None,
        until_timestamp: int | None = None,
    ) -> list[InstagramMedia]:  # noqa: C901  # noqa: C901
        """
        Busca publicações recentes e seus insights via Batch Operations (alta performance).
        """
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            "fields": "id,caption,media_url,permalink,timestamp,like_count,comments_count,media_type,media_product_type",
            "limit": str(limit),
        }

        if since_timestamp:
            params["since"] = str(since_timestamp)

        if until_timestamp:
            params["until"] = str(until_timestamp)

        media_items_data = []
        max_pages = 5
        current_page = 0

        while current_page < max_pages:
            try:
                data = self._make_request(endpoint, params)
                page_data = data.get("data", [])
                if not page_data:
                    break

                media_items_data.extend(page_data)

                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break

                current_page += 1
            except Exception as e:
                logger.warning(f"Erro durante a paginação do Instagram: {e}")
                sentry_sdk.capture_exception(e)
                break

        # Batch Request para puxar Insights sem N+1 queries (Regra da skill Caching Expert)
        insights_map = {}
        batch_requests = []
        for item in media_items_data:
            ig_id = item.get("id")
            media_product_type = item.get("media_product_type", "")
            if media_product_type == "REELS":
                # Metricas validas para Reels na v22.0
                # 'plays' foi depreciado — use ig_reels_video_view_total_time
                metrics = "reach,saved,shares,total_interactions,ig_reels_video_view_total_time,ig_reels_avg_watch_time"
            else:
                metrics = "reach,saved,shares,profile_activity,profile_visits,follows"

            batch_requests.append(
                {
                    "method": "GET",
                    # Barra inicial obrigatória na relative_url do Batch API
                    "relative_url": f"/{ig_id}/insights?metric={metrics}",
                }
            )

        for i in range(0, len(batch_requests), 50):
            chunk = batch_requests[i : i + 50]
            try:
                batch_res = self.session.post(
                    self.BATCH_URL,  # Batch API não usa versão na URL base
                    data={"access_token": self.token, "batch": json.dumps(chunk)},
                    timeout=20,
                )
                batch_res.raise_for_status()
                for j, response_item in enumerate(batch_res.json()):
                    if response_item.get("code") == 200:
                        body = json.loads(response_item.get("body", "{}"))
                        req_idx = i + j
                        ig_id = media_items_data[req_idx]["id"]
                        insights_map[ig_id] = body.get("data", [])
            except Exception as e:
                logger.error(f"Erro no Batch de Insights: {e}")
                sentry_sdk.capture_exception(e)

        media_list = []
        for item in media_items_data:
            ig_id = item.get("id")
            insights_data = insights_map.get(ig_id, [])

            metrics_dict = {}
            for insight in insights_data:
                name = insight.get("name")
                values = insight.get("values", [])
                if values:
                    metrics_dict[name] = values[0].get("value", 0)

            try:
                media = InstagramMedia(
                    id=ig_id,
                    caption=item.get("caption", ""),
                    media_url=item.get("media_url"),
                    media_type=item.get("media_type", ""),
                    media_product_type=item.get("media_product_type", ""),
                    permalink=item.get("permalink", ""),
                    timestamp=item.get("timestamp", ""),
                    like_count=int(item.get("like_count", 0)),
                    comments_count=int(item.get("comments_count", 0)),
                    reach=int(metrics_dict.get("reach", 0)),
                    shares=int(metrics_dict.get("shares", 0)),
                    saved=int(metrics_dict.get("saved", 0)),
                    ig_reels_video_view_total_time=float(
                        metrics_dict.get("ig_reels_video_view_total_time", 0)
                    ),
                    ig_reels_avg_watch_time=float(
                        metrics_dict.get("ig_reels_avg_watch_time", 0)
                    ),
                    profile_activity=int(metrics_dict.get("profile_activity", 0)),
                    profile_visits=int(metrics_dict.get("profile_visits", 0)),
                    follows=int(metrics_dict.get("follows", 0)),
                )
                media_list.append(media)
            except Exception as e:
                logger.warning(f"Erro ao parsear a mídia do Instagram {ig_id}: {e}")

        return media_list

    def get_active_stories(self) -> list[InstagramStory]:  # noqa: C901
        """
        Busca os stories ativos (últimas 24h) e seus insights de retenção via Batch.
        """
        endpoint = f"{self.instagram_account_id}/stories"
        params = {"fields": "id,caption,media_url,permalink,timestamp"}

        try:
            data = self._make_request(endpoint, params)
            stories_data = data.get("data", [])
        except Exception as e:
            logger.error(f"Erro ao buscar stories: {e}")
            return []

        if not stories_data:
            return []

        batch_requests = []
        for item in stories_data:
            ig_id = item.get("id")
            metrics = "reach,exits,replies,taps_forward,taps_back"
            batch_requests.append(
                {"method": "GET", "relative_url": f"/{ig_id}/insights?metric={metrics}"}
            )

        insights_map = {}
        for i in range(0, len(batch_requests), 50):
            chunk = batch_requests[i : i + 50]
            try:
                batch_res = self.session.post(
                    self.BATCH_URL,  # Batch API não usa versão na URL base
                    data={"access_token": self.token, "batch": json.dumps(chunk)},
                    timeout=20,
                )
                batch_res.raise_for_status()
                for j, response_item in enumerate(batch_res.json()):
                    if response_item.get("code") == 200:
                        body = json.loads(response_item.get("body", "{}"))
                        req_idx = i + j
                        ig_id = stories_data[req_idx]["id"]
                        insights_map[ig_id] = body.get("data", [])
            except Exception as e:
                logger.error(f"Erro no Batch de Insights de Stories: {e}")
                sentry_sdk.capture_exception(e)

        stories_list = []
        for item in stories_data:
            ig_id = item.get("id")
            insights_data = insights_map.get(ig_id, [])

            metrics_dict = {}
            for insight in insights_data:
                name = insight.get("name")
                values = insight.get("values", [])
                if values:
                    metrics_dict[name] = values[0].get("value", 0)

            stories_list.append(
                InstagramStory(
                    id=ig_id,
                    caption=item.get("caption", ""),
                    media_url=item.get("media_url"),
                    permalink=item.get("permalink", ""),
                    timestamp=item.get("timestamp", ""),
                    reach=int(metrics_dict.get("reach", 0)),
                    exits=int(metrics_dict.get("exits", 0)),
                    replies=int(metrics_dict.get("replies", 0)),
                    taps_forward=int(metrics_dict.get("taps_forward", 0)),
                    taps_back=int(metrics_dict.get("taps_back", 0)),
                )
            )

        return stories_list

    def get_account_insights(self) -> dict[str, int]:
        """
        Busca insights a nível de conta (Últimos 28 dias).
        Métricas de cliques (website_clicks, email_contacts) foram depreciadas na API oficial,
        mas mantemos a estrutura para puxar as visualizações de perfil reais.
        """
        import datetime
        until = datetime.datetime.now()
        since = until - datetime.timedelta(days=28)
        
        # profile_views foi restaurada na v19.0 para nível de conta (period=day)
        endpoint = f"{self.instagram_account_id}/insights"
        params = {
            "metric": "profile_views,website_clicks,profile_links_taps",
            "metric_type": "total_value",
            "period": "day",
            "since": str(int(since.timestamp())),
            "until": str(int(until.timestamp()))
        }
        
        results = {"profile_views": 0, "website_clicks": 0, "profile_links_taps": 0}
        
        try:
            data = self._make_request(endpoint, params)
            insights = data.get("data", [])
            for insight in insights:
                name = insight.get("name")
                total = insight.get("total_value", {}).get("value", 0)
                results[name] = total
        except Exception as e:
            logger.warning(f"Erro ao buscar account insights: {e}")
            
        return results

    def get_total_media_count(self) -> int:
        """Busca o número total de posts publicados pela conta"""
        try:
            params = {"fields": "media_count"}
            data = self._make_request(f"{self.instagram_account_id}", params)
            return int(data.get("media_count", 0))
        except Exception as e:
            logger.warning(f"Erro ao contar media: {e}")
            return 0

    def get_all_media_ids_since_beginning(self) -> list[str]:
        """Busca TODOS os IDs de mídia desde o início da conta, lidando com paginação ilimitada."""
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            "fields": "id",
            "limit": "100",
        }
        media_ids = []
        try:
            while True:
                data = self._make_request(endpoint, params)
                page_data = data.get("data", [])
                if not page_data:
                    break
                media_ids.extend([item["id"] for item in page_data])
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.warning(f"Erro ao buscar all_media_ids: {e}")
        return media_ids

    def get_top_comment_for_account(self, media_ids: list[str]) -> dict[str, Any] | None:
        """Busca o comentário mais curtido dado uma lista de media_ids (Sem limite, usa chunks de 50 no Batch)"""
        if not media_ids: return None
        best_comment = None
        max_likes = -1
        
        batch_requests = []
        for ig_id in media_ids:
            batch_requests.append(
                {"method": "GET", "relative_url": f"/{ig_id}/comments?fields=id,text,like_count,username,timestamp&limit=50"}
            )
        
        try:
            for i in range(0, len(batch_requests), 50):
                chunk = batch_requests[i:i + 50]
                batch_res = self.session.post(
                    self.BATCH_URL,
                    data={"access_token": self.token, "batch": json.dumps(chunk)},
                    timeout=20,
                )
                batch_res.raise_for_status()
                for response_item in batch_res.json():
                    if response_item.get("code") == 200:
                        body = json.loads(response_item.get("body", "{}"))
                        comments = body.get("data", [])
                        for c in comments:
                            likes = int(c.get("like_count", 0))
                            if likes > max_likes:
                                max_likes = likes
                                best_comment = c
        except Exception as e:
            logger.error(f"Erro ao buscar top comment: {e}")
            sentry_sdk.capture_exception(e)
            
        return best_comment
