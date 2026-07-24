import streamlit as st
from schemas.meta import CampaignInsight
import pandas as pd
from typing import List

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
            label="🎯 Total de Leads (Geral)", 
            value=f"{total_leads}"
        )
    
    with col3:
        st.metric(
            label="📉 Custo por Lead (Geral)", 
            value=f"R$ {avg_cpl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )

def render_whatsapp_campaigns(campaigns: List[CampaignInsight]):
    """
    Renderiza tabela para campanhas de Mensagem (WhatsApp / Direct).
    Métricas principais: Conversas Iniciadas e Custo por Conversa.
    """
    st.markdown("### 💬 Campanhas de Mensagens (WhatsApp/Direct)")
    
    if not campaigns:
        st.info("Você não tem campanhas de mensagens rodando no momento. Ative uma campanha focada em WhatsApp ou Direct para ver os resultados aqui.")
        return
        
    data = []
    for c in campaigns:
        data.append({
            "Campanha": c.campaign_name,
            "Gastos (R$)": round(c.spend, 2),
            "Conversas Iniciadas": c.whatsapp_starts,
            "Custo por Conversa (R$)": round(c.cost_per_whatsapp, 2),
            "Alcance Máx (Imp)": c.impressions
        })
        
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Simple Bar Chart for Cost per Message
    if any(c.whatsapp_starts > 0 for c in campaigns):
        st.markdown("**Comparativo: Custo por Conversa**")
        chart_data = pd.DataFrame({
            "Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0],
            "Custo (R$)": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0]
        }).set_index("Campanha")
        
        st.bar_chart(chart_data, y="Custo (R$)", color="#25D366")


def render_profile_campaigns(campaigns: List[CampaignInsight]):
    """
    Renderiza tabela para campanhas focadas em Tráfego (Visitas ao Perfil / Seguidores).
    Métricas principais: Visitas ao Perfil e Seguidores Gerados.
    """
    st.markdown("### 📸 Campanhas de Seguidores e Visitas ao Perfil")
    
    if not campaigns:
        st.info("Você não teve campanhas de Tráfego focadas em atrair seguidores ou visitas no período. Crie uma para começar a medir.")
        return
        
    data = []
    for c in campaigns:
        data.append({
            "Campanha": c.campaign_name,
            "Gastos (R$)": round(c.spend, 2),
            "Seguidores Gerados": c.instagram_follows,
            "Custo por Seguidor (R$)": round(c.cost_per_follower, 2),
            "Visitas ao Perfil": c.profile_visits,
            "Custo por Visita (R$)": round(c.cost_per_profile_visit, 2)
        })
        
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_general_campaigns(campaigns: List[CampaignInsight], title: str = "Outras Campanhas"):
    """
    Renderiza tabela genérica (Fallback) para outras campanhas (Reconhecimento, Cadastros, etc).
    """
    st.markdown(f"### 🌐 {title}")
    
    if not campaigns:
        st.info("Não há campanhas com outros objetivos (como Cadastros) ativas no período. Teste novos formatos para expandir sua estratégia.")
        return
        
    data = []
    for c in campaigns:
        data.append({
            "Campanha": c.campaign_name,
            "Objetivo": c.objective_friendly,
            "Gastos (R$)": round(c.spend, 2),
            "Impressões": c.impressions,
            "Cliques": c.clicks,
            "Leads (Site)": c.leads,
            "CPL (R$)": round(c.cpl, 2),
            "CPM (R$)": round(c.cpm, 2)
        })
        
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
