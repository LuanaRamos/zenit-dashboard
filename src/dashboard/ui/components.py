import base64
import html as html_lib
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from schemas.meta import CampaignInsight
import plotly.graph_objects as go

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
    body_height = min(38 * (n_rows + 1) + 20, 480)
    toolbar_height = 40
    iframe_height = body_height + toolbar_height + 16

    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    csv_b64 = base64.b64encode(csv_bytes).decode("ascii")

    table_html = f"""
    <html>
    <head>
    <style>
        html, body {{ margin: 0; padding: 0; background: transparent !important; font-family: 'Inter', sans-serif; }}
        .glass-table-container {{
            max-height: {body_height}px;
            overflow-y: auto;
            border-radius: 12px;
        }}
        .glass-table {{ width: 100%; border-collapse: collapse; color: #E2E8F0; font-size: 12px; }}
        .glass-table th {{
            text-align: left; padding: 10px 14px; color: #8B949E; font-weight: 500;
            font-size: 0.8rem; border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            position: sticky; top: 0; background: #151515; cursor: pointer; user-select: none;
        }}
        .glass-table th:hover {{ color: #FFB300; }}
        .glass-table td {{ padding: 12px 14px; border-bottom: 1px solid rgba(255, 255, 255, 0.03); font-weight: 500; color: #E2E8F0; }}
        .glass-table tr:hover td {{ background: rgba(255, 255, 255, 0.02); }}
        .sort-arrow {{ font-size: 0.7rem; margin-left: 4px; color: #FFB300; }}
        .glass-link {{ color: #FFB300; text-decoration: none; }}
        .glass-download {{
            display: inline-flex; align-items: center; gap: 6px;
            margin-top: 10px; padding: 5px 14px; font-size: 0.8rem;
            color: #FFB300; background: rgba(255, 179, 0, 0.08);
            border: 1px solid rgba(255, 179, 0, 0.25); border-radius: 8px;
            text-decoration: none; cursor: pointer; transition: all 0.15s ease;
        }}
        .glass-download:hover {{ background: rgba(255, 179, 0, 0.16); border-color: rgba(255, 179, 0, 0.4); color: #FFC107; }}
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
    
    fig = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=0.82, # More premium thin donut
        marker=dict(
            colors=["#FFB300", "#FFC107", "#E5A000", "#FFFFFF", "#4A4A4A"],
            line=dict(color='#151515', width=3) # Absolute black borders for seamless dark UI
        ),
        textinfo='none', # Cleaner look, only on hover
        hoverinfo='label+percent+value'
    )])
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", 
        plot_bgcolor="rgba(0,0,0,0)", 
        font={"color": "#8B949E", "family": "Inter, sans-serif"}, 
        margin={"l": 0, "r": 0, "t": 10, "b": 0}, 
        showlegend=True, 
        legend={"orientation": "h", "y": -0.15, "font": {"size": 11}}, 
        height=320
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_whatsapp_campaigns(campaigns: list[CampaignInsight]) -> None:
    st.markdown("### Campanhas de Mensagens (WhatsApp/Direct)")
    if not campaigns: return
    
    # Bento Grid Layout
    col1, col2 = st.columns([1.1, 1])
    
    with col1:
        data = [{"Campanha": c.campaign_name, "Gastos": round(c.spend, 2), "Conversas": c.whatsapp_starts, "Custo/Conv": round(c.cost_per_whatsapp, 2), "Alcance": c.impressions} for c in campaigns]
        render_glass_table(
            pd.DataFrame(data),
            currency_cols=["Gastos", "Custo/Conv"],
            key="tbl_whatsapp",
            csv_filename="campanhas_whatsapp.csv",
        )
    
    with col2:
        if any(c.whatsapp_starts > 0 for c in campaigns):
            chart_data = pd.DataFrame({"Campanha": [c.campaign_name for c in campaigns if c.whatsapp_starts > 0], "Custo": [c.cost_per_whatsapp for c in campaigns if c.whatsapp_starts > 0]})
            
            fig = go.Figure()
            # Mudando para Barras Finas (Sleek/Dashdark style) para não ficar grosseiro.
            # E mantendo o eixo Y no Zero para não distorcer.
            fig.add_trace(go.Bar(
                x=chart_data["Campanha"], 
                y=chart_data["Custo"],
                width=0.15, # Barra ultra fina, visual premium
                marker=dict(
                    color='#FFB300', # Ouro Zenit
                    # Adicionando um leve degradê na barra (simulado com line color mais clara e sem bordas duras)
                    line=dict(color='rgba(255, 179, 0, 0.8)', width=0),
                ),
                text=chart_data["Custo"].apply(lambda x: f"R$ {x:,.2f}".replace(".", ",")),
                textposition='outside', # Como a barra é fina, o texto vai para cima dela
                textfont=dict(color="#E2E8F0", family="Inter", size=11, weight="bold"),
                hoverinfo='y+x'
            ))
            
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", 
                paper_bgcolor="rgba(0,0,0,0)", 
                xaxis=dict(showgrid=False, zeroline=False, showline=False, color="#8B949E", tickfont=dict(size=10, family="Inter")), 
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)", gridwidth=1, zeroline=True, zerolinecolor="rgba(255,255,255,0.1)", rangemode="tozero", color="#8B949E", tickprefix="R$ ", tickfont=dict(size=10, family="Inter")), 
                margin=dict(l=0, r=0, t=15, b=0), # Margem top um pouco maior pro texto 'outside' caber
                height=260, 
                hovermode="x unified",
                hoverlabel=dict(bgcolor="#0B1739", font_size=12, font_family="Inter", bordercolor="#7E89AC")
            )
            st.markdown("<div class='glass-card' style='padding: 16px !important;'>", unsafe_allow_html=True)
            st.markdown("<h4 style='color: #8B949E; font-size: 0.85rem; margin-top: 0; margin-bottom: 12px; font-weight: 500;'>Desempenho de Custo</h4>", unsafe_allow_html=True)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            st.markdown("</div>", unsafe_allow_html=True)

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