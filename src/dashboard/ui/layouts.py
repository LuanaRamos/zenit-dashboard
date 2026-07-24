import datetime
import streamlit as st
from streamlit_option_menu import option_menu


def render_sidebar() -> tuple[str, str, dict[str, str] | None]:
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna o módulo selecionado.
    """
    with st.sidebar:
        st.markdown(
            """
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 30px;">
                <h2 style="margin: 0; color: #ffffff; font-weight: 800; font-size: 1.8rem; letter-spacing: -1px;">
                    <span style="color: #4B93FF; font-size: 1.2rem;">🌐</span> Zenit<br>Dashboard
                </h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<h4 style='color: #9c9ca3; font-size: 0.9rem; margin-bottom: 10px; font-weight: 500;'>Módulos</h4>", unsafe_allow_html=True)
        selected_module = option_menu(
            menu_title=None,
            options=["Visão Geral (Ads)", "Orgânico (Instagram)"],
            icons=["bar-chart-line-fill", "instagram"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "#9c9ca3", "font-size": "20px"},
                "nav-link": {
                    "font-size": "16px",
                    "text-align": "left",
                    "margin-bottom": "8px",
                    "--hover-color": "rgba(30, 30, 36, 0.85)",
                    "border-radius": "0.5rem",
                    "padding": "16px 20px",
                    "border": "1px solid transparent",
                    "color": "#9c9ca3",
                    "font-family": "Inter, sans-serif",
                    "font-weight": "600",
                    "transition": "all 0.2s ease",
                },
                "nav-link-selected": {
                    "background": "rgba(24, 24, 28, 0.7)",
                    "border": "1px solid rgba(255, 179, 0, 0.25)",
                    "box-shadow": "0px 4px 24px rgba(255, 179, 0, 0.12)",
                    "color": "#ffb300",
                    "font-weight": "700"
                },
            }
        )
        
        # Override icon color when selected using a quick CSS hack for the selected icon
        st.markdown("""
        <style>
        .nav-item .active i { color: #ffb300 !important; }
        </style>
        """, unsafe_allow_html=True)

        # Filtro de Tempo Global
        st.markdown("---")
        periodo_selecionado = st.selectbox(
            "Período de Análise",
            [
                "Últimos 30 Dias",
                "Máximo (Ads: Sempre | Orgânico: 1 Ano)",
                "Personalizado",
            ],
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

        st.markdown("---")
        st.caption("Atualizado em tempo real via Meta Graph API v22.0")

        if st.button("🔄 Forçar Atualização"):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.rerun()

    return selected_module, date_preset, time_range
