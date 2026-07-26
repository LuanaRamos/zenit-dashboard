import datetime
import streamlit as st
from streamlit_option_menu import option_menu


def render_sidebar() -> tuple[str, str, dict[str, str] | None, "ClientConfig"]:
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna (modulo_selecionado, date_preset, time_range, client_config).
    """
    with st.sidebar:
        # Zenit Logo styling (Gold and Dark)
        st.markdown(
            """
            <div style="padding: 10px 0 24px 0; text-align: left; display: flex; align-items: center; gap: 12px;">
                <div style="width: 26px; height: 26px; border-radius: 6px; background: linear-gradient(135deg, #FFB300, #FF6F00); box-shadow: 0 4px 12px rgba(255, 179, 0, 0.3);"></div>
                <h2 style="margin:0; font-size: 1.4rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.5px;">
                    <span style="color: #ffffff;">Zenit</span><span style="color: #FFB300;">Analytics</span>
                </h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        from core.config import settings
        clients = settings.get_clients()
        if not clients:
            st.error("⚠️ Nenhum cliente configurado no sistema (CLIENTS_JSON).")
            st.stop()

        client_names = [c.name for c in clients]
        if "selected_client_name" not in st.session_state:
            st.session_state["selected_client_name"] = client_names[0]
        
        # Garante que o cliente salvo na sessao ainda existe na config
        if st.session_state["selected_client_name"] not in client_names:
            st.session_state["selected_client_name"] = client_names[0]

        st.markdown("<h4 style='color: #8B949E; font-size: 0.75rem; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Cliente</h4>", unsafe_allow_html=True)
        
        def on_client_change():
            # Limpa o cache ao trocar de cliente
            st.cache_data.clear()

        selected_client_name = st.selectbox(
            "Selecione o Cliente",
            options=client_names,
            index=client_names.index(st.session_state["selected_client_name"]),
            key="selected_client_name",
            label_visibility="collapsed",
            on_change=on_client_change,
        )
        
        selected_client = next(c for c in clients if c.name == selected_client_name)

        st.markdown("<br><h4 style='color: #8B949E; font-size: 0.75rem; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Main Menu</h4>", unsafe_allow_html=True)
        selected_module = option_menu(
            menu_title=None,
            options=["Visão Geral (Ads)", "Orgânico (Instagram)"],
            icons=["bar-chart-line-fill", "instagram"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {
                    "padding": "0!important", 
                    "background-color": "transparent",
                },
                "icon": {"color": "#8B949E", "font-size": "16px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px 0px 6px 0px",
                    "--hover-color": "rgba(255, 255, 255, 0.02)",
                    "border-radius": "6px",
                    "padding": "10px 14px",
                    "border": "1px solid transparent",
                    "color": "#8B949E",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "500",
                    "transition": "all 0.2s ease",
                },
                "nav-link-selected": {
                    "background": "rgba(255, 179, 0, 0.08)",
                    "border": "1px solid rgba(255, 179, 0, 0.15)",
                    "box-shadow": "none",
                    "color": "#FFB300",
                    "font-weight": "600"
                },
            }
        )
        
        # Override icon color when selected to Zenit Gold
        st.markdown("""
        <style>
        .nav-item .active i { color: #FFB300 !important; }
        </style>
        """, unsafe_allow_html=True)

        # Filtro de Tempo Global
        st.markdown("<br><h4 style='color: #8B949E; font-size: 0.85rem; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Filters</h4>", unsafe_allow_html=True)
        periodo_selecionado = st.selectbox(
            "Período de Análise",
            [
                "Últimos 30 Dias",
                "Desde o início (Sempre)",
                "Personalizado",
            ],
            label_visibility="collapsed"
        )

        date_preset = "last_30d"
        time_range = None

        if "Desde o início" in periodo_selecionado:
            date_preset = "maximum"
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
                    min_value=start_date, # Garantir que não selecione antes da inicial
                    max_value=max_date,
                    format="DD/MM/YYYY",
                )

            if start_date and end_date:
                if start_date <= end_date:
                    delta = end_date - start_date
                    # Meta API restricts custom time_range to ~37 months (approx 1125 days).
                    if delta.days > 1125:
                        st.warning("⚠️ A API da Meta permite um intervalo personalizado máximo de 37 meses (aprox. 3 anos). Para ver todo o histórico, selecione 'Desde o início' no filtro acima.")
                        st.stop()
                    else:
                        time_range = {
                            "since": start_date.strftime("%Y-%m-%d"),
                            "until": end_date.strftime("%Y-%m-%d"),
                        }
                else:
                    st.warning("A data inicial não pode ser maior que a data final.")
                    st.stop()
            else:
                st.warning("Selecione a data inicial e final.")
                st.stop()

        st.markdown("<div style='margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 20px;'></div>", unsafe_allow_html=True)
        st.caption("Atualizado via Meta Graph API v22.0")

        if st.button("🔄 Forçar Atualização", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    # Trigger reload
    return selected_module, date_preset, time_range, selected_client