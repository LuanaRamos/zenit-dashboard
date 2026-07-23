import streamlit as st
from typing import List
from api.meta_client import MetaAdsClient
from schemas.meta import CampaignInsight, PageInsight

@st.cache_resource
def get_api_client() -> MetaAdsClient:
    """
    Inicializa o cliente da API apenas uma vez e guarda em cache na memória do servidor.
    Isso evita recriar o objeto a cada clique.
    """
    return MetaAdsClient()

@st.cache_data(ttl=3600)
def load_campaigns_data() -> List[CampaignInsight]:
    """
    Busca os dados de campanhas e armazena em cache por 1 hora (3600s).
    Se o usuário atualizar a página 50 vezes, a API do Facebook só será chamada na primeira vez.
    """
    client = get_api_client()
    return client.get_campaign_insights()

@st.cache_data(ttl=3600)
def load_page_data() -> PageInsight:
    """
    Simula o fetch dos dados da página orgânica.
    Implementaremos a extração de métricas de engajamento aqui.
    """
    # Exemplo mockado por enquanto, pois exige endpoint específico de page insights
    return PageInsight(followers=1250, reach=8450, engagement=340)