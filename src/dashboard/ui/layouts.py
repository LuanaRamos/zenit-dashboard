import datetime
import unicodedata
import streamlit as st
from ui.build_info import UI_BUILD_ID
from streamlit_option_menu import option_menu
from core.config import ClientConfig


import base64
from pathlib import Path


def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


def _client_name_sort_key(name: str) -> tuple[str, str, str]:
    folded = name.casefold()
    normalized = unicodedata.normalize("NFD", folded)
    unaccented = "".join(char for char in normalized if not unicodedata.combining(char))
    return unaccented, folded, name


def available_modules_for_client(client: "ClientConfig") -> list[str]:
    """Exibe somente funcionalidades para as quais o cliente tem ativos."""
    return (
        ["Visão Geral (Ads)", "Orgânico (Instagram)"]
        if client.has_ads
        else ["Orgânico (Instagram)"]
    )


def render_sidebar() -> tuple[str, str, dict[str, str] | None, "ClientConfig"]:
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna (modulo_selecionado, date_preset, time_range, client_config).
    """
    with st.sidebar:
        # Marca da Zenit e navegação de alto contraste
        logo_path = Path(__file__).parent.parent / "assets" / "zenit_logo.png"
        if logo_path.exists():
            logo_base64 = get_base64_image(logo_path)
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" alt="Logo da Zenit" width="32" height="32" style="width: 32px; height: 32px; border-radius: 6px; box-shadow: 0 4px 12px rgba(255, 179, 0, 0.3); object-fit: contain;">'
        else:
            logo_html = '<div style="width: 26px; height: 26px; border-radius: 6px; background: linear-gradient(135deg, #FFB300, #FF6F00); box-shadow: 0 4px 12px rgba(255, 179, 0, 0.3);"></div>'

        st.markdown(
            f"""
            <div style="padding: 4px 0 10px 0; text-align: left; display: flex; align-items: center; gap: 12px;">
                {logo_html}
                <h2 style="margin:0; font-size: 1.3rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.5px;">
                    <span style="color: #ffffff;">Zenit</span><span style="color: #FFB300;">Analytics</span>
                </h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        from core.config import settings

        try:
            clients = settings.get_clients()
        except ValueError as exc:
            # Mensagem inclui apenas índice/nomes de campos, nunca credenciais.
            st.error(f"Configuração CLIENTS_JSON inválida: {exc}")
            st.stop()
        if not clients:
            st.error("Nenhum cliente configurado no sistema (CLIENTS_JSON).")
            st.stop()

        client_names = sorted((client.name for client in clients), key=_client_name_sort_key)
        # A ordem do menu é independente do cliente padrão definido na configuração.
        if st.session_state.get("selected_client_name") not in client_names:
            st.session_state["selected_client_name"] = clients[0].name


        def on_client_change():
            # Os caches já usam client_name como chave; não invalidar outras contas.
            st.session_state["data_loaded"] = False

        selected_client_name = st.selectbox(
            "Selecione o Cliente",
            options=client_names,
            key="selected_client_name",
            label_visibility="visible",
            on_change=on_client_change,
        )

        selected_client = next(c for c in clients if c.name == selected_client_name)

        st.markdown(
            "<h4 style='color: #c4c9ac; font-size: 0.72rem; margin-top: 10px; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Navegação</h4>",
            unsafe_allow_html=True,
        )
        selected_module = option_menu(
            menu_title=None,
            options=available_modules_for_client(selected_client),
            icons=(
                ["bar-chart-line-fill", "instagram"]
                if selected_client.has_ads else ["instagram"]
            ),
            menu_icon="cast",
            default_index=0,
            key=f"navigation_{selected_client.name}",
            styles={
                "container": {
                    "padding": "0!important",
                    "background-color": "transparent",
                },
                "icon": {"color": "#c4c9ac", "font-size": "15px"},
                "nav-link": {
                    "font-size": "13px",
                    "text-align": "left",
                    "margin": "0px 0px 4px 0px",
                    "--hover-color": "rgba(255, 255, 255, 0.02)",
                    "border-radius": "6px",
                    "padding": "8px 12px",
                    "border": "1px solid transparent",
                    "color": "#c4c9ac",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "500",
                    "transition": "background-color 160ms ease, color 160ms ease",
                },
                "nav-link-selected": {
                    "background": "rgba(255, 179, 0, 0.08)",
                    "border": "1px solid rgba(255, 179, 0, 0.15)",
                    "box-shadow": "none",
                    "color": "#FFB300",
                    "font-weight": "600",
                },
            },
        )

        # Override icon color when selected to Zenit Gold
        st.markdown(
            """
        <style>
        .nav-item .active i { color: #FFB300 !important; }
        </style>
        """,
            unsafe_allow_html=True,
        )

        # Filtro de Tempo Global
        periodo_selecionado = st.selectbox(
            "Período de Análise",
            [
                "Últimos 30 Dias",
                "Todo o histórico disponível",
                "Personalizado",
            ],
            label_visibility="visible",
        )
        if selected_module == "Orgânico (Instagram)":
            st.caption("Posts por data de publicação.")

        date_preset = "last_30d"
        time_range = None

        if periodo_selecionado == "Todo o histórico disponível":
            date_preset = "maximum"
            if selected_module == "Orgânico (Instagram)":
                with st.expander("Cobertura do período", expanded=False):
                    st.caption(
                        "Posts desde a primeira publicação acessível. "
                        "Insights da conta respeitam limites próprios da Meta."
                    )
            else:
                from ui.data_loader import fetch_ads_history_coverage_cached

                history = fetch_ads_history_coverage_cached(selected_client.name)
                with st.expander("Cobertura do período", expanded=False):
                    if history.get("status") == "ok":
                        st.caption(
                            f"Primeira entrega identificada: {history.get('first_delivery', 'N/D')}. "
                            f"Início da consulta: {history.get('requested_since', 'N/D')}."
                        )
                    else:
                        st.caption(
                            history.get("note", "Início histórico não confirmado.")
                        )
        elif "Personalizado" in periodo_selecionado:
            date_preset = "custom"

            min_date = datetime.date(2004, 2, 4)
            max_date = datetime.date.today()

            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input(
                    "Data Inicial",
                    value=max_date - datetime.timedelta(days=30),
                    min_value=min_date,
                    max_value=max_date,
                    format="DD/MM/YYYY",
                )
            with col2:
                end_date = st.date_input(
                    "Data Final",
                    value=max_date,
                    min_value=min_date,  # Usar a data mínima global para destravar o seletor de ano
                    max_value=max_date,
                    format="DD/MM/YYYY",
                )

            if start_date and end_date:
                if start_date > end_date:
                    st.error("A data inicial precisa ser anterior à data final.")
                    st.stop()
                else:
                    delta = end_date - start_date
                    if selected_module == "Visão Geral (Ads)" and delta.days > 1125:
                        st.warning(
                            "O intervalo solicitado ultrapassa a janela retroativa "
                            "usual de 37 meses dos Insights de anúncios. "
                            "Use 'Todo o histórico disponível' para consultar o máximo "
                            "recuperável com indicação da cobertura."
                        )
                        st.stop()
                    time_range = {
                        "since": start_date.strftime("%Y-%m-%d"),
                        "until": end_date.strftime("%Y-%m-%d"),
                    }
            else:
                st.warning("Selecione a data inicial e final.")
                st.stop()

        st.markdown(
            "<div style='margin-top: 14px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;'></div>",
            unsafe_allow_html=True,
        )
        version_file = Path(__file__).resolve().parents[3] / "VERSION"
        if version_file.exists():
            st.caption(
                f"Zenit Analytics · v{version_file.read_text(encoding='utf-8').strip()} "
                f"· build {UI_BUILD_ID}"
            )
        else:
            st.caption(f"Zenit Analytics · build {UI_BUILD_ID}")

        if st.button("Atualizar dados", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    return selected_module, date_preset, time_range, selected_client
