import datetime

import streamlit as st


def render_sidebar() -> tuple[str, str, dict[str, str] | None]:
    """
    Configura e renderiza a barra lateral de navegação e filtros.
    Retorna o módulo selecionado.
    """
    with st.sidebar:
        st.markdown("## 🌐 Meta Platforms")
        st.title("Zenit Dashboard")
        st.markdown("---")

        # O rádio permite clicar e trocar de tela
        selected_module = st.radio(
            "Módulos", ["📈 Visão Geral (Ads)", "📱 Orgânico (Instagram)"]
        )

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
