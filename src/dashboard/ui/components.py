import pandas as pd
import streamlit as st
from schemas.meta import CampaignInsight
import plotly.graph_objects as go


def render_glass_table(df: pd.DataFrame, currency_cols: list[str] = None) -> None:
    """
    Renderiza uma tabela HTML customizada com estilo glassmorphism.
    Garante que colunas numéricas tenham a formatação correta e usa currency_cols
    para formatar colunas monetárias de forma explícita.
    """
    currency_cols = currency_cols or []
    
    html = '<div class="glass-table-container"><table class="glass-table">'
    
    # Headers
    html += "<thead><tr>"
    for col in df.columns:
        html += f"<th>{col}</th>"
    html += "</tr></thead>"
    
    # Body
    html += "<tbody>"
    for _, row in df.iterrows():
        html += "<tr>"
        for col, val in zip(df.columns, row):
            # Check explicit currency formatting
            if col in currency_cols and isinstance(val, (int, float)):
                val_str = f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            elif isinstance(val, (int, float)):
                # Normal number format
                if isinstance(val, int) or val.is_integer():
                    val_str = f"{int(val):,}".replace(",", ".")
                else:
                    val_str = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            else:
                val_str = str(val)
                
            html += f"<td>{val_str}</td>"
        html += "</tr>"
    
    html += "</tbody></table></div>"
    st.markdown(html, unsafe_allow_html=True)


def render_metric_card(label: str, value: str, delta: str = None, delta_type: str = "green", help_text: str = None) -> None:
    """Renderiza um card de métrica unificado."""
    delta_html = f'<div style="margin-top: 0.2rem;"><span class="metric-pill-{delta_type}">{delta}</span></div>' if delta else ""
    help_html = f'<div class="metric-card-title" style="margin-top: 0.2rem;">{help_text}</div>' if help_text else ""
    
    st.markdown(f"""<div class="glass-card">
        <div class="metric-card-title">{label}</div>
        <div class="metric-card-value">{value}</div>
        {delta_html}
        {help_html}
    </div>""", unsafe_allow_html=True)

def render_metric_cards(total_spend: float, total_conversions: int, avg_cpa: float) -> None:
    """
    Renderiza uma linha de cards com métricas principais usando glass-cards premium.
    """
    cols = st.columns(3)
    
    with cols[0]:
        render_metric_card(
            label='<i class="bi bi-currency-dollar"></i> Investimento Total',
            value=f"R$ {total_spend:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            help_text="Custo total das campanhas ativas"
        )

    with cols[1]:
        render_metric_card(
            label='<i class="bi bi-lightning-charge"></i> Conversões',
            value=f"{total_conversions:,}".replace(",", "."),
            help_text="Leads e mensagens geradas"
        )

    with cols[2]:
        cpa_color = "green" if avg_cpa < 10 else "gold" if avg_cpa < 20 else "red"
        render_metric_card(
            label='<i class="bi bi-graph-down"></i> CPA Médio',
            value=f"R$ {avg_cpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            delta="Custo por conversão",
            delta_type=cpa_color
        )


def render_objective_pie_chart(campaigns: list[CampaignInsight]) -> None:
    """Renderiza um gráfico de pizza mostrando a distribuição de gastos por objetivo da campanha."""
    st.markdown("<br>#### 🎯 Distribuição de Investimento por Objetivo", unsafe_allow_html=True)
    
    spend_by_obj = {}
    for c in campaigns:
        obj = c.objective_friendly
        spend_by_obj[obj] = spend_by_obj.get(obj, 0.0) + c.spend
        
    labels = list(spend_by_obj.keys())
    values = list(spend_by_obj.values())
    
    if not labels or sum(values) == 0:
        st.info("Não há dados de investimento suficientes para gerar o gráfico.")
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.6,
                marker={"colors": ["#ffb300", "#5af8fb", "#1877f2", "#e89a00", "#10B981", "#8B5CF6"]},
            )
        ]
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#FFFFFF"},
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        showlegend=True,
        legend={"orientation": "h", "y": -0.1},
        height=320
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


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
    render_glass_table(df, currency_cols=["Gastos (R$)", "Custo por Conversa (R$)"])

    # Premium Area Chart for Cost per Message using Plotly
    if any(c.whatsapp_starts > 0 for c in campaigns):
        st.markdown("<br><h4 style='color: white; font-weight: 600;'>Desempenho de Custo</h4>", unsafe_allow_html=True)
        
        chart_data = pd.DataFrame(
            {
                "Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0],
                "Custo (R$)": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0],
            }
        )
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=chart_data["Campanha"],
            y=chart_data["Custo (R$)"],
            mode='lines+markers',
            line=dict(color='#FDBA21', width=5, shape='spline', smoothing=1.3), # Bolder line
            marker=dict(size=14, color='#07090E', line=dict(width=3, color='#FDBA21')), # Bolder markers
            fill='tozeroy',
            fillcolor='rgba(253, 186, 33, 0.3)' # Bolder fill (glass)
        ))
        
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#8E95A3"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False, color="#8E95A3", tickprefix="R$ "),
            margin=dict(l=0, r=0, t=20, b=0),
            height=320,
            hovermode="x unified"
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
                "Cliques no Link": c.clicks,
                "Custo por Clique (R$)": round(c.cpc, 2),
                "Visitas ao Perfil": c.profile_visits,
                "Seguidores Gerados": c.instagram_follows,
                "Custo por Seguidor (R$)": round(c.cost_per_follower, 2),
            }
        )

    df = pd.DataFrame(data)
    render_glass_table(df, currency_cols=["Gastos (R$)", "Custo por Clique (R$)", "Custo por Seguidor (R$)"])


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
    render_glass_table(df, currency_cols=["Gastos (R$)", "CPL (R$)", "CPM (R$)"])
