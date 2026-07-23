import streamlit as st
import asyncio
import os
import sys
import ssl

# Desativa a verificação estrita de SSL para desenvolvimento local no Windows
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Garante que o diretório atual está no path para importar pacotes
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auth.oauth import get_login_url, exchange_code_for_token
from api.meta_client import MetaAPIClient
from ui.styles import apply_impeccable_styles, render_hero_section
from ui.dashboard_view import render_analytics_dashboard

# ==========================================
# INICIALIZAÇÃO DE ESTADOS (Regra: Session State Management)
# ==========================================
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None

if "demo_mode" not in st.session_state:
    st.session_state["demo_mode"] = False

# ==========================================
# APLICAÇÃO DE ESTILOS MODULARIZADOS
# ==========================================
apply_impeccable_styles()

# ==========================================
# LÓGICA PRINCIPAL (ASYNC)
# ==========================================
async def main():
    # Renderiza UI Encapsulada
    render_hero_section()
    
    # 1. Verifica se estamos recebendo um código de login na URL
    query_params = st.query_params
    
    if "code" in query_params and not st.session_state["access_token"]:
        # Usuário acabou de voltar da tela do Facebook com o código secreto!
        code = query_params["code"]
        try:
            with st.spinner("Autenticando com a Meta..."):
                token = await exchange_code_for_token(code)
                st.session_state["access_token"] = token
                
                # Limpa a URL para ficar bonita de novo (remove o ?code=...)
                st.query_params.clear()
                st.rerun()
                
        except Exception as e:
            st.error(f"Erro ao fazer login: {e}")
            
    # 2. Renderiza Tela de Acordo com Estado
    if st.session_state["demo_mode"]:
        st.info("💡 Você está no **Modo Demonstração** (Inspirado no protótipo code.html).")
        if st.button("⬅️ Sair do Modo Demo"):
            st.session_state["demo_mode"] = False
            st.rerun()
            
        render_analytics_dashboard(is_demo=True)
        
    elif not st.session_state["access_token"]:
        st.write("---")
        st.markdown("<br><br>", unsafe_allow_html=True)
        login_url = get_login_url()
        st.link_button("Entrar com Facebook / Instagram", url=login_url, use_container_width=True)
        
        if st.button("📊 Ver Exemplo do Dashboard Completo (Modo Demo)"):
            st.session_state["demo_mode"] = True
            st.rerun()
    else:
        st.success("✅ Autenticado com sucesso na Meta!")
        
        # Testando Motor API
        client = MetaAPIClient(access_token=st.session_state["access_token"])
        
        with st.spinner("Buscando dados da Meta..."):
            pages = await client.get_user_pages()
            
            if not pages:
                st.warning("Nenhuma página do Facebook encontrada nesta conta.")
                st.info("💡 Isso acontece se sua conta do Facebook não for administradora de nenhuma página ou se você não marcou as páginas durante o login.")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🔄 Refazer Login"):
                        st.session_state["access_token"] = None
                        st.rerun()
                with col2:
                    if st.button("🚪 Sair / Trocar Conta"):
                        st.session_state["access_token"] = None
                        st.rerun()
                with col3:
                    if st.button("📊 Abrir Modo Demo Completo"):
                        st.session_state["demo_mode"] = True
                        st.rerun()
            else:
                st.write("### Páginas Encontradas:")
                for page in pages:
                    st.write(f"- {page.get('name')}")
                    
                render_analytics_dashboard(is_demo=False)
                
                if st.button("🚪 Sair"):
                    st.session_state["access_token"] = None
                    st.rerun()
    # Final do main
if __name__ == "__main__":
    asyncio.run(main())
