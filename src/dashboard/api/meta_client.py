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

    def __init__(self, client_config) -> None:
        self.token = client_config.token if getattr(client_config, "token", None) else settings.meta_master_token.get_secret_value()
        self.ad_account_id = client_config.ad_account_id
        if not self.ad_account_id.startswith("act_"):
            self.ad_account_id = f"act_{self.ad_account_id}"
        self.page_id = client_config.page_id
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
            response = self.session.get(url, params=params, timeout=10, verify=False)
            response.raise_for_status()
            return response.json()  # type: ignore
        except requests.exceptions.HTTPError as e:
            error_data = e.response.json() if e.response else {}
            error_msg = error_data.get("error", {}).get("message", str(e))

            logger.error(f"Erro na API da Meta: {error_msg}")

            if (
                "Session has expired" in error_msg
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
            "fields": "campaign_name,campaign_id,objective,spend,impressions,clicks,cpc,cpm,actions",
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
                insights_data = data.get("data") or []
                
                for item in insights_data:
                    try:
                        insights.append(CampaignInsight.from_api_response(item))
                    except Exception as e:
                        logger.error(f"Erro ao converter insight da campanha: {e}")
                        sentry_sdk.capture_exception(e)
                
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.error(f"Erro durante paginação de campanhas: {e}")
            sentry_sdk.capture_exception(e)
            raise e

        return insights

    def get_demographics_insights(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> "InstagramDemographics":
        """Busca insights demográficos (Idade, Gênero, Cidades, Países) para Ads"""
        from schemas.instagram import InstagramDemographics
        
        endpoint = f"{self.ad_account_id}/insights"
        
        age_gender = {}
        cities = {}
        countries = {}

        breakdowns_list = ["age,gender", "country", "region"]

        for brk in breakdowns_list:
            params = {
                "level": "account",
                "breakdowns": brk,
                "fields": "impressions,spend",
                "limit": "1000",
            }
            if time_range:
                params["time_range"] = json.dumps(time_range)
            else:
                params["date_preset"] = date_preset

            try:
                while True:
                    data = self._make_request(endpoint, params)
                    for item in data.get("data", []):
                        val = int(item.get("impressions", 0))
                        
                        if brk == "age,gender":
                            a = item.get("age", "Unknown")
                            g = item.get("gender", "Unknown")
                            if a != "Unknown" and g != "Unknown":
                                key = f"{a} ({g})"
                                age_gender[key] = age_gender.get(key, 0) + val
                        elif brk == "country":
                            country = item.get("country", "Unknown")
                            if country != "Unknown":
                                countries[country] = countries.get(country, 0) + val
                        elif brk == "region":
                            # 'region' no Meta Ads = estado/região (o mais próximo de cidade disponível)
                            region = item.get("region", "Unknown")
                            if region != "Unknown":
                                cities[region] = cities.get(region, 0) + val
                                
                    paging = data.get("paging", {})
                    if "cursors" in paging and "after" in paging["cursors"]:
                        params["after"] = paging["cursors"]["after"]
                    else:
                        break
            except Exception as e:
                logger.error(f"Erro em demographics (breakdown {brk}): {e}")
                sentry_sdk.capture_exception(e)

        return InstagramDemographics(
            age_gender=age_gender,
            cities=cities,
            countries=countries
        )

    def get_creative_real_audience(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> dict[str, dict]:
        """
        Retorna o público REAL entregue por anúncio (não o targeting configurado).

        Usa breakdowns da Insights API para saber quem de fato viu o anúncio —
        essencial para campanhas Advantage+ onde a Meta espalha o criativo
        automaticamente para o melhor público sem configuração manual.

        Returns:
            Dict[ad_id, {
                "age_gender": {"25-34 (female)": 812, ...},
                "regions": {"Ceará": 3439, ...},
                "countries": {"BR": 47562, ...},
            }]
        """
        endpoint = f"{self.ad_account_id}/insights"
        base_params: dict = {"level": "ad", "fields": "ad_id,impressions", "limit": "1000"}
        if time_range:
            base_params["time_range"] = json.dumps(time_range)
        else:
            base_params["date_preset"] = date_preset

        audience_map: dict[str, dict] = {}

        for brk in ["age,gender", "region", "country"]:
            params = {**base_params, "breakdowns": brk}
            try:
                while True:
                    data = self._make_request(endpoint, params)
                    for item in data.get("data", []):
                        ad_id = item.get("ad_id", "")
                        if not ad_id:
                            continue
                        if ad_id not in audience_map:
                            audience_map[ad_id] = {"age_gender": {}, "regions": {}, "countries": {}}

                        impressions = int(item.get("impressions", 0))

                        if brk == "age,gender":
                            age = item.get("age", "")
                            gender = item.get("gender", "")
                            if age and gender:
                                key = f"{age} ({gender})"
                                audience_map[ad_id]["age_gender"][key] = (
                                    audience_map[ad_id]["age_gender"].get(key, 0) + impressions
                                )
                        elif brk == "region":
                            region = item.get("region", "")
                            if region:
                                audience_map[ad_id]["regions"][region] = (
                                    audience_map[ad_id]["regions"].get(region, 0) + impressions
                                )
                        elif brk == "country":
                            country = item.get("country", "")
                            if country:
                                audience_map[ad_id]["countries"][country] = (
                                    audience_map[ad_id]["countries"].get(country, 0) + impressions
                                )

                    paging = data.get("paging", {})
                    if "cursors" in paging and "after" in paging["cursors"]:
                        params["after"] = paging["cursors"]["after"]
                    else:
                        break
            except Exception as e:
                logger.warning(f"Erro em real audience breakdown={brk}: {e}")
                sentry_sdk.capture_exception(e)

        return audience_map

    def get_creative_performance(
        self, date_preset: str = "last_30d", time_range: dict[str, str] | None = None
    ) -> list[Any]:
        """Busca a performance focado no Ad, cruza com criativo, público-alvo e datas do adset."""
        # Passo 1: Insights no nível de ad
        endpoint = f"{self.ad_account_id}/insights"
        params = {
            "level": "ad",
            "fields": "ad_id,ad_name,objective,spend,impressions,clicks,actions",
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

        # Passo 2: Buscar imagens/thumbnails + adset (targeting + schedule) no endpoint de ads
        ads_endpoint = f"{self.ad_account_id}/ads"
        ads_params = {
            "fields": (
                "id,name,status,"
                "creative{thumbnail_url,image_url,body},"
                "adset{id,name,start_time,end_time,status,targeting}"
            ),
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

        # Mapa enriquecido: ad_id -> criativo + targeting + schedule
        creatives_map = {}
        for ad in ads_data:
            c = ad.get("creative", {})
            adset = ad.get("adset", {})
            tgt = adset.get("targeting", {})
            geo = tgt.get("geo_locations", {})

            # Cidades e países do targeting
            cities_tgt = [x.get("name", "") for x in geo.get("cities", [])]
            countries_tgt = geo.get("countries", [])
            regions_tgt = [x.get("name", "") for x in geo.get("regions", [])]

            gender_map = {1: "Masculino", 2: "Feminino"}
            genders_raw = tgt.get("genders", [])
            genders_tgt = [gender_map.get(g, str(g)) for g in genders_raw] if genders_raw else ["Todos"]

            creatives_map[ad.get("id")] = {
                "thumbnail_url": c.get("thumbnail_url"),
                "image_url": c.get("image_url"),
                "body": c.get("body", ""),
                "ad_status": ad.get("status", ""),
                "adset_name": adset.get("name", ""),
                "start_time": adset.get("start_time"),
                "end_time": adset.get("end_time"),
                "adset_status": adset.get("status", ""),
                "age_min": tgt.get("age_min"),
                "age_max": tgt.get("age_max"),
                "genders": genders_tgt,
                "cities": cities_tgt,
                "countries": countries_tgt,
                "regions": regions_tgt,
            }

        # Cruzar dados e montar CreativePerformance
        results = []
        from schemas.meta import CreativePerformance
        for item in insights_data:
            ad_id = item.get("ad_id")
            if not ad_id:
                continue

            leads = 0
            whatsapp = 0
            instagram_follows = 0
            profile_visits = 0
            link_clicks = 0
            for action in item.get("actions", []):
                act_type = action.get("action_type", "")
                val = int(action.get("value", 0))
                if act_type == "link_click":
                    link_clicks += val
                if act_type in ["lead", "leadgen"]:
                    leads += val
                if act_type.startswith("onsite_conversion.messaging_conversation_started"):
                    whatsapp += val
                if act_type == "instagram_follows":
                    instagram_follows += val
                if act_type in ["profile_visit", "instagram_profile_views"]:
                    profile_visits += val
                    
            if instagram_follows == 0:
                instagram_follows = int(item.get("instagram_follows", 0))

            spend = float(item.get("spend", 0.0))
            clicks = int(item.get("clicks", 0))
            
            objective = item.get("objective", "UNKNOWN")
            if objective in ["OUTCOME_TRAFFIC", "LINK_CLICKS", "OUTCOME_AWARENESS"] and instagram_follows > 0:
                cpa = spend / instagram_follows
            else:
                conversions = leads + whatsapp
                cpa = spend / conversions if conversions > 0 else 0.0

            creative = creatives_map.get(ad_id, {})

            results.append(CreativePerformance(
                ad_id=ad_id,
                ad_name=item.get("ad_name", "Unknown"),
                objective=item.get("objective", "UNKNOWN"),
                image_url=creative.get("image_url"),
                thumbnail_url=creative.get("thumbnail_url"),
                body=creative.get("body"),
                spend=spend,
                impressions=int(item.get("impressions", 0)),
                clicks=clicks,
                link_clicks=link_clicks,
                leads=leads,
                whatsapp_starts=whatsapp,
                instagram_follows=instagram_follows,
                profile_visits=profile_visits,
                cpa=cpa,
                cpc=spend / clicks if clicks > 0 else 0.0,
                # Novos campos
                ad_status=creative.get("ad_status", ""),
                adset_name=creative.get("adset_name", ""),
                start_time=creative.get("start_time"),
                end_time=creative.get("end_time"),
                adset_status=creative.get("adset_status", ""),
                age_min=creative.get("age_min"),
                age_max=creative.get("age_max"),
                genders=creative.get("genders", []),
                target_cities=creative.get("cities", []),
                target_countries=creative.get("countries", []),
                target_regions=creative.get("regions", []),
            ))

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
            "breakdowns": "publisher_platform",
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
            if item.get("publisher_platform") != "instagram":
                continue
                
            ad_id = item.get("ad_id")
            if ad_id:
                if ad_id not in ad_metrics_map:
                    ad_metrics_map[ad_id] = {
                        "reach": 0,
                        "impressions": 0,
                        "clicks": 0,
                        "link_clicks": 0,
                        "likes": 0,
                        "shares": 0,
                        "saved": 0,
                    }
                
                ad_metrics_map[ad_id]["reach"] += int(item.get("reach", 0))
                ad_metrics_map[ad_id]["impressions"] += int(item.get("impressions", 0))
                ad_metrics_map[ad_id]["clicks"] += int(item.get("clicks", 0))

                # Procura interações pagas (curtidas feitas no dark post) e link clicks
                for action in item.get("actions", []):
                    action_type = action.get("action_type")
                    if action_type == "link_click":
                        ad_metrics_map[ad_id]["link_clicks"] += int(action.get("value", 0))
                    elif action_type in [
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
                        "link_clicks": 0,
                        "likes": 0,
                        "shares": 0,
                        "saved": 0,
                    }

                ig_mapping[ig_id]["reach"] += metrics["reach"]
                ig_mapping[ig_id]["impressions"] += metrics["impressions"]
                ig_mapping[ig_id]["clicks"] += metrics["clicks"]
                ig_mapping[ig_id]["link_clicks"] += metrics.get("link_clicks", 0)
                ig_mapping[ig_id]["likes"] += metrics["likes"]
                ig_mapping[ig_id]["shares"] += metrics["shares"]
                ig_mapping[ig_id]["saved"] += metrics["saved"]

        return ig_mapping

