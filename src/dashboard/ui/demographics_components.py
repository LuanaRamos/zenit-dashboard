import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from schemas.instagram import AccountDemographics, InstagramDemographics

def render_age_gender_chart(demo: InstagramDemographics, title: str):
    """Renderiza um gráfico de pirâmide/barras cruzadas para Idade e Gênero"""
    data = demo.age_gender
    if not data:
        st.info("Sem dados demográficos de Idade/Gênero disponíveis.")
        return
        
    # Extrair idade e gênero do formato "25-34 (M)" ou "25-34 (F)"
    parsed_data = []
    for key, value in data.items():
        if " (" in key and ")" in key:
            age = key.split(" (")[0]
            gender = key.split(" (")[1].replace(")", "")
            # Mapeamento para exibição amigável
            if gender == "M": gender = "Masculino"
            elif gender == "F": gender = "Feminino"
            elif gender == "U": gender = "Indefinido"
            parsed_data.append({"Idade": age, "Gênero": gender, "Pessoas": value})
            
    if not parsed_data:
        return
        
    df = pd.DataFrame(parsed_data)
    
    # Ordenar pelas faixas etárias
    age_order = ['13-17', '18-24', '25-34', '35-44', '45-54', '55-64', '65+']
    
    fig = px.bar(
        df, 
        x="Pessoas", 
        y="Idade", 
        color="Gênero", 
        barmode="group",
        category_orders={"Idade": age_order},
        color_discrete_map={"Masculino": "#2A85FF", "Feminino": "#FF2A85", "Indefinido": "#A0A0A0"},
        orientation='h'
    )
    
    fig.update_layout(
        title=f"Distribuição de Idade e Gênero - {title}",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E2E8F0"),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)"),
        yaxis=dict(showgrid=False),
        margin=dict(l=0, r=0, t=40, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def render_top_locations(data: dict[str, int], title: str, is_country: bool = False):
    """Renderiza tabela/barras de Top Localizações"""
    if not data:
        st.info(f"Sem dados de {title.lower()} disponíveis.")
        return
        
    # Converter para lista e pegar os top 10
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Criar formatação visual
    html = f"""
    <div style="background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; padding: 20px;">
        <h4 style="margin-top: 0; color: #F8FAFC; font-weight: 500;">{title}</h4>
        <div style="display: flex; flex-direction: column; gap: 12px;">
    """
    
    if not sorted_items:
        return
        
    max_val = sorted_items[0][1]
    
    for name, val in sorted_items:
        # Se for país e estiver no formato ISO (ex: "BR"), vamos exibir
        display_name = name
        pct = (val / max_val) * 100 if max_val > 0 else 0
        
        # Cor baseada no tipo
        color = "#2A85FF" if not is_country else "#6366F1"
        
        html += f"""
            <div>
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #CBD5E1; margin-bottom: 4px;">
                    <span>{display_name}</span>
                    <span style="font-weight: 600; color: #F8FAFC;">{val:,}</span>
                </div>
                <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.05); border-radius: 4px; overflow: hidden;">
                    <div style="width: {pct}%; height: 100%; background: {color}; border-radius: 4px;"></div>
                </div>
            </div>
        """
        
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def render_demographics_dashboard(demo: AccountDemographics):
    """Renderiza a aba completa de Dados Demográficos"""
    st.markdown("### Perfil da Audiência (Insight Demográfico)")
    st.markdown("<p style='color: #94A3B8; margin-bottom: 24px;'>Descubra quem são as pessoas que te seguem e interagem com seu conteúdo organicamente.</p>", unsafe_allow_html=True)
    
    tab_type = st.pills(
        "Selecione o Público",
        options=["Seguidores (Lifetime)", "Público Engajado (Este Mês)"],
        default="Seguidores (Lifetime)"
    )
    if not tab_type:
        tab_type = "Seguidores (Lifetime)"
    
    current_demo = demo.followers if tab_type.startswith("Seguidores") else demo.engaged
    title_suffix = "Seguidores" if tab_type.startswith("Seguidores") else "Público Engajado"
    
    if not current_demo.age_gender and not current_demo.cities and not current_demo.countries:
        st.warning(f"O Instagram não retornou dados suficientes para o {title_suffix}. Isso pode ocorrer em contas novas, com poucos seguidores, ou caso não tenha havido engajamento suficiente no mês atual.")
        return
        
    render_age_gender_chart(current_demo, title_suffix)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        render_top_locations(current_demo.cities, f"Top Cidades ({title_suffix})", is_country=False)
    with col2:
        render_top_locations(current_demo.countries, f"Top Países ({title_suffix})", is_country=True)
def render_demographics_tab(date_preset: str, time_range: dict = None):
    "\""Renderiza a aba Demográfica de Anúncios (Ads)"\""
    st.markdown("### 👥 Perfil de Audiência (Anúncios)")
    st.markdown("<p style='color: #94A3B8; margin-bottom: 24px;'>Visão demográfica das pessoas que foram impactadas e interagiram com suas campanhas pagas.</p>", unsafe_allow_html=True)
    
    try:
        from api.meta_client import MetaAdsClient
        client = MetaAdsClient()
        insights = client.get_demographics_insights(date_preset, time_range)
        
        if not insights:
            st.info("Não há dados demográficos disponíveis para o período.")
            return
            
        # Converter dados para o formato que a função de chart espera
        age_gender_dict = {}
        for item in insights:
            # item.age: '25-34', item.gender: 'female'
            gender = "U"
            if item.gender == "male": gender = "M"
            elif item.gender == "female": gender = "F"
            elif item.gender == "unknown": gender = "U"
            
            key = f"{item.age} ({gender})"
            # Usar impressões como peso principal para demografia de ads
            age_gender_dict[key] = age_gender_dict.get(key, 0) + item.impressions
            
        demo = InstagramDemographics(age_gender=age_gender_dict)
        render_age_gender_chart(demo, "Anúncios (Impressões)")
        
    except Exception as e:
        st.error(f"Erro ao carregar dados demográficos de ads.")
        import sentry_sdk
        sentry_sdk.capture_exception(e)
