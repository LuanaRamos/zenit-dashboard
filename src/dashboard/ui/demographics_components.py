import streamlit as st
import pandas as pd
from typing import Any
import plotly.express as px
from ui.components import render_glass_chart

def render_demographics_tab(demographics_data: list[Any]) -> None:
    """Renderiza a aba de Público (Demografia)"""
    st.markdown("### 👥 Análise de Público (Idade e Gênero)")
    
    if not demographics_data:
        st.info("Não há dados demográficos suficientes para o período selecionado.")
        return

    # Converter para DataFrame
    data = []
    for d in demographics_data:
        data.append({
            "Idade": d.age,
            "Gênero": d.gender,
            "Impressões": d.impressions,
            "Cliques": d.clicks,
            "Gasto": d.spend
        })
    df = pd.DataFrame(data)

    # Limpar dados "unknown" ou irrelevantes
    df = df[df["Idade"] != "unknown"]
    
    # Agrupar por Gênero
    gender_df = df.groupby("Gênero")["Gasto"].sum().reset_index()
    # Agrupar por Idade
    age_df = df.groupby("Idade")["Gasto"].sum().reset_index()

    cols = st.columns(2)
    
    with cols[0]:
        fig_gender = px.pie(
            gender_df, 
            values='Gasto', 
            names='Gênero', 
            hole=0.6,
            color_discrete_sequence=['#FFB300', '#FF8C00', '#4A4A4A']
        )
        fig_gender.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E2E8F0"),
            showlegend=True,
            margin=dict(l=20, r=20, t=30, b=20)
        )
        render_glass_chart(fig_gender, title="Gasto por Gênero", height=400)

    with cols[1]:
        fig_age = px.bar(
            age_df, 
            x='Idade', 
            y='Gasto',
            color_discrete_sequence=['#FFB300']
        )
        fig_age.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E2E8F0"),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        render_glass_chart(fig_age, title="Gasto por Faixa Etária", height=400)
