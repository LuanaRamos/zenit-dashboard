import pandas as pd
import streamlit as st
from schemas.meta import CampaignInsight
import plotly.graph_objects as go

def render_glass_table(df: pd.DataFrame, currency_cols: list[str] = None) -> None:
    currency_cols = currency_cols or []
    html = '<div class="glass-table-container"><table class="glass-table"><thead><tr>'
    for col in df.columns: html += f"<th>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        html += "<tr>"
        for col, val in zip(df.columns, row):
            if col in currency_cols and isinstance(val, (int, float)):
                val_str = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            elif isinstance(val, (int, float)):
                val_str = f"{int(val):,}".replace(",", ".") if isinstance(val, int) or val.is_integer() else f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_str = str(val)
            html += f"<td>{val_str}</td>"
        html += "</tr>"
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)

def render_metric_card(label: str, value: str, delta: str = None, delta_type: str = "green", help_text: str = None) -> None:
    icon_arrow = "bi-arrow-up-right" if delta_type == "green" else "bi-arrow-down-right" if delta_type == "red" else "bi-dash"
    delta_html = f'<span class="metric-pill-{delta_type}" style="margin-left: 12px;"><i class="bi {icon_arrow}"></i> {delta}</span>' if delta else ""
    html = f"""<div class="glass-card" title="{help_text or ''}">
<div style="color: #8B949E; font-size: 0.95rem; font-weight: 500; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">{label}</div>
<div style="display: flex; align-items: baseline;">
<div style="font-size: 2.2rem; font-weight: 700; color: #FFFFFF; line-height: 1; letter-spacing: -0.5px;">{value}</div>
{delta_html}
</div>
</div>"""
    st.markdown(html, unsafe_allow_html=True)

def render_metric_cards(total_spend: float, total_conversions: int, avg_cpa: float) -> None:
    cols = st.columns(3)
    with cols[0]: render_metric_card(label='<i class="bi bi-eye"></i> Investimento Total', value=f"R$ {total_spend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), help_text="Custo total ativas")
    with cols[1]: render_metric_card(label='<i class="bi bi-person"></i> Conversões', value=f"{total_conversions:,}".replace(",", "."), help_text="Leads e mensagens geradas")
    with cols[2]:
        cpa_color = "green" if avg_cpa < 10 else "gold" if avg_cpa < 20 else "red"
        render_metric_card(label='<i class="bi bi-currency-dollar"></i> CPA Médio', value=f"R$ {avg_cpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), delta="Custo", delta_type=cpa_color)

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
    data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Conversas": c.whatsapp_starts, "Custo/Conv": round(c.cost_per_whatsapp, 2), "Alcance": c.impressions} for c in campaigns]
    render_glass_table(pd.DataFrame(data), currency_cols=["Gastos", "Custo/Conv"])
    
    if any(c.whatsapp_starts > 0 for c in campaigns):
        st.markdown("<br><h4 style='color: white; font-weight: 600;'>Desempenho de Custo</h4>", unsafe_allow_html=True)
        chart_data = pd.DataFrame({"Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0], "Custo": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0]})
        
        fig = go.Figure()
        # Restaura a fluidez: linha spline e sombra translucida abaixo do eixo
        fig.add_trace(go.Scatter(
            x=chart_data["Campanha"], 
            y=chart_data["Custo"], 
            mode='lines+markers', 
            line=dict(color='#FFB300', width=4, shape='spline', smoothing=1.3), 
            marker=dict(size=10, color='#FFB300', line=dict(width=2, color='#151515')), 
            fill='tozeroy', 
            fillcolor='rgba(255, 179, 0, 0.15)'
        ))
        
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)", 
            xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#8B949E"), 
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False, color="#8B949E", tickprefix="R$ "), 
            margin=dict(l=0, r=0, t=20, b=0), 
            height=300, 
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

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