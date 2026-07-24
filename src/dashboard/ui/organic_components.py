import streamlit as st
import pandas as pd
from typing import List
from schemas.instagram import InstagramMedia

def render_organic_metrics_cards(media_list: List[InstagramMedia]):
    if not media_list:
        st.info("Nenhuma publicação encontrada no período selecionado.")
        return
        
    total_posts = len(media_list)
    total_likes = sum(m.total_likes for m in media_list)
    total_comments = sum(m.comments_count for m in media_list)
    total_reach = sum(m.reach for m in media_list)
    
    total_organic_reach = sum(m.organic_reach for m in media_list)
    total_paid_reach = sum(m.paid_reach for m in media_list)
    
    # Calcular % de tráfego pago
    perc_paid = (total_paid_reach / total_reach * 100) if total_reach > 0 else 0
    
    cols = st.columns(5)
    cols[0].metric("Total de Publicações", total_posts)
    cols[1].metric("Total de Curtidas", total_likes)
    cols[2].metric("Total de Comentários", total_comments)
    cols[3].metric("Alcance Orgânico", f"{total_organic_reach:,}".replace(",", "."))
    cols[4].metric("Alcance Pago", f"{total_paid_reach:,}".replace(",", ".") + f" ({perc_paid:.1f}%)")

def render_posts_table(media_list: List[InstagramMedia]):
    st.markdown("### Análise Individual por Publicação")
    
    if not media_list:
        return
        
    table_data = []
    for m in media_list:
        # Formatar caption curto
        short_caption = m.caption[:45] + "..." if len(m.caption) > 45 else m.caption
        if not short_caption:
            short_caption = "[Sem legenda]"
            
        table_data.append({
            "Publicação": short_caption,
            "Likes": m.total_likes,
            "Alcance Orgânico": m.organic_reach,
            "Alcance Pago": m.paid_reach,
            "CTR Anúncio (%)": round(m.paid_ctr, 2) if m.paid_reach > 0 else "-",
            "Frequência (Ads)": round(m.paid_frequency, 2) if m.paid_reach > 0 else "-",
            "Visualizar no IG": m.permalink
        })
        
    df = pd.DataFrame(table_data)
    
    st.dataframe(
        df,
        column_config={
            "Visualizar no IG": st.column_config.LinkColumn("Link Direto", display_text="Abrir post")
        },
        use_container_width=True,
        hide_index=True
    )
