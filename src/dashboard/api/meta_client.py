import datetime
import json
import logging
import sentry_sdk

from typing import Any
import requests
from api.exceptions import MetaAPIError
from core.config import settings
from schemas.meta import CampaignInsight

logger = logging.getLogger(__name__)

class MetaAdsClient:
    """
    Cliente para comunicação direta com a Graph API da Meta.
    Responsável por fazer o fetch de insights das campanhas e páginas.
    """

    BASE_URL = "https://graph.facebook.com/v22.0"

    def __init__(self) -> None:
        self.token = settings.meta_master_token.get_secret_value()
        self.ad_account_id = settings.ad_account_id
        self.page_id = settings.page_id
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Método base para fazer requisições à Graph API.
        Trata erros e token expirado de forma robusta.
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

            logger.error(f"Erro na API da Meta: {error_msg}")

            if (
                "Session has expired"
                or "Error validating access token" in error_msg
            ):
                raise MetaAPIError(
                    "O seu Token expirou ou é inválido. Por favor, gere um novo no portal de desenvolvedores e atualize o arquivo .env."
                )

            raise MetaAPIError(f"Erro ao consultar o Meta Ads: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar a Meta: {e}")
            raise MetaAPIError(
                "Não foi possível conectar aos servidores da Meta. Verifique sua conexão."
            )

    def get_campaign_insights(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> list[CampaignInsight]:
        """
        Busca os insights a nível de campanha com base no período selecionado.
        Inclui o objetivo da campanha para renderização dinâmica (ODAX).
        """
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "campaign",
            "fields": "campaign_name,campaign_id,objective,daily_budget,spend,impressions,clicks,cpc,cpm,actions",
            "limit": "1000",
        }

        if time_range:
            params["time_range"] = json.dumps(time_range)
        else:
            params["date_preset"] = date_preset

        insights = []
        try:
            while True:
                data = self._make_request(endpoint, params)
                insights_data = data.get("data", [])
                
                for item in insights_data:
                    insights.append(CampaignInsight.from_api_response(item))
                
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.error(f"Erro durante paginação de campanhas: {e}")
            sentry_sdk.capture_exception(e)

        return insights

    def get_demographics_insights(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> list[Any]:
        """Busca insights demográficos (Idade e Gênero)"""
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "account",
            "breakdowns": "age,gender",
            "fields": "impressions,clicks,spend",
            "limit": "1000",
        }
        if time_range:
            params["time_range"] = json.dumps(time_range)
        else:
            params["date_preset"] = date_preset

        insights = []
        from schemas.meta import DemographicsInsight
        try:
            while True:
                data = self._make_request(endpoint, params)
                for item in data.get("data", []):
                    insights.append(DemographicsInsight(
                        age=item.get("age", "Unknown"),
                        gender=item.get("gender", "Unknown"),
                        impressions=int(item.get("impressions", 0)),
                        clicks=int(item.get("clicks", 0)),
                        spend=float(item.get("spend", 0.0))
                    ))
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.error(f"Erro em demographics: {e}")
            sentry_sdk.capture_exception(e)
        return insights

    def get_creative_performance(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> list[Any]:
        """Busca a performance focado no Ad e cruza com a imagem do criativo."""
        # Passo 1: Insights no nível de ad
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "ad",
            "fields": "ad_id,ad_name,spend,impressions,clicks,actions",
            "limit": "1000",
        }
        if time_range:
            params["time_range"] = json.dumps(time_range)
        else:
            params["date_preset"] = date_preset

        insights_data = []
        try:
            while True:
                data = self._make_request(endpoint, params)
                insights_data.extend(data.get("data", []))
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.error(f"Erro em ad insights: {e}")
            sentry_sdk.capture_exception(e)

        # Passo 2: Buscar imagens/thumbnails no endpoint de ads
        ads_endpoint = f"{self.ad_account_id}/ads"
        ads_params = {
            "fields": "id,creative{thumbnail_url,image_url,body}",
            "limit": "1000",
        }
        ads_data = []
        try:
            while True:
                data = self._make_request(ads_endpoint, ads_params)
                ads_data.extend(data.get("data", []))
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    ads_params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.error(f"Erro em ads data: {e}")
            sentry_sdk.capture_exception(e)

        # Map ads data
        creatives_map = {}
        for ad in ads_data:
            c = ad.get("creative", {})
            creatives_map[ad.get("id")] = {
                "thumbnail_url": c.get("thumbnail_url"),
                "image_url": c.get("image_url"),
                "body": c.get("body", "")
            }

        # Cruzar os dados
        results = []
        from schemas.meta import CreativePerformance
        for item in insights_data:
            ad_id = item.get("ad_id")
            if not ad_id: continue
            
            leads = 0
            whatsapp = 0
            for action in item.get("actions", []):
                act_type = action.get("action_type", "")
                val = int(action.get("value", 0))
                if act_type in ["lead", "leadgen"]: leads += val
                if act_type in ["onsite_conversion.messaging_conversation_started_7d"]: whatsapp += val

            spend = float(item.get("spend", 0.0))
            clicks = int(item.get("clicks", 0))
            conversions = leads + whatsapp

            creative = creatives_map.get(ad_id, {})
            
            results.append(CreativePerformance(
                ad_id=ad_id,
                ad_name=item.get("ad_name", "Unknown"),
                image_url=creative.get("image_url"),
                thumbnail_url=creative.get("thumbnail_url"),
                body=creative.get("body"),
                spend=spend,
                impressions=int(item.get("impressions", 0)),
                clicks=clicks,
                leads=leads,
                whatsapp_starts=whatsapp,
                cpa=spend / conversions if conversions > 0 else 0.0,
                cpc=spend / clicks if clicks > 0 else 0.0
            ))

        # Ordenar por CPA e retornar
        return sorted(results, key=lambda x: (x.cpa == 0, x.cpa))

    def check_catalog_assets(self) -> list[Any]:
        """Busca catálogos vinculados à conta de anúncios"""
        endpoint = f"{self.ad_account_id}/owned_product_catalogs"
        try:
            params = {"fields": "id,name,product_count"}
            data = self._make_request(f"{self.ad_account_id}/product_catalogs", params)
            catalogs = []
            from schemas.meta import CatalogData
            for item in data.get("data", []):
                catalogs.append(CatalogData(
                    catalog_id=item.get("id"),
                    name=item.get("name"),
                    product_count=int(item.get("product_count", 0))
                ))
            return catalogs
        except Exception as e:
            logger.warning(f"Erro ao buscar catálogos (provavelmente não vinculado diretamente à ad_account): {e}")
            return []

    def get_total_organic_leads(self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None) -> int:
        """
        Busca leads dos formulários da página e conta apenas os orgânicos (is_organic=True).
        """
        endpoint = f"{self.page_id}/leadgen_forms"
        params = {"fields": "id"}
        try:
            data = self._make_request(endpoint, params)
            forms = data.get("data", [])
        except Exception as e:
            logger.warning(f"Erro ao buscar forms para leads orgânicos: {e}")
            return 0
            
        organic_leads = 0
        since_timestamp = None
        until_timestamp = None
        if time_range:
            since_dt = datetime.datetime.strptime(time_range["since"], "%Y-%m-%d")
            until_dt = datetime.datetime.strptime(time_range["until"], "%Y-%m-%d") + datetime.timedelta(days=1)
            since_timestamp = int(since_dt.timestamp())
            until_timestamp = int(until_dt.timestamp())
        else:
            if date_preset != "maximum":
                since_dt = datetime.datetime.now() - datetime.timedelta(days=30)
                since_timestamp = int(since_dt.timestamp())
                
        for form in forms:
            form_id = form.get("id")
            leads_endpoint = f"{form_id}/leads"
            leads_params = {"fields": "is_organic,created_time", "limit": "1000"}
            
            filtering = []
            if since_timestamp:
                filtering.append({"field": "time_created", "operator": "GREATER_THAN_OR_EQUAL", "value": since_timestamp})
            if until_timestamp:
                filtering.append({"field": "time_created", "operator": "LESS_THAN_OR_EQUAL", "value": until_timestamp})
                
            if filtering:
                leads_params["filtering"] = json.dumps(filtering)
            
            try:
                while True:
                    leads_data = self._make_request(leads_endpoint, leads_params)
                    for lead in leads_data.get("data", []):
                        if lead.get("is_organic") in [True, "true", 1, "1"]:
                            organic_leads += 1
                            
                    paging = leads_data.get("paging", {})
                    if "cursors" in paging and "after" in paging["cursors"]:
                        leads_params["after"] = paging["cursors"]["after"]
                    else:
                        break
            except Exception as e:
                logger.warning(f"Erro ao buscar leads do form {form_id}: {e}")
                
        return organic_leads

    def get_ads_reach_mapping(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        Busca insights de todos os anúncios e agrupa pelo ID do post do Instagram
        para cálculo do tráfego pago vs orgânico. Alta performance: Sem N+1 queries.

        Returns:
            Dict[str, Dict[str, int]]: Mapa com a chave sendo o 'effective_instagram_story_id' e o
                                       valor sendo a soma de reach, impressions e clicks.
        """
        # Passo 1: Buscar insights de todos os ads na conta de uma vez
        insights_endpoint = f"{self.ad_account_id}/insights"
        insights_params = {
            "level": "ad",
            "fields": "ad_id,reach,impressions,clicks,actions",
            "limit": "1000",
        }
        if time_range:
            insights_params["time_range"] = json.dumps(time_range)
        else:
            insights_params["date_preset"] = date_preset

        insights_data = []
        try:
            while True:
                data = self._make_request(insights_endpoint, insights_params)
                insights_data.extend(data.get("data", []))
                
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    insights_params["after"] = paging["cursors"]["after"]
                else:
                    break
        except MetaAPIError as e:
            logger.warning(
                f"Erro ao buscar insights de anúncios (Organic mapping): {e}"
            )
            sentry_sdk.capture_exception(e)
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
                    "likes": 0,
                    "shares": 0,
                    "saved": 0,
                }

                # Procura interações pagas (curtidas feitas no dark post)
                for action in item.get("actions", []):
                    action_type = action.get("action_type")
                    if action_type in [
                        "post_reaction",
                        "onsite_conversion.post_net_like",
                    ]:
                        ad_metrics_map[ad_id]["likes"] = max(
                            ad_metrics_map[ad_id]["likes"], int(action.get("value", 0))
                        )
                    elif action_type == "post":
                        ad_metrics_map[ad_id]["shares"] = max(
                            ad_metrics_map[ad_id]["shares"], int(action.get("value", 0))
                        )
                    elif action_type in [
                        "onsite_conversion.post_save",
                        "onsite_conversion.post_net_save",
                    ]:
                        ad_metrics_map[ad_id]["saved"] = max(
                            ad_metrics_map[ad_id]["saved"], int(action.get("value", 0))
                        )

        # Passo 2: Buscar a ligação entre o Ad e o Instagram Post (Feed, Reels, Stories)
        ads_endpoint = f"{self.ad_account_id}/ads"
        ads_params = {
            "fields": "id,creative{effective_instagram_story_id,effective_instagram_media_id,source_instagram_media_id}",
            "limit": "1000",
        }

        ads_data = []
        try:
            while True:
                data = self._make_request(ads_endpoint, ads_params)
                ads_data.extend(data.get("data", []))
                
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    ads_params["after"] = paging["cursors"]["after"]
                else:
                    break
        except MetaAPIError as e:
            logger.warning(f"Erro ao buscar lista de anúncios (Organic mapping): {e}")
            sentry_sdk.capture_exception(e)
            return {}

        # Passo 3: Agrupar as métricas baseadas no Instagram Post ID
        ig_mapping = {}
        for ad in ads_data:
            ad_id = ad.get("id")
            creative = ad.get("creative", {})

            # 1. source_instagram_media_id = Post original que deu origem ao anúncio (prioridade máxima)
            # 2. effective_instagram_media_id = Feed, Reels, Carousel (Ads nativos)
            # 3. effective_instagram_story_id = Stories
            ig_id = (
                creative.get("source_instagram_media_id")
                or creative.get("effective_instagram_media_id")
                or creative.get("effective_instagram_story_id")
            )

            # Se esse anúncio está atrelado a um post do IG e possui métricas registradas
            if ig_id and ad_id in ad_metrics_map:
                metrics = ad_metrics_map[ad_id]

                if ig_id not in ig_mapping:
                    ig_mapping[ig_id] = {
                        "reach": 0,
                        "impressions": 0,
                        "clicks": 0,
                        "likes": 0,
                        "shares": 0,
                        "saved": 0,
                    }

                ig_mapping[ig_id]["reach"] += metrics["reach"]
                ig_mapping[ig_id]["impressions"] += metrics["impressions"]
                ig_mapping[ig_id]["clicks"] += metrics["clicks"]
                ig_mapping[ig_id]["likes"] += metrics["likes"]
                ig_mapping[ig_id]["shares"] += metrics["shares"]
                ig_mapping[ig_id]["saved"] += metrics["saved"]

        return ig_mapping

