import streamlit as st
import pandas as pd
import plotly.express as px
from api.meta_client import MetaAdsClient
import sentry_sdk

@st.cache_data(ttl=3600)
def fetch_demographics(date_preset: str, time_range: dict = None):
    client = MetaAdsClient()
    return client.get_demographics_insights(date_preset, time_range)

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
        df = pd.DataFrame([d.model_dump() for d in data])
        
        # Ignore Unknown/unclassified if too small, or keep them.
        # Group by Gender
        df_gender = df.groupby("gender")["impressions"].sum().reset_index()
        # Group by Age
        df_age = df.groupby("age")["impressions"].sum().reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Impressões por Gênero**")
            fig_gender = px.pie(df_gender, values='impressions', names='gender', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_gender, use_container_width=True)
            
        with col2:
            st.markdown("**Impressões por Idade**")
            fig_age = px.bar(df_age, x='age', y='impressions', color_discrete_sequence=["#4a90e2"])
            st.plotly_chart(fig_age, use_container_width=True)
            
        st.markdown("---")
        st.markdown("**Tabela Completa (Investimento por Público)**")
        st.dataframe(df.sort_values(by="spend", ascending=False), use_container_width=True, hide_index=True)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        st.error("Ocorreu um erro ao carregar os dados demográficos. Nossa equipe já foi notificada e está trabalhando nisso.")
