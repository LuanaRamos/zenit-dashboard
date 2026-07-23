import streamlit as st

def apply_impeccable_styles():
    st.set_page_config(page_title="Zenit Analytics - Instagram & Ads Insights", page_icon="📈", layout="wide")

    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;600;700;900&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap');

        /* Reset e Fundo Absoluto (Dark Mode Obsidian - Zenit Analytics) */
        .stApp {
            background: #0c0c0e !important;
            color: #FFFFFF !important;
            font-family: 'Inter', sans-serif !important;
        }
        
        /* Esconder o header padrão do Streamlit */
        header[data-testid="stHeader"] {
            background: transparent !important;
        }

        /* ANIMAÇÕES */
        @keyframes slideUpFade {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulseGlow {
            0% { opacity: 0.3; transform: scale(0.98); }
            100% { opacity: 0.7; transform: scale(1.02); }
        }
        
        @keyframes textShimmer {
            to { background-position: 200% center; }
        }
        
        /* Main Container Wide Mode */
        div[data-testid="stMainBlockContainer"] {
            background: transparent;
            padding: 2rem 2rem !important;
            max-width: 1400px !important;
            margin-left: auto;
            margin-right: auto;
            animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        /* Glass Cards (Inspirado no code.html) */
        .glass-card {
            background: rgba(24, 24, 28, 0.75) !important;
            backdrop-filter: blur(20px) !important;
            -webkit-backdrop-filter: blur(20px) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 16px !important;
            padding: 1.5rem !important;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4) !important;
            transition: all 0.3s ease !important;
        }
        
        .glass-card:hover {
            border-color: rgba(255, 179, 0, 0.3) !important;
            box-shadow: 0px 8px 30px rgba(255, 179, 0, 0.15) !important;
            transform: translateY(-2px) !important;
        }

        /* Títulos Grandes e Claros */
        .zenit-title {
            font-family: 'Hanken Grotesk', sans-serif;
            font-size: clamp(2.5rem, 6vw, 4rem) !important;
            font-weight: 900;
            background: linear-gradient(135deg, #FFB300 0%, #FFDCA1 40%, #FFFFFF 60%, #FFB300 100%);
            background-size: 200% auto;
            animation: textShimmer 5s linear infinite;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin-bottom: 0.5rem;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }
        
        .zenit-subtitle {
            font-family: 'Inter', sans-serif;
            font-size: clamp(1.1rem, 2.5vw, 1.4rem) !important;
            text-align: center;
            color: #9C9CA3;
            line-height: 1.5;
            margin-bottom: 2.5rem;
            font-weight: 400;
        }

        /* Custom Badges & Pills */
        .metric-pill-green {
            background: rgba(76, 175, 80, 0.15);
            color: #4CAF50;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }

        .metric-pill-gold {
            background: rgba(255, 179, 0, 0.15);
            color: #FFB300;
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Botão de Login Gigante */
        .stLinkButton > a {
            font-family: 'Hanken Grotesk', sans-serif !important;
            background: linear-gradient(135deg, #1877F2 0%, #0A4EAB 100%) !important;
            color: white !important;
            font-size: 1.3rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            border-radius: 14px !important;
            padding: 1.2rem 3rem !important;
            text-decoration: none !important;
            border: 2px solid transparent !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 8px 24px rgba(24, 119, 242, 0.4) !important;
            letter-spacing: 0.05em;
        }
        
        .stLinkButton > a:hover {
            transform: translateY(-3px) scale(1.01) !important;
            box-shadow: 0 15px 35px rgba(24, 119, 242, 0.6) !important;
            border: 2px solid rgba(255, 255, 255, 0.4) !important;
        }
    </style>
    """, unsafe_allow_html=True)

def render_hero_section():
    st.markdown('''
        <h1 class="zenit-title">Dashboard Zenit</h1>
        <p class="zenit-subtitle">Acompanhe o crescimento orgânico e tráfego pago da sua empresa em tempo real.</p>
    ''', unsafe_allow_html=True)
