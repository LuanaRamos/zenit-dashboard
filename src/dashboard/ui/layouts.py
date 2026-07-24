import datetime
import streamlit as st
from streamlit_option_menu import option_menu


def render_sidebar() -> tuple[str, str, dict[str, str] | None]:
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna o módulo selecionado.
    """
    with st.sidebar:
        # Dashdark X Logo styling (Cyan and White)
        st.markdown(
            """
            <div style="padding: 10px 0 20px 0; text-align: left; display: flex; align-items: center; gap: 10px;">
                <div style="width: 24px; height: 24px; border-radius: 6px; background: linear-gradient(135deg, #00f0ff, #b026ff);"></div>
                <h2 style="margin:0; font-size: 1.5rem; font-weight: 800; line-height: 1.1; letter-spacing: -0.5px;">
                    <span style="color: #ffffff;">Dashdark</span> <span style="color: #00f0ff;">X</span>
                </h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<h4 style='color: #8B949E; font-size: 0.85rem; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Main Menu</h4>", unsafe_allow_html=True)
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
                "icon": {"color": "#8B949E", "font-size": "18px"},
                "nav-link": {
                    "font-size": "15px",
                    "text-align": "left",
                    "margin": "0px 0px 8px 0px",
                    "--hover-color": "rgba(255, 255, 255, 0.03)",
                    "border-radius": "8px",
                    "padding": "12px 16px",
                    "border": "1px solid transparent",
                    "color": "#8B949E",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "500",
                    "transition": "all 0.2s ease",
                },
                "nav-link-selected": {
                    "background": "rgba(176, 38, 255, 0.1)",
                    "border": "1px solid rgba(176, 38, 255, 0.2)",
                    "box-shadow": "none",
                    "color": "#ffffff",
                    "font-weight": "600"
                },
            }
        )
        
        # Override icon color when selected to Magenta Neon
        st.markdown("""
        <style>
        .nav-item .active i { color: #b026ff !important; }
        </style>
        """, unsafe_allow_html=True)

        # Filtro de Tempo Global
        st.markdown("<br><h4 style='color: #8B949E; font-size: 0.85rem; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;'>Filters</h4>", unsafe_allow_html=True)
        periodo_selecionado = st.selectbox(
            "Período de Análise",
            [
                "Últimos 30 Dias",
                "Máximo (Ads: Sempre | Orgânico: 1 Ano)",
                "Personalizado",
            ],
            label_visibility="collapsed"
        )

        date_preset = "last_30d"
        time_range = None

        if "Máximo" in periodo_selecionado:
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

    return selected_module, date_preset, time_range