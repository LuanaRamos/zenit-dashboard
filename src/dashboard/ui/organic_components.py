import streamlit as st
import pandas as pd
from typing import Any
import plotly.graph_objects as go
from ui.components import render_glass_table, render_glass_chart

def render_organic_overview(
    mapping_data: dict[str, Any],
    total_organic_leads: int,
    total_paid_spend: float
) -> None:
    """Renderiza a aba de Orgânico vs Ads"""
    st.markdown("### 📊 Orgânico (Instagram) vs Ads")
    
    # 1. Totalizadores de Leads
    st.markdown("#### Captação de Leads no Período")
    cols = st.columns(2)
    with cols[0]:
        html_organic = f"""
        <div class="glass-card kpi-card">
            <div style="color: #FFFFFF; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">LEADS ORGÂNICOS (SITE + BIO)</div>
            <div style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.8rem; font-weight: 800; line-height: 1; margin-bottom: 12px; font-family: 'Montserrat', sans-serif;">+{total_organic_leads}</div>
            <div style="color: #8B949E; font-size: 0.8rem;">Custo: R$ 0,00</div>
        </div>
        """
        st.markdown(html_organic, unsafe_allow_html=True)
        
    with cols[1]:
        # Para saber os pagos totais, precisamos injetar? Como os campaigns já vieram pra page, a gente precisaria do sum_paid.
        # Vamos omitir o pago aqui se n\u00e3o tivermos e focar na economia
        economia = total_organic_leads * 5.0 # M\u00e9dia de 5 reais por lead estimado
        html_economy = f"""
        <div class="glass-card kpi-card">
            <div style="color: #FFFFFF; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">ECONOMIA ESTIMADA</div>
            <div style="background: linear-gradient(135deg, #FFD700 0%, #FF8C00 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.8rem; font-weight: 800; line-height: 1; margin-bottom: 12px; font-family: 'Montserrat', sans-serif;">R$ {economia:,.2f}</div>
            <div style="color: #8B949E; font-size: 0.8rem;">Em leads não pagos</div>
        </div>
        """
        st.markdown(html_economy, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Top Posts (Mapping Ads vs Organic)
    st.markdown("#### 🚀 Impulsionamentos Eficientes")
    st.markdown("Mostra quais publicações originadas no feed renderam mais engajamento (orgânico + impulsionado).")

    if not mapping_data:
        st.info("Nenhuma publicação do Instagram impulsionada no período selecionado.")
        return

    data = []
    for post_id, m in mapping_data.items():
        data.append({
            "Post ID": str(post_id), # Poderia ser um link para o instagram se tiv\u00e9ssemos o shortcode
            "Alcance Total": m["reach"],
            "Impressões": m["impressions"],
            "Cliques": m["clicks"],
            "Curtidas": m["likes"],
            "Salvamentos": m["saved"],
            "Compartilhamentos": m["shares"]
        })

    df = pd.DataFrame(data)
    # Ordenar pelos que tem mais engajamento (Curtidas + Salvos + Shares)
    df["Engajamento"] = df["Curtidas"] + df["Salvamentos"] + df["Compartilhamentos"]
    df = df.sort_values(by="Engajamento", ascending=False).drop(columns=["Engajamento"])

    render_glass_table(
        df,
        key="tbl_ig_mapping",
        csv_filename="ig_mapping.csv"
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. Gráfico de Funil de Interações
    st.markdown("#### 🌪️ Funil de Interações das Publicações Impulsionadas")
    total_reach = df["Alcance Total"].sum()
    total_clicks = df["Cliques"].sum()
    total_eng = df["Curtidas"].sum() + df["Salvamentos"].sum() + df["Compartilhamentos"].sum()

    if total_reach > 0:
        funnel_data = dict(
            number=[total_reach, total_clicks, total_eng],
            stage=["Alcance", "Cliques", "Engajamentos (Likes/Salvos)"]
        )
        
        fig = go.Figure(go.Funnel(
            y = funnel_data["stage"],
            x = funnel_data["number"],
            textposition = "inside",
            textinfo = "value+percent initial",
            opacity = 0.9,
            marker = {"color": ["#FFD700", "#FFB300", "#FF8C00"],
                    "line": {"width": [0, 0, 0]}}
        ))
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E2E8F0", family="Inter"),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        render_glass_chart(fig, title="", height=350)
