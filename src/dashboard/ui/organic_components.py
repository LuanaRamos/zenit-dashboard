import streamlit as st
import pandas as pd
from typing import List
from schemas.instagram import InstagramMedia

def render_organic_metrics_cards(media_list: List[InstagramMedia]):
    """Renderiza os cartões de métricas consolidadas (Visão Geral)."""
    if not media_list:
        st.info("Nenhuma publicação encontrada no período selecionado.")
        return

    # Cálculos para visão geral
    total_organic_reach = sum(m.organic_reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    total_reach = total_organic_reach + total_paid_reach
    
    # Calcular percentual de tráfego orgânico vs pago
    pct_organic = (total_organic_reach / total_reach * 100) if total_reach > 0 else 0
    pct_paid = (total_paid_reach / total_reach * 100) if total_reach > 0 else 0
    st.markdown(f"### Visão Geral ({len(media_list)} Publicações)")
    cols = st.columns(3)
    
    with cols[0]:
        st.metric(
            label="Alcance Total Global", 
            value=f"{total_reach:,}".replace(",", "."),
            help="Total de pessoas alcançadas (Orgânico + Pago)."
        )
        
    with cols[1]:
        st.metric(
            label="Alcance Puramente Orgânico", 
            value=f"{total_organic_reach:,}".replace(",", "."),
            delta=f"{pct_organic:.1f}% do Total",
            delta_color="normal",
            help="Pessoas alcançadas naturalmente, sem o uso de anúncios."
        )
        
    with cols[2]:
        st.metric(
            label="Alcance via Ads (Pago)", 
            value=f"{total_paid_reach:,}".replace(",", "."),
            delta=f"{pct_paid:.1f}% do Total",
            delta_color="off",
            help="Pessoas alcançadas através de impulsionamento pago."
        )


def render_posts_table(media_list: List[InstagramMedia]):
    """Renderiza a tabela linha a linha para cada publicação com formatação Lean."""
    if not media_list:
        return
        
    st.markdown("### Análise Individual por Publicação")
    
    # Converter para dataframe para tabela nativa bonita
    data = []
    for m in media_list:
        # Pega as primeiras 40 letras da legenda
        short_caption = m.caption[:40].replace('\n', ' ') + "..." if len(m.caption) > 40 else m.caption
        
        data.append({
            "Publicação": short_caption,
            "Likes": m.total_likes,
            "Alcance Orgânico": m.organic_reach,
            "Alcance Pago": m.paid_reach,
            "CTR Anúncio (%)": round(m.paid_ctr, 2) if m.paid_reach > 0 else None,
            "Frequência Anúncio": round(m.paid_frequency, 2) if m.paid_reach > 0 else None,
            "Visualizar no IG": m.permalink
        })
        
    df = pd.DataFrame(data)
    
    # Formatando a exibição no Streamlit
    st.dataframe(
        df,
        use_container_width=True,
        column_config={
            "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir post"),
            "CTR Anúncio (%)": st.column_config.NumberColumn(
                "CTR Anúncio (%)", 
                help="Taxa de pessoas que viram e clicaram no anúncio (Média Ponderada).",
                format="%.2f"
            ),
            "Frequência Anúncio": st.column_config.NumberColumn(
                "Frequência (Ads)",
                help="Quantas vezes, em média, o anúncio foi exibido para a mesma pessoa.",
                format="%.2f"
            )
        },
        hide_index=True
    )
