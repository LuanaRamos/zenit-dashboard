import streamlit as st
import pandas as pd
import plotly.express as px
from api.meta_client import MetaAdsClient
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_demographics(date_preset: str, time_range: dict = None):
    client = MetaAdsClient()
    data = client.get_demographics_insights(date_preset, time_range)
    return [d.model_dump() for d in data]

def render_demographics_tab(date_preset: str, time_range: dict = None):
    st.subheader("👥 Análise de Público (Demografia)")
    st.markdown("Veja o perfil das pessoas que estão sendo alcançadas e clicando nos seus anúncios.")
    
    try:
        with st.spinner("Buscando dados demográficos..."):
            data = fetch_demographics(date_preset, time_range)
            
        if not data:
            st.warning("Sem dados demográficos no período.")
            return
            
        # Convert to pandas
        df = pd.DataFrame(data)

        # Translate columns
        df = df.rename(columns={
            "gender": "Gênero",
            "age": "Idade",
            "impressions": "Impressões",
            "spend": "Gastos",
            "clicks": "Cliques",
            "leads": "Leads (Form)",
            "site_leads": "Leads (Site)",
            "whatsapp_starts": "Conversas",
        })

        # Translate gender values
        gender_map = {"male": "Masculino", "female": "Feminino", "unknown": "Desconhecido"}
        if "Gênero" in df.columns:
            df["Gênero"] = df["Gênero"].map(lambda x: gender_map.get(str(x).lower(), x) if pd.notna(x) else x)
            df_gender = df.groupby("Gênero")["Impressões"].sum().reset_index()
        else:
            df_gender = pd.DataFrame(columns=["Gênero", "Impressões"])

        if "Idade" in df.columns:
            df["Idade"] = df["Idade"].map(lambda x: "Desconhecido" if str(x).lower() == "unknown" else x)
            df_age = df.groupby("Idade")["Impressões"].sum().reset_index()
        else:
            df_age = pd.DataFrame(columns=["Idade", "Impressões"])
        
        from ui.components import render_glass_chart, render_glass_table
        
        col1, col2 = st.columns(2)
        
        with col1:
            color_map = {"Feminino": "#FF69B4", "Masculino": "#4a90e2", "Desconhecido": "#9e9e9e"}
            fig_gender = px.pie(
                df_gender, 
                values='Impressões', 
                names='Gênero', 
                hole=0.4, 
                color='Gênero',
                color_discrete_map=color_map
            )
            fig_gender.update_layout(
                separators=",.",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8B949E", family="Inter, sans-serif"),
                margin=dict(l=0, r=0, t=10, b=60),
                showlegend=True,
                legend=dict(orientation="h", y=-0.25, font=dict(size=11)),
                height=400,
                hoverlabel=dict(bgcolor="rgba(20,20,20,0.9)", bordercolor="#4a90e2", font=dict(family="Montserrat", size=13))
            )
            render_glass_chart(fig_gender, title="Impressões por Gênero", height=460)
            
        with col2:
            fig_age = px.bar(
                df_age, 
                x='Idade', 
                y='Impressões', 
                color_discrete_sequence=["#4a90e2"]
            )
            fig_age.update_layout(
                separators=",.",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#8B949E", family="Inter, sans-serif"),
                xaxis=dict(showgrid=False, color="#8B949E", title=None),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.03)", color="#8B949E", title=None),
                margin=dict(l=0, r=0, t=10, b=40),
                height=400,
                hoverlabel=dict(bgcolor="rgba(20,20,20,0.9)", bordercolor="#4a90e2", font=dict(family="Montserrat", size=13))
            )
            render_glass_chart(fig_age, title="Impressões por Idade", height=460)
            
        st.markdown("---")
        st.markdown("### Investimento por Público")
        
        # Keep only useful columns for the table
        display_cols = ["Gênero", "Idade", "Gastos", "Impressões", "Cliques", "Conversas"]
        table_df = df[[c for c in display_cols if c in df.columns]].sort_values(by="Gastos", ascending=False)
        
        render_glass_table(
            table_df, 
            currency_cols=["Gastos"], 
            key="tbl_demographics", 
            csv_filename="demografia.csv"
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os dados demográficos. Nossa equipe já foi notificada e está trabalhando nisso.")