import streamlit as st
from schemas.meta import CampaignInsight

def render_metric_cards(total_spend: float, total_leads: int, avg_cpl: float):
    """
    Renderiza uma linha de cards com métricas principais usando st.columns.
    """
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💰 Investimento Total", 
            value=f"R$ {total_spend:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    
    with col2:
        st.metric(
            label="🎯 Total de Leads", 
            value=f"{total_leads}"
        )
    
    with col3:
        st.metric(
            label="📉 Custo por Lead (CPL)", 
            value=f"R$ {avg_cpl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

def render_campaign_table(campaigns: list[CampaignInsight]):
    """
    Renderiza uma tabela iterativa com os dados brutos de campanha.
    """
    st.subheader("📊 Performance por Campanha")
    
    if not campaigns:
        st.info("Nenhuma campanha ativa encontrada para exibir.")
        return

    # Convert to list of dicts for Streamlit dataframe
    data = []
    for c in campaigns:
        data.append({
            "Campanha": c.campaign_name,
            "Gastos (R$)": round(c.spend, 2),
            "Impressões": c.impressions,
            "Cliques": c.clicks,
            "Leads": c.leads,
            "CPL (R$)": round(c.cpl, 2),
            "CPC (R$)": round(c.cpc, 2)
        })
    
    st.dataframe(
        data, 
        use_container_width=True,
        hide_index=True
    )