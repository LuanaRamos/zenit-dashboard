import pandas as pd
import streamlit as st
from schemas.meta import CampaignInsight
import plotly.graph_objects as go

def render_glass_table(df: pd.DataFrame, currency_cols: list[str] = None) -> None:
    currency_cols = currency_cols or []
    
    # Configure columns
    column_config = {}
    for col in df.columns:
        if col in currency_cols:
            column_config[col] = st.column_config.NumberColumn(
                col, format="$,.2f"
            )
        else:
            if pd.api.types.is_numeric_dtype(df[col]):
                column_config[col] = st.column_config.NumberColumn(
                    col, format=",d"
                )
    
    # Render with Streamlit's native dataframe which supports sorting and dark mode
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config=column_config
    )

def render_metric_card(label: str, value: str, delta: str = None, delta_type: str = "normal", help_text: str = None) -> None:
    help_html = f"<div style='font-size: 0.75rem; color: #8B949E; margin-top: 4px;'>{help_text}</div>" if help_text else ""
    
    delta_html = ""
    if delta:
        if delta_type == "green":
            delta_html = f"<div class='metric-pill-green'>↑ {delta}</div>"
        elif delta_type == "gold":
            delta_html = f"<div class='metric-pill-gold'>↑ {delta}</div>"
        elif delta_type == "red":
            delta_html = f"<div class='metric-pill-red'>↓ {delta}</div>"
        else:
            delta_html = f"<div style='color: #8B949E; font-size: 0.8rem; margin-top: 4px;'>{delta}</div>"
            
    html = (
        '<div class="glass-card">'
        f'<div style="color: #8B949E; font-size: 0.85rem; font-weight: 500; margin-bottom: 8px;">{label}</div>'
        f'<div style="color: #ffffff; font-size: 1.8rem; font-weight: 700; margin-bottom: 8px;">{value}</div>'
        f'{delta_html}'
        f'{help_html}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def render_metric_cards(total_spend: float, total_conversions: float, avg_cpa: float) -> None:
    cols = st.columns(3)
    with cols[0]:
        render_metric_card(
            label='<i class="bi bi-wallet2"></i> Investimento Total',
            value=f"R$ {total_spend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            delta="Orçamento em dia",
            delta_type="green"
        )
    with cols[1]:
        render_metric_card(
            label='<i class="bi bi-bullseye"></i> Total de Conversões',
            value=f"{int(total_conversions):,}".replace(",", "."),
            help_text="Mensagens WhatsApp + Cadastros"
        )
    with cols[2]:
        cpa_color = "green" if avg_cpa < 10 else "gold" if avg_cpa < 20 else "red"
        render_metric_card(
            label='<i class="bi bi-graph-down-arrow"></i> Custo por Conversão (CPA)',
            value=f"R$ {avg_cpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            delta="Custo atual",
            delta_type=cpa_color
        )

def render_objective_pie_chart(campaigns: list[CampaignInsight]) -> None:
    st.markdown("<h4 style='color: #ffffff; font-weight: 600; margin-top: 1rem; margin-bottom: 1rem;'>Distribuição de Investimento</h4>", unsafe_allow_html=True)
    spend_by_obj = {}
    for c in campaigns:
        obj = c.objective_friendly
        spend_by_obj[obj] = spend_by_obj.get(obj, 0.0) + c.spend
    labels, values = list(spend_by_obj.keys()), list(spend_by_obj.values())
    if not labels or sum(values) == 0:
        st.info("Não há dados de investimento suficientes para o gráfico.")
        return
    
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.75, marker={"colors": ["#FFB300", "#FFC107", "#E5A000", "#FFFFFF", "#4A4A4A"]})])
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#8B949E"}, margin={"l": 0, "r": 0, "t": 20, "b": 0}, showlegend=True, legend={"orientation": "h", "y": -0.1}, height=300)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_whatsapp_campaigns(campaigns: list[CampaignInsight]) -> None:
    st.markdown("### Campanhas de Mensagens (WhatsApp/Direct)")
    if not campaigns: return
    
    # Bento Grid Layout
    col1, col2 = st.columns([1.1, 1])
    
    with col1:
        data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Conversas": c.whatsapp_starts, "Custo/Conv": round(c.cost_per_whatsapp, 2), "Alcance": c.impressions} for c in campaigns]
        render_glass_table(pd.DataFrame(data), currency_cols=["Gastos", "Custo/Conv"])
    
    with col2:
        if any(c.whatsapp_starts > 0 for c in campaigns):
            chart_data = pd.DataFrame({"Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0], "Custo": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0]})
            
            fig = go.Figure()
            # Alta fluidez: linha fina e sombra suave
            fig.add_trace(go.Scatter(
                x=chart_data["Campanha"], 
                y=chart_data["Custo"], 
                mode='lines+markers', 
                line=dict(color='#FFB300', width=2, shape='spline', smoothing=1.3), 
                marker=dict(size=6, color='#FFB300', line=dict(width=1, color='#151515')), 
                fill='tozeroy', 
                fillcolor='rgba(255, 179, 0, 0.08)'
            ))
            
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#8B949E", tickfont=dict(size=10)), 
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)", zeroline=False, color="#8B949E", tickprefix="R$ ", tickfont=dict(size=10)), 
                margin=dict(l=0, r=0, t=10, b=0), 
                height=250, 
                hovermode="x unified"
            )
            st.markdown("<div class='glass-card' style='padding: 16px !important;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color: #8B949E; font-size: 0.85rem; margin-top: 0; margin-bottom: 12px; font-weight: 500;'>Desempenho de Custo</h4>", unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)

def render_profile_campaigns(campaigns: list[CampaignInsight]) -> None:
    st.markdown("### Campanhas de Seguidores e Visitas")
    if not campaigns: return
    data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Cliques": c.clicks, "CPC": round(c.cpc, 2), "Visitas": c.profile_visits, "Seguidores": c.instagram_follows, "Custo/Seg": round(c.cost_per_follower, 2)} for c in campaigns]
    render_glass_table(pd.DataFrame(data), currency_cols=["Gastos", "CPC", "Custo/Seg"])

def render_general_campaigns(campaigns: list[CampaignInsight], title: str = "Outras Campanhas") -> None:
    st.markdown(f"### {title}")
    if not campaigns: return
    data = [{"Campanha": c.campaign_name, "Objetivo": c.objective_friendly, "Gastos": round(c.spend, 2), "Impr": c.impressions, "Cliques": c.clicks, "CPL": round(c.cpl, 2), "CPM": round(c.cpm, 2)} for c in campaigns]
    render_glass_table(pd.DataFrame(data), currency_cols=["Gastos", "CPL", "CPM"])