"""Diagnóstico seguro das falhas de Meta Ads, sem imprimir credenciais.

O aplicativo não conhece os acessos do Gerenciador de Negócios: consultas
somente leitura identificam em qual fronteira ocorre o problema.
"""
from __future__ import annotations

import logging
from typing import Any

import streamlit as st

logger = logging.getLogger(__name__)


def classify_ads_error(error: Exception) -> dict[str, str]:
    """Classifica apenas padrões de erro. Nunca inclui o texto bruto no retorno."""
    message = str(error).casefold()
    if any(t in message for t in (
        "access token", "invalid token", "session has expired",
        "token expir", "token invál", "(#190)", "oauth 190", "erro 401",
    )):
        return {
            "code": "auth",
            "title": "Credencial Meta inválida ou expirada",
            "action": "Verifique a credencial da integração nas configurações do Streamlit.",
        }
    if any(t in message for t in (
        "permission", "(#200)", "not authorized", "not permitted",
        "permissão", "permissões", "access denied",
    )):
        return {
            "code": "permission",
            "title": "Acesso aos anúncios não autorizado",
            "action": "Confira se a integração possui ads_read e acesso à conta no portfólio empresarial.",
        }
    if any(t in message for t in (
        "unsupported get request", "object with id", "does not exist",
        "object not found", "unknown object",
    )):
        return {
            "code": "access",
            "title": "Conta de anúncios inacessível",
            "action": "Confirme o ID da conta e se ela foi compartilhada com o usuário da integração.",
        }
    if any(t in message for t in (
        "unknown field", "nonexisting field", "unsupported field",
        "invalid field", "campo inválido", "field not found",
    )):
        return {
            "code": "fields",
            "title": "Métrica não aceita pela API",
            "action": "A consulta de campanhas precisa usar os campos compatíveis com esta conta.",
        }
    if any(t in message for t in (
        "timed out", "timeout", "connection", "network", "conexão",
        "rate limit", "too many requests",
    )):
        return {
            "code": "network",
            "title": "Falha temporária na comunicação",
            "action": "Tente atualizar os dados. Se persistir, consulte os registros de execução.",
        }
    return {
        "code": "unknown",
        "title": "Não foi possível carregar os anúncios",
        "action": "Use o teste de acesso abaixo para separar falha de autorização e falha de métricas.",
    }


def render_ads_diagnostic(client: Any, error: Exception, stage: str) -> None:
    """Mostra a etapa que falhou e oferece uma verificação GET não destrutiva."""
    from ui.build_info import UI_BUILD_ID

    result = classify_ads_error(error)
    logger.error(
        "Falha Ads na etapa %s, conta %s, categoria %s",
        stage, getattr(client, "name", ""), result["code"], exc_info=True,
    )
    st.error(result["title"])
    st.caption(result["action"])
    with st.expander("Diagnóstico de anúncios", expanded=False):
        st.write(f"Etapa: {stage}")
        st.write(f"Conta de anúncios configurada: {'sim' if getattr(client, 'ad_account_id', '') else 'não'}")
        st.write(f"Categoria: {result['code']}")
        st.caption(f"Versão do dashboard: {UI_BUILD_ID}")
        st.caption("O teste abaixo consulta apenas o cadastro da conta. Não altera campanhas ou verbas.")
        if st.button("Testar acesso à conta", key=f"ads_probe_{getattr(client, 'name', 'cliente')}"):
            try:
                from ui.data_loader import get_api_client
                probe = get_api_client(client.name).probe_ads_account()
                if probe.get("ok"):
                    st.success("Acesso à conta confirmado. Investigue métricas, período ou renderização.")
                else:
                    st.warning("A API não confirmou o acesso à conta.")
            except Exception as probe_error:
                logger.warning(
                    "Teste de acesso Meta falhou para %s", getattr(client, "name", ""),
                    exc_info=True,
                )
                detail = classify_ads_error(probe_error)
                st.warning(detail["title"])
                st.caption(detail["action"])
