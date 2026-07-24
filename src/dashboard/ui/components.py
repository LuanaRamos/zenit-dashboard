import pandas as pd
import streamlit as st
from schemas.meta import CampaignInsight


def render_metric_cards(total_spend: float, total_conversions: int, avg_cpa: float) -> None:
    """
    Renderiza uma linha de cards com métricas principais usando st.columns.
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="💰 Investimento Total",
            value=f"R$ {total_spend:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
        )

    with col2:
        st.metric(label="🎯 Total de Conversões (Geral)", value=f"{total_conversions}")

    with col3:
        st.metric(
            label="📉 Custo por Conversão (Geral)",
            value=f"R$ {avg_cpa:,.2f}".replace(",", "X")
            .replace(".", ",")
            .replace("X", "."),
        )


def render_whatsapp_campaigns(campaigns: list[CampaignInsight]) -> None:
    """
    Renderiza tabela para campanhas de Mensagem (WhatsApp / Direct).
    Métricas principais: Conversas Iniciadas e Custo por Conversa.
    """
    st.markdown("### 💬 Campanhas de Mensagens (WhatsApp/Direct)")

    if not campaigns:
        st.info(
            "Você não tem campanhas de mensagens rodando no momento. Ative uma campanha focada em WhatsApp ou Direct para ver os resultados aqui."
        )
        return

    data = []
    for c in campaigns:
        data.append(
            {
                "Campanha": c.campaign_name,
                "Gastos (R$)": round(c.spend, 2),
                "Conversas Iniciadas": c.whatsapp_starts,
                "Custo por Conversa (R$)": round(c.cost_per_whatsapp, 2),
                "Alcance Máx (Imp)": c.impressions,
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Elegant Bar Chart for Cost per Message using Plotly
    if any(c.whatsapp_starts > 0 for c in campaigns):
        st.markdown("**Comparativo: Custo por Conversa**")
        
        import plotly.express as px
        
        chart_data = pd.DataFrame(
            {
                "Campanha": [
                    c.campaign_name for c in campaigns if c.whatsapp_starts > 0
                ],
                "Custo (R$)": [
                    c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0
                ],
            }
        )
        
        fig = px.bar(
            chart_data,
            x="Campanha",
            y="Custo (R$)",
            text="Custo (R$)",
            color_discrete_sequence=["#25D366"]
        )
        fig.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title="",
            yaxis_title="Custo (R$)",
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def render_profile_campaigns(campaigns: list[CampaignInsight]) -> None:
    """
    Renderiza tabela para campanhas focadas em Tráfego (Visitas ao Perfil / Seguidores).
    Métricas principais: Visitas ao Perfil e Seguidores Gerados.
    """
    st.markdown("### 📸 Campanhas de Seguidores e Visitas ao Perfil")

    if not campaigns:
        st.info(
            "Você não teve campanhas de Tráfego focadas em atrair seguidores ou visitas no período. Crie uma para começar a medir."
        )
        return

    data = []
    for c in campaigns:
        data.append(
            {
                "Campanha": c.campaign_name,
                "Gastos (R$)": round(c.spend, 2),
                "Seguidores Gerados": c.instagram_follows,
                "Custo por Seguidor (R$)": round(c.cost_per_follower, 2),
                "Visitas ao Perfil": c.profile_visits,
                "Custo por Visita (R$)": round(c.cost_per_profile_visit, 2),
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_general_campaigns(
    campaigns: list[CampaignInsight], title: str = "Outras Campanhas"
) -> None:
    """
    Renderiza tabela genérica (Fallback) para outras campanhas (Reconhecimento, Cadastros, etc).
    """
    st.markdown(f"### 🌐 {title}")

    if not campaigns:
        st.info(
            "Não há campanhas com outros objetivos (como Cadastros) ativas no período. Teste novos formatos para expandir sua estratégia."
        )
        return

    data = []
    for c in campaigns:
        data.append(
            {
                "Campanha": c.campaign_name,
                "Objetivo": c.objective_friendly,
                "Gastos (R$)": round(c.spend, 2),
                "Impressões": c.impressions,
                "Cliques": c.clicks,
                "Leads (Site)": c.leads,
                "CPL (R$)": round(c.cpl, 2),
                "CPM (R$)": round(c.cpm, 2),
            }
        )

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
