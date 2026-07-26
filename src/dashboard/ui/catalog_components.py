import streamlit as st
import pandas as pd
from typing import Any
from schemas.meta import CatalogData

def render_catalog_tab(catalogs: list[CatalogData]) -> None:
    """Renderiza a aba de Catálogo & E-commerce"""
    st.markdown("### 🛍️ Catálogos de Produtos")
    
    if not catalogs:
        st.info("Nenhum catálogo vinculado a esta conta de anúncios.")
        return

    # Cards superiores
    total_products = sum(c.product_count for c in catalogs)
    cols = st.columns(3)
    cols[0].metric("Total de Catálogos", len(catalogs))
    cols[1].metric("Total de Produtos", f"{total_products:,}".replace(",", "."))
    
    # Tabela de Catálogos
    st.markdown("#### Detalhamento")
    
    data = []
    for c in catalogs:
        data.append({
            "ID do Catálogo": c.catalog_id,
            "Nome": c.name,
            "Qtd. Produtos": c.product_count
        })
        
    df = pd.DataFrame(data)
    from ui.components import render_glass_table
    render_glass_table(
        df,
        key="tbl_catalog",
        csv_filename="catalogos.csv"
    )
