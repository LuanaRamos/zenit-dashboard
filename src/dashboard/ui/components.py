import base64
import html as html_lib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from schemas.meta import CampaignInsight
import plotly.graph_objects as go
from pathlib import Path

def get_global_css() -> str:
    """Carrega o CSS global para injetar nos iframes, garantindo estilo único."""
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def _format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _format_int(value: float) -> str:
    return f"{int(round(value)):,}".replace(",", ".")

def render_glass_table(
    df: pd.DataFrame,
    currency_cols: list[str] = None,
    link_col: str = None,
    link_label: str = "Ver",
    key: str = "glass_table",
    csv_filename: str = "tabela.csv",
) -> None:
    """Renderiza a tabela custom (.glass-table) do design system: sem depender de nenhum
    widget nativo do Streamlit (nem st.dataframe, nem st.download_button). Ordenação por
    clique no cabeçalho e download do CSV completo são feitos em HTML/JS puro, dentro do
    mesmo iframe isolado — 100% estilizável."""
    currency_cols = currency_cols or []

    if df.empty:
        return

    display_cols = [c for c in df.columns if c != link_col]

    thead_cells = []
    for i, col in enumerate(display_cols):
        col_type = "num" if pd.api.types.is_numeric_dtype(df[col]) else "text"
        thead_cells.append(
            f'<th data-idx="{i}" data-type="{col_type}">'
            f'{html_lib.escape(str(col))}<span class="sort-arrow"></span></th>'
        )
    if link_col:
        thead_cells.append("<th></th>")

    rows_html = []
    for _, row in df.iterrows():
        cells = []
        for col in display_cols:
            val = row[col]
            if col in currency_cols:
                raw = float(val)
                display_val = _format_brl(raw)
                sort_val = raw
            elif pd.api.types.is_number(val):
                raw = float(val)
                display_val = _format_int(val)
                sort_val = raw
            else:
                display_val = html_lib.escape(str(val))
                sort_val = str(val).lower()
            cells.append(f'<td data-sort="{html_lib.escape(str(sort_val))}">{display_val}</td>')
        if link_col:
            url = row.get(link_col)
            if pd.notna(url) and url:
                cells.append(
                    f'<td data-sort=""><a href="{html_lib.escape(str(url))}" target="_blank" '
                    f'class="glass-link">{html_lib.escape(link_label)}</a></td>'
                )
            else:
                cells.append('<td data-sort="">-</td>')
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    n_rows = len(df)
    # Dá bastante respiro para cada linha (50px) + cabeçalho + padding
    body_height = min(50 * (n_rows + 1) + 40, 500)
    toolbar_height = 50
    # Adiciona 40px extras de folga para o iframe nunca criar barra de rolagem nativa
    iframe_height = body_height + toolbar_height + 40

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    csv_b64 = base64.b64encode(csv_bytes).decode("ascii")

    table_html = f"""
    <html>
    <head>
    <style>
        html, body {{ margin: 0; padding: 0; background: transparent !important; font-family: 'Inter', sans-serif; overflow: hidden; }}
        {get_global_css()}
    </style>
    </head>
    <body>
        <div class="glass-table-container">
            <table class="glass-table" id="{key}">
                <thead><tr>{''.join(thead_cells)}</tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
        </div>
        <a class="glass-download" download="{html_lib.escape(csv_filename)}"
           href="data:text/csv;charset=utf-8;base64,{csv_b64}">⬇ Baixar CSV completo</a>
        <script>
            (function() {{
                const table = document.getElementById("{key}");
                const headers = table.querySelectorAll("th[data-idx]");
                let sortAsc = {{}};
                headers.forEach(function(th) {{
                    th.addEventListener("click", function() {{
                        const idx = parseInt(th.getAttribute("data-idx"));
                        const type = th.getAttribute("data-type");
                        const asc = !sortAsc[idx];
                        sortAsc = {{}};
                        sortAsc[idx] = asc;
                        const tbody = table.querySelector("tbody");
                        const rows = Array.from(tbody.querySelectorAll("tr"));
                        rows.sort(function(a, b) {{
                            const av = a.children[idx].getAttribute("data-sort");
                            const bv = b.children[idx].getAttribute("data-sort");
                            if (type === "num") {{
                                return asc ? parseFloat(av) - parseFloat(bv) : parseFloat(bv) - parseFloat(av);
                            }}
                            return asc ? av.localeCompare(bv) : bv.localeCompare(av);
                        }});
                        headers.forEach(function(h) {{ h.querySelector(".sort-arrow").textContent = ""; }});
                        th.querySelector(".sort-arrow").textContent = asc ? "▲" : "▼";
                        rows.forEach(function(r) {{ tbody.appendChild(r); }});
                    }});
                }});
            }})();
        </script>
    </body>
    </html>
    """
    components.html(table_html, height=iframe_height, scrolling=False)

def render_metric_card(label: str, value: str, subtext: str = None, help_text: str = None) -> None:
    sub_html = f"<div style='color: #FFFFFF; font-size: 0.95rem; font-weight: 500; margin-bottom: 12px;'>{subtext}</div>" if subtext else ""
    help_html = f"<div style='font-size: 0.75rem; color: #8B949E; font-weight: 400;'>{help_text}</div>" if help_text else ""
    
    html = (
        '<div class="glass-card kpi-card">'
        f'<div style="color: #FFFFFF; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;">{label}</div>'
        f'<div style="background: linear-gradient(135deg, #FFD700 0%, #FF8C00 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.8rem; font-weight: 800; line-height: 1; margin-bottom: 12px; font-family: \'Montserrat\', sans-serif; display: inline-block;">{value}</div>'
        f'{sub_html}'
        f'{help_html}'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def render_metric_cards(total_spend: float, total_conversions: float, avg_cpa: float) -> None:
    cols = st.columns(3)
    with cols[0]:
        # Formata sem casas decimais para impacto visual, assim como R$ 284 investidos do exemplo
        spend_fmt = f"R$ {int(total_spend):,}".replace(",", ".")
        render_metric_card(
            label='INVESTIMENTO TOTAL',
            value=spend_fmt,
            subtext="em anúncios no período",
            help_text="Orçamento distribuído"
        )
    with cols[1]:
        conv_fmt = f"+{int(total_conversions):,}".replace(",", ".")
        render_metric_card(
            label='TOTAL DE CONVERSÕES',
            value=conv_fmt,
            subtext="novos leads e contatos",
            help_text="Tráfego Pago + Orgânico"
        )
    with cols[2]:
        cpa_fmt = f"R$ {avg_cpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        render_metric_card(
            label='CUSTO POR CONVERSÃO',
            value=cpa_fmt,
            subtext="média de CPA geral",
            help_text="Performance do período"
        )

def render_glass_chart(fig: go.Figure, title: str = None, height: int = 400) -> None:
    """Isola completamente o gráfico Plotly em um iframe HTML para evitar barras de rolagem
    e bugs de padding do Streamlit. Renderiza o glassmorphism nativamente no HTML."""
    plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})
    title_html = f"<div class='title'>{title}</div>" if title else ""
    
    html_content = f"""
    <html>
    <head>
    <style>
        html, body {{ margin: 0; padding: 0; overflow: hidden; background: transparent !important; font-family: 'Inter', sans-serif; }}
        {get_global_css()}
        /* Card isolation specifics for chart wrapper to ensure exact height fitting */
        .glass-card {{ height: 100%; box-sizing: border-box; }}
    </style>
    </head>
    <body>
        <div class="glass-card">
            {title_html}
            <div style="width: 100%; height: calc(100% - {'28px' if title else '0px'}); display: flex; justify-content: center; align-items: center;">
                {plotly_html}
            </div>
        </div>
    </body>
    </html>
    """
    components.html(html_content, height=height, scrolling=False)

def render_objective_pie_chart(campaigns: list[CampaignInsight]) -> None:
    spend_by_obj = {}
    for c in campaigns:
        obj = c.objective_friendly
        spend_by_obj[obj] = spend_by_obj.get(obj, 0.0) + c.spend
    labels, values = list(spend_by_obj.keys()), list(spend_by_obj.values())
    if not labels or sum(values) == 0:
        st.info("Não há dados de investimento suficientes para o gráfico.")
        return
    
    fig = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        marker=dict(
            colors=["#FFB300", "#FFC107", "#E5A000", "#FFFFFF", "#4A4A4A"],
            line=dict(color='rgba(0,0,0,0)', width=0)
        ),
        textinfo='none',
        hoverinfo='label+percent+value',
        hovertemplate='<b>%{label}</b><br>Gastos: %{value:$.2f}<br>Proporção: %{percent}<extra></extra>'
    )])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font={"color": "#8B949E", "family": "Inter, sans-serif"}, 
        margin={"l": 0, "r": 0, "t": 10, "b": 60},  # Margem bottom bem maior para a legenda caber
        showlegend=True, 
        legend={"orientation": "h", "y": -0.25, "font": {"size": 11}}, 
        height=400,  # Aumenta a altura interna do Plotly
        hoverlabel=dict(bgcolor="rgba(20,20,20,0.9)", bordercolor="#FFB300", font=dict(family="Montserrat", size=13))
    )
    # Mesma altura para os dois gráficos
    render_glass_chart(fig, title="Distribuição de Investimento", height=460)

def render_whatsapp_cost_chart(campaigns: list[CampaignInsight]) -> None:
    if not campaigns: return
    
    if any(c.whatsapp_starts > 0 for c in campaigns):
        chart_data = pd.DataFrame({"Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0], "Custo": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0]})
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_data["Campanha"], 
            y=chart_data["Custo"],
            width=0.15,
            marker=dict(
                color='#FFB300',
                line=dict(color='rgba(255, 179, 0, 0.8)', width=0),
                cornerradius="50%"
            ),
            text=chart_data["Custo"].apply(lambda x: f"R$ {x:,.2f}".replace(".", ",")),
            textposition='outside',
            textfont=dict(color="#E2E8F0", family="Inter", size=11, weight="bold"),
            hoverinfo='y+x'
        ))
        
        fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)", 
            xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#8B949E", tickfont=dict(size=10, family="Inter")), 
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)", gridwidth=1, zeroline=True, zerolinecolor="rgba(255,255,255,0.1)", rangemode="tozero", color="#8B949E", tickprefix="R$ ", tickfont=dict(size=10, family="Inter")), 
            margin=dict(l=0, r=0, t=10, b=40), # Espaço embaixo para a label X
            height=400, 
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#0B1739", font_size=12, font_family="Inter", bordercolor="#7E89AC")
        )
        # Mesma altura para os dois gráficos
        render_glass_chart(fig, title="Desempenho de Custo", height=460)

def render_whatsapp_campaigns(campaigns: list[CampaignInsight]) -> None:
    st.markdown("### Campanhas de Mensagens (WhatsApp/Direct)")
    if not campaigns: return
    
    data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Conversas": c.whatsapp_starts, "Custo/Conv": round(c.cost_per_whatsapp, 2), "Alcance": c.impressions} for c in campaigns]
    render_glass_table(
        pd.DataFrame(data),
        currency_cols=["Gastos", "Custo/Conv"],
        key="tbl_whatsapp",
        csv_filename="campanhas_whatsapp.csv",
    )

def render_profile_campaigns(campaigns: list[CampaignInsight]) -> None:
    st.markdown("### Campanhas de Seguidores e Visitas")
    if not campaigns: return
    data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Cliques": c.clicks, "CPC": round(c.cpc, 2), "Visitas": c.profile_visits, "Seguidores": c.instagram_follows, "Custo/Seg": round(c.cost_per_follower, 2)} for c in campaigns]
    render_glass_table(
        pd.DataFrame(data),
        currency_cols=["Gastos", "CPC", "Custo/Seg"],
        key="tbl_profile",
        csv_filename="campanhas_seguidores_visitas.csv",
    )

def render_general_campaigns(campaigns: list[CampaignInsight], title: str = "Outras Campanhas") -> None:
    st.markdown(f"### {title}")
    if not campaigns: return
    data = [{"Campanha": c.campaign_name, "Objetivo": c.objective_friendly, "Gastos": round(c.spend, 2), "Impr": c.impressions, "Cliques": c.clicks, "CPL": round(c.cpl, 2), "CPM": round(c.cpm, 2)} for c in campaigns]
    slug = title.lower().replace(" ", "_")
    render_glass_table(
        pd.DataFrame(data),
        currency_cols=["Gastos", "CPL", "CPM"],
        key=f"tbl_{slug}",
        csv_filename=f"{slug}.csv",
    )
