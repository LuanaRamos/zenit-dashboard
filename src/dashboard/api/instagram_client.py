import json
import logging
from typing import Any
import requests
import sentry_sdk
from api.exceptions import InstagramAPIError
from core.config import settings
from schemas.instagram import (
    AccountDemographics,
    InstagramDemographics,
    InstagramMedia,
    InstagramStory,
)

logger = logging.getLogger(__name__)


class InstagramClient:
    """
    Cliente para comunicação direta com a Graph API do Instagram.
    Responsável por fazer o fetch de publicações orgânicas, insights de mídia
    e informações cadastrais do perfil.
    """

    API_VERSION = "v26.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    # O Batch API recebe a versão em cada relative_url.
    BATCH_URL = "https://graph.facebook.com"

    def __init__(self, client_config) -> None:
        self.token = (
            client_config.token
            if getattr(client_config, "token", None)
            else settings.meta_master_token.get_secret_value()
        )
        self.page_id = client_config.page_id
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.instagram_account_id = self._fetch_instagram_account_id()

    def _fetch_instagram_account_id(self) -> str:
        """Busca o ID do Instagram vinculado à página dinamicamente."""
        url = f"{self.BASE_URL}/{self.page_id}"
        params = {"fields": "instagram_business_account"}
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "instagram_business_account" in data:
                return str(data["instagram_business_account"]["id"])
            else:
                logger.error(f"Nenhum Instagram vinculado à Página {self.page_id}.")
                raise InstagramAPIError(
                    "Nenhum Instagram Comercial vinculado à Página do Facebook. Verifique as configurações na Meta."
                )
        except Exception as e:
            if isinstance(e, InstagramAPIError):
                raise
            logger.error(f"Erro ao buscar instagram_business_account: {e}")
            sentry_sdk.capture_exception(e)
            raise InstagramAPIError(
                "Falha de conexão ao tentar validar o Instagram vinculado à conta."
            )

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
            error_data = e.response.json() if e.response is not None else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            logger.error(f"Erro na API do Instagram: {error_msg}")

            if e.response is not None and e.response.status_code == 401:
                raise InstagramAPIError(
                    "Token de Acesso do Instagram Inválido ou Expirado. Por favor, gere um novo token e atualize as configurações (Erro 401)."
                )

            if (
                "Session has expired" in error_msg
                or "Error validating access token" in error_msg
                or "OAuthException" in error_msg
            ):
                raise InstagramAPIError(
                    "O seu Token expirou ou é inválido. Por favor, gere um novo no portal de desenvolvedores e atualize o arquivo .env."
                )

            raise InstagramAPIError(f"Erro ao consultar a API do Instagram: {error_msg}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro de rede ao consultar o Instagram: {e}")
            raise InstagramAPIError(
                "Não foi possível conectar aos servidores do Instagram. Verifique sua conexão."
            )

    def get_account_profile_info(self) -> dict[str, Any]:
        """
        Busca informações do perfil do Instagram:
        foto, username, nome, biografia, contadores de seguidores, seguindo e publicações.
        """
        endpoint = f"{self.instagram_account_id}"
        fields = (
            "id,username,name,biography,profile_picture_url,"
            "followers_count,follows_count,media_count"
        )
        try:
            data = self._make_request(endpoint, {"fields": fields})
            return {
                "id": str(data.get("id", self.instagram_account_id)),
                "username": str(data.get("username", "")),
                "name": str(data.get("name", "")),
                "biography": str(data.get("biography", "")),
                "profile_picture_url": str(data.get("profile_picture_url", "")),
                "followers_count": int(data.get("followers_count", 0)),
                "follows_count": int(data.get("follows_count", 0)),
                "media_count": int(data.get("media_count", 0)),
            }
        except Exception as e:
            logger.warning(
                f"Erro ao buscar informações do perfil da conta {self.instagram_account_id}: {e}"
            )
            return {
                "id": str(self.instagram_account_id),
                "username": "",
                "name": "",
                "biography": "",
                "profile_picture_url": "",
                "followers_count": 0,
                "follows_count": 0,
                "media_count": 0,
            }

    def get_recent_media(  # noqa: C901
        self,
        limit: int = 50,
        since_timestamp: int | None = None,
        until_timestamp: int | None = None,
    ) -> list[InstagramMedia]:
        """
        Busca todas as páginas de publicações e seus insights via Batch Operations.

        ``limit`` é o tamanho de cada página, não o total de publicações.
        Sem filtros de data, percorre até a publicação mais antiga disponível.
        """
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            "fields": (
                "id,caption,media_url,thumbnail_url,permalink,timestamp,"
                "like_count,comments_count,media_type,media_product_type"
            ),
            "limit": str(limit),
        }

        if since_timestamp:
            params["since"] = str(since_timestamp)

        if until_timestamp:
            params["until"] = str(until_timestamp)

        media_items_data = []
        media_ids_seen = set()
        cursors_seen = set()

        while True:
            data = self._make_request(endpoint, params)
            page_data = data.get("data", [])
            for item in page_data:
                media_id = item.get("id")
                if media_id and media_id in media_ids_seen:
                    continue
                if media_id:
                    media_ids_seen.add(media_id)
                media_items_data.append(item)

            paging = data.get("paging", {})
            if not paging.get("next"):
                break
            after = paging.get("cursors", {}).get("after")
            if not after or after in cursors_seen:
                raise InstagramAPIError(
                    "A paginação do Instagram foi interrompida. "
                    "Não foi possível confirmar o histórico completo; tente atualizar novamente."
                )
            cursors_seen.add(after)
            params["after"] = after

        # Consultas em lote separadas por família de métricas. Uma métrica
        # não suportada não pode invalidar todas as outras do mesmo post.
        base_metrics = ("reach", "views", "likes", "comments", "saved",
                        "shares", "total_interactions")
        reel_metrics = ("ig_reels_video_view_total_time", "ig_reels_avg_watch_time")
        profile_metrics = ("profile_activity", "profile_visits", "follows")
        requested_by_media = {}
        for item in media_items_data:
            media_id = str(item.get("id") or "")
            if not media_id:
                continue
            relevant = list(base_metrics)
            if item.get("media_product_type") == "REELS":
                relevant.extend(reel_metrics)
                relevant.extend(profile_metrics)
            requested_by_media[media_id] = tuple(relevant)

        metrics_by_media: dict[str, dict] = {
            media_id: {} for media_id in requested_by_media
        }

        def fetch_metric_batch(requests_list):
            """Processa no máximo 50 GETs por POST, sem mascarar HTTP 400."""
            responses = {}
            for offset in range(0, len(requests_list), 50):
                chunk = requests_list[offset:offset + 50]
                try:
                    batch = self.session.post(
                        self.BATCH_URL,
                        data={
                            "access_token": self.token,
                            "batch": json.dumps([
                                {
                                    "method": "GET",
                                    "relative_url": (
                                        f"/{self.API_VERSION}/{media_id}/insights"
                                        f"?metric={','.join(names)}"
                                    ),
                                }
                                for media_id, names in chunk
                            ]),
                        },
                        timeout=30,
                    )
                    batch.raise_for_status()
                    payload = batch.json()
                    for (media_id, names), row in zip(chunk, payload):
                        if row.get("code") != 200:
                            continue
                        body = json.loads(row.get("body") or "{}")
                        extracted = {}
                        for insight in body.get("data", []):
                            name = insight.get("name")
                            if name not in names:
                                continue
                            raw = (insight.get("total_value") or {}).get("value")
                            if raw is None:
                                values = insight.get("values") or []
                                raw = values[0].get("value") if values else None
                            if isinstance(raw, (int, float)):
                                extracted[name] = raw
                        responses[(media_id, names)] = extracted
                except Exception as exc:
                    logger.warning("Batch de Insights de mídia indisponível: %s", exc)
            return responses

        # Prioriza grupos menores de métricas. Campos de Reel só são
        # consultados para Reels, e falhas geram fallback por campo.
        groups = (
            ("reach", "views"),
            ("likes", "comments", "saved", "shares", "total_interactions"),
            reel_metrics,
            profile_metrics,
        )
        for group in groups:
            requests_list = [
                (media_id, tuple(metric for metric in group
                                 if metric in requested_by_media[media_id]))
                for media_id in requested_by_media
            ]
            requests_list = [(mid, names) for mid, names in requests_list if names]
            batched = fetch_metric_batch(requests_list)
            retry = []
            for media_id, names in requests_list:
                got = batched.get((media_id, names), {})
                metrics_by_media[media_id].update(got)
                missing = [name for name in names if name not in got]
                if missing and len(names) > 1:
                    retry.extend((media_id, (metric,)) for metric in missing)
            if retry:
                for (media_id, names), found in fetch_metric_batch(retry).items():
                    metrics_by_media[media_id].update(found)

        media_list = []
        for item in media_items_data:
            ig_id = str(item.get("id") or "")
            if not ig_id:
                continue
            metrics_dict = metrics_by_media.get(ig_id, {})
            expected = requested_by_media.get(ig_id, ())
            present = tuple(name for name in expected if name in metrics_dict)
            missing = tuple(name for name in expected if name not in metrics_dict)
            if not expected or not present:
                status = "indisponivel"
            elif missing:
                status = "parcial"
            else:
                status = "ok"

            try:
                media = InstagramMedia(
                    id=ig_id,
                    caption=item.get("caption", ""),
                    media_url=item.get("media_url"),
                    thumbnail_url=item.get("thumbnail_url"),
                    media_type=item.get("media_type", ""),
                    media_product_type=item.get("media_product_type", ""),
                    permalink=item.get("permalink", ""),
                    timestamp=item.get("timestamp", ""),
                    like_count=metrics_dict.get("likes"),
                    comments_count=metrics_dict.get("comments"),
                    visible_like_count=item.get("like_count"),
                    visible_comments_count=item.get("comments_count"),
                    reach=metrics_dict.get("reach"),
                    shares=metrics_dict.get("shares"),
                    saved=metrics_dict.get("saved"),
                    total_interactions=metrics_dict.get("total_interactions"),
                    ig_reels_video_view_total_time=metrics_dict.get(
                        "ig_reels_video_view_total_time"
                    ),
                    organic_views=metrics_dict.get("views"),
                    ig_reels_avg_watch_time=metrics_dict.get(
                        "ig_reels_avg_watch_time"
                    ),
                    profile_activity=metrics_dict.get("profile_activity"),
                    profile_visits=metrics_dict.get("profile_visits"),
                    follows=metrics_dict.get("follows"),
                    insights_status=status,
                    insights_available=present,
                    insights_missing=missing,
                )
                media_list.append(media)
            except Exception as exc:
                logger.warning("Erro ao interpretar mídia do Instagram %s: %s", ig_id, exc)

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
            metrics = "views,reach,replies,shares,total_interactions"
            batch_requests.append(
                {
                    "method": "GET",
                    "relative_url": f"/{self.API_VERSION}/{ig_id}/insights?metric={metrics}",
                }
            )

        insights_map = {}
        for i in range(0, len(batch_requests), 50):
            chunk = batch_requests[i : i + 50]
            try:
                batch_res = self.session.post(
                    self.BATCH_URL,
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

        # "exits", "taps_forward" e "taps_back" foram substituídos
        # pela métrica navigation com breakdown específico.
        navigation_map = {}
        for i in range(0, len(stories_data), 50):
            subset = stories_data[i : i + 50]
            nav_requests = [
                {
                    "method": "GET",
                    "relative_url": (
                        f"/{self.API_VERSION}/{item['id']}/insights"
                        "?metric=navigation&breakdown=story_navigation_action_type"
                    ),
                }
                for item in subset
            ]
            try:
                nav_res = self.session.post(
                    self.BATCH_URL,
                    data={"access_token": self.token, "batch": json.dumps(nav_requests)},
                    timeout=20,
                )
                nav_res.raise_for_status()
                for j, response_item in enumerate(nav_res.json()):
                    if response_item.get("code") != 200:
                        continue
                    body = json.loads(response_item.get("body", "{}"))
                    actions = {}
                    for insight in body.get("data", []):
                        for breakdown in (
                            (insight.get("total_value") or {}).get("breakdowns") or []
                        ):
                            for result in breakdown.get("results", []):
                                dimensions = result.get("dimension_values") or []
                                if dimensions:
                                    key = str(dimensions[0]).upper()
                                    actions[key] = actions.get(key, 0) + int(
                                        result.get("value") or 0
                                    )
                    navigation_map[subset[j]["id"]] = actions
            except Exception as exc:
                logger.warning("Navegação de Stories indisponível: %s", exc)

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

            nav = navigation_map.get(ig_id, {})
            stories_list.append(
                InstagramStory(
                    id=ig_id,
                    caption=item.get("caption", ""),
                    media_url=item.get("media_url"),
                    permalink=item.get("permalink", ""),
                    timestamp=item.get("timestamp", ""),
                    views=metrics_dict.get("views"),
                    reach=metrics_dict.get("reach"),
                    shares=metrics_dict.get("shares"),
                    total_interactions=metrics_dict.get("total_interactions"),
                    replies=metrics_dict.get("replies"),
                    exits=nav.get("TAP_EXIT"),
                    taps_forward=nav.get("TAP_FORWARD"),
                    taps_back=nav.get("TAP_BACK"),
                    navigation=nav,
                )
            )

        return stories_list

    def get_account_insights(
        self,
        date_preset: str = "last_30d",
        time_range: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Consulta o maior histórico realmente recuperável por indicador.

        Contagens de eventos são somadas somente entre janelas disjuntas.
        Reach/accounts_engaged são consultados em uma única janela porque
        usuários únicos NÃO podem ser somados entre meses ou posts.
        Todas as métricas carregam sua cobertura, inclusive erros da API.
        """
        import datetime
        from dateutil.relativedelta import relativedelta

        today = datetime.datetime.now(datetime.timezone.utc).date()
        requested_full_history = date_preset == "maximum" and time_range is None
        end = today + datetime.timedelta(days=1)  # until exclusivo
        if time_range:
            start = datetime.date.fromisoformat(time_range["since"])
            end = datetime.date.fromisoformat(time_range["until"]) + datetime.timedelta(days=1)
        elif date_preset == "maximum":
            start = today - relativedelta(months=13)
        elif date_preset == "last_90d":
            start = today - datetime.timedelta(days=90)
        else:
            start = today - datetime.timedelta(days=30)

        # A API de Insights da conta não expõe alcance único vitalício.
        # 13 meses é um teto conservador para tentativa de backfill de
        # eventos; cada resposta efetiva é documentada abaixo.
        cutoff = today - relativedelta(months=13)
        clamped = start < cutoff
        if clamped:
            start = cutoff
        if start >= end:
            return {"_coverage": {}, "_requested_period": {
                "since": start.isoformat(), "until": end.isoformat(),
            }}

        additive = (
            "views", "total_interactions", "likes", "comments",
            "shares", "saves", "profile_links_taps",
        )
        unique = ("reach", "accounts_engaged")
        result: dict[str, Any] = {
            metric: None for metric in (*additive, *unique)
        }
        result.update({
            "profile_views": None, "website_clicks": None,
            "follows_and_unfollows": None,
            "_requested_period": {
                "since": (datetime.date.fromisoformat(time_range["since"]).isoformat()
                          if time_range else (today - relativedelta(months=13)).isoformat()
                          if date_preset == "maximum" else start.isoformat()),
                "until": (end - datetime.timedelta(days=1)).isoformat(),
            },
            "_coverage": {},
            "_is_partial": clamped or requested_full_history,
            "_history_note": (
                "A API não disponibiliza alcance único vitalício da conta. "
                "As datas de cada indicador representam apenas o histórico recuperado."
                if requested_full_history else ""
            ),
        })

        endpoint = f"{self.instagram_account_id}/insights"
        coverage = result["_coverage"]

        def _request(names: tuple[str, ...], begin: datetime.date,
                     finish: datetime.date) -> dict[str, int]:
            # Datas UTC e janelas não sobrepostas: [begin, finish).
            def ts(date: datetime.date) -> int:
                return int(datetime.datetime.combine(
                    date, datetime.time.min, tzinfo=datetime.timezone.utc
                ).timestamp())
            response = self._make_request(endpoint, {
                "metric": ",".join(names),
                "metric_type": "total_value",
                "period": "day",
                "since": str(ts(begin)),
                "until": str(ts(finish)),
            })
            values = {}
            for item in response.get("data", []):
                metric = item.get("name")
                raw = item.get("total_value", {}).get("value")
                if metric in names and isinstance(raw, (int, float)):
                    values[metric] = int(raw)
            return values

        def _set_coverage(metric: str, since: datetime.date | None,
                          until: datetime.date | None, status: str,
                          explanation: str) -> None:
            coverage[metric] = {
                "since": since.isoformat() if since else None,
                "until": (until - datetime.timedelta(days=1)).isoformat() if until else None,
                "status": status, "note": explanation,
            }

        # Contagens aditivas: blocos de até 30 dias, preservando a
        # cobertura real de CADA métrica, não apenas da consulta em grupo.
        # Se uma métrica tornar o batch inválido, tentamos as demais
        # individualmente em vez de zerar o relatório inteiro.
        earliest: dict[str, datetime.date] = {}
        latest: dict[str, datetime.date] = {}
        failed: set[str] = set()
        remaining = set(additive)
        cursor = end
        while cursor > start and remaining:
            begin = max(start, cursor - datetime.timedelta(days=30))
            batch_names = tuple(m for m in additive if m in remaining)
            try:
                found = _request(batch_names, begin, cursor)
            except Exception as exc:
                logger.warning("Falha do grupo de insights %s: %s", batch_names, exc)
                found = {}
            for metric in batch_names:
                if metric not in found:
                    try:
                        found.update(_request((metric,), begin, cursor))
                    except Exception as exc:
                        logger.warning("Insight %s indisponível: %s", metric, exc)
                if metric in found:
                    result[metric] = (result[metric] or 0) + found[metric]
                    earliest[metric] = begin
                    latest.setdefault(metric, cursor)
                else:
                    failed.add(metric)
                    # Consultas antigas que falham não apagam totais recentes.
                    remaining.discard(metric)
            cursor = begin

        for metric in additive:
            if metric in earliest:
                was_partial = earliest[metric] > start or clamped or requested_full_history
                _set_coverage(
                    metric, earliest[metric], latest[metric],
                    "parcial" if was_partial else "ok",
                    ("Somente a parte acessível do período; janelas anteriores indisponíveis."
                     if was_partial else "Soma de janelas disjuntas retornadas pela API.")
                )
            else:
                _set_coverage(metric, None, None, "indisponivel",
                              "A API não retornou valor para esta métrica.")

        # Métricas únicas: uma ÚNICA consulta agregada por período.
        # Se a API recusar 90 dias, reduzir para 30, nunca somar
        # alcances mensais ou somas de alcances das publicações.
        unique_end = end
        for metric in unique:
            found = None
            for days in (90, 30):
                begin = max(start, unique_end - datetime.timedelta(days=days))
                if begin >= unique_end:
                    continue
                try:
                    value = _request((metric,), begin, unique_end).get(metric)
                except Exception as exc:
                    logger.warning("Insight único %s (%s dias): %s", metric, days, exc)
                    value = None
                if value is not None:
                    found = (value, begin)
                    break
            if found is None:
                _set_coverage(metric, None, None, "indisponivel",
                              "A API não retornou um agregado único compatível.")
            else:
                value, begin = found
                result[metric] = value
                partial = begin > start or clamped or requested_full_history
                _set_coverage(
                    metric, begin, unique_end, "parcial" if partial else "ok",
                    ("Agregado único da janela informada; não representa o histórico vitalício."
                     if partial else "Agregado único do período sem somas entre janelas.")
                )

        # Não reaproveitar nomes descontinuados ou não equivalentes.
        for metric in ("profile_views", "website_clicks", "follows_and_unfollows"):
            _set_coverage(
                metric, None, None, "indisponivel",
                ("Sem equivalente direto validado nesta consulta. "
                 "Não foi substituído por outra métrica de significado diferente.")
            )
        result["_is_segmented"] = len(earliest) > 0 and (
            end - start
        ).days > 30
        return result

    def get_total_media_count(self) -> int:
        """Busca o número total de posts publicados pela conta."""
        try:
            params = {"fields": "media_count"}
            data = self._make_request(f"{self.instagram_account_id}", params)
            return int(data.get("media_count", 0))
        except Exception as e:
            logger.warning(f"Erro ao contar media: {e}")
            return 0

    def get_all_media_ids_since_beginning(self, max_pages: int = 5) -> list[str]:
        """
        Busca IDs de mídia da conta. Por padrão limita a 5 páginas (até 500 mídias)
        para garantir performance e prevenir timeouts de requisição.
        """
        endpoint = f"{self.instagram_account_id}/media"
        params = {
            "fields": "id",
            "limit": "100",
        }
        media_ids = []
        pages = 0
        try:
            while pages < max_pages:
                data = self._make_request(endpoint, params)
                page_data = data.get("data", [])
                if not page_data:
                    break
                media_ids.extend([item["id"] for item in page_data])
                pages += 1
                paging = data.get("paging", {})
                if "cursors" in paging and "after" in paging["cursors"]:
                    params["after"] = paging["cursors"]["after"]
                else:
                    break
        except Exception as e:
            logger.warning(f"Erro ao buscar all_media_ids: {e}")
        return media_ids

    def get_comments_for_media(
        self, media_ids: list[str], limit_per_media: int = 25
    ) -> list[dict[str, Any]]:
        """
        Busca comentários de uma lista específica de mídias usando requisições em lote (Batch API).
        Otimizado para execução rápida sem varredura completa da conta.
        """
        if not media_ids:
            return []

        batch_requests = [
            {
                "method": "GET",
                "relative_url": (
                    f"/{self.API_VERSION}/{ig_id}/comments"
                    f"?fields=id,text,like_count,username,timestamp&limit={limit_per_media}"
                ),
            }
            for ig_id in media_ids
        ]

        all_comments = []
        try:
            for i in range(0, len(batch_requests), 50):
                chunk = batch_requests[i : i + 50]
                batch_res = self.session.post(
                    self.BATCH_URL,
                    data={"access_token": self.token, "batch": json.dumps(chunk)},
                    timeout=20,
                )
                batch_res.raise_for_status()
                for media_id, response_item in zip(
                    media_ids[i : i + 50], batch_res.json(), strict=False
                ):
                    if response_item.get("code") == 200:
                        body = json.loads(response_item.get("body", "{}"))
                        comments = body.get("data", [])
                        all_comments.extend(
                            {**comment, "media_id": str(media_id)}
                            for comment in comments
                        )
        except Exception as e:
            logger.error(f"Erro ao buscar comentários via Batch: {e}")
            sentry_sdk.capture_exception(e)

        return all_comments

    def get_all_comments_for_account(
        self, media_ids: list[str]
    ) -> list[dict[str, Any]]:
        """
        Busca comentários para uma lista de mídias fornecida.
        Mantido para compatibilidade, delegando para get_comments_for_media.
        """
        return self.get_comments_for_media(media_ids)

    def get_followers_history(self) -> list:
        """
        Busca o histórico de follower_count (novos seguidores diários) dos últimos 30 dias.
        A API da Meta bloqueia a consulta de período maior que 30 dias para essa métrica.
        Retorna uma lista de dicionários contendo o ganho diário.
        """
        import datetime

        endpoint = f"{self.instagram_account_id}/insights"

        until_dt = datetime.datetime.now()
        since_dt = until_dt - datetime.timedelta(days=30)

        params = {
            "metric": "follower_count",
            "period": "day",
            "since": int(since_dt.timestamp()),
            "until": int(until_dt.timestamp()),
        }

        try:
            data = self._make_request(endpoint, params)
            insights = data.get("data", [])
            if insights and insights[0].get("values"):
                return insights[0]["values"]
            return []
        except Exception as e:
            logger.warning(
                f"Não foi possível buscar follower_count history (possivelmente conta pré-business): {e}"
            )
            return []

    def get_account_demographics(self) -> "AccountDemographics":
        """
        Busca os dados demográficos (Idade, Gênero, Cidades, Países) dos Seguidores
        e do Público Engajado (Últimos 30 dias).
        """
        endpoint = f"{self.instagram_account_id}/insights"

        def _fetch_demographic(
            metric: str, timeframe: str | None = None
        ) -> InstagramDemographics:
            age_gender = {}
            cities = {}
            countries = {}

            breakdown_queries = ["age,gender", "city", "country"]

            for brk in breakdown_queries:
                params = {
                    "metric": metric,
                    "period": "lifetime",
                    "breakdown": brk,
                    "metric_type": "total_value",
                }
                if timeframe:
                    params["timeframe"] = timeframe

                try:
                    data = self._make_request(endpoint, params)
                    insights = data.get("data", [])
                    for insight in insights:
                        if insight.get("name") == metric:
                            breakdowns = insight.get("total_value", {}).get(
                                "breakdowns", []
                            )
                            for brk_data in breakdowns:
                                dims = brk_data.get("dimension_keys", [])
                                results = brk_data.get("results", [])

                                if "age" in dims and "gender" in dims:
                                    for res in results:
                                        val_dims = res.get("dimension_values", [])
                                        if len(val_dims) == 2:
                                            key = f"{val_dims[0]} ({val_dims[1]})"
                                            age_gender[key] = res.get("value", 0)
                                elif "city" in dims:
                                    for res in results:
                                        val_dims = res.get("dimension_values", [])
                                        if len(val_dims) == 1:
                                            cities[val_dims[0]] = res.get("value", 0)
                                elif "country" in dims:
                                    for res in results:
                                        val_dims = res.get("dimension_values", [])
                                        if len(val_dims) == 1:
                                            countries[val_dims[0]] = res.get(
                                                "value", 0
                                            )
                except Exception as e:
                    logger.warning(
                        f"Erro ao buscar {metric} com breakdown {brk}: {e}"
                    )

            return InstagramDemographics(
                age_gender=age_gender, cities=cities, countries=countries
            )

        followers_demo = _fetch_demographic("follower_demographics", timeframe=None)
        engaged_demo = _fetch_demographic(
            "engaged_audience_demographics", timeframe="this_month"
        )
        reached_demo = _fetch_demographic(
            "reached_audience_demographics", timeframe="this_month"
        )

        return AccountDemographics(
            followers=followers_demo,
            engaged=engaged_demo,
            reached=reached_demo,
        )
