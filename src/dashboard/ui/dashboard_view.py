import streamlit as st
import plotly.graph_objects as go

def render_analytics_dashboard(is_demo: bool = True):
    """Renderiza a visão completa de Analytics inspirada no design do code.html."""
    
    col_head, col_filter = st.columns([3, 1])
    with col_head:
        st.markdown("### 📊 Visão Geral de Performance (Instagram & Meta Ads)")
    with col_filter:
        periodo = st.selectbox("Período:", ["Últimos 30 dias", "Últimos 7 dias", "Este Mês"], index=0)

    st.write("---")

    # ==========================================
    # 1. TOP METRICS CARDS (GLASS CARDS GRID)
    # ==========================================
    m1, m2, m3, m4 = st.columns(4)
    
    with m1:
        st.markdown("""<div class="glass-card">
<div style="color: #9C9CA3; font-size: 0.85rem; font-weight: 500;">Alcance Total</div>
<div style="font-size: 2rem; font-weight: 700; color: #FFFFFF; margin: 0.3rem 0;">1.250.400</div>
<div><span class="metric-pill-green">↑ +18.4%</span> <span style="color: #9C9CA3; font-size: 0.8rem;">vs mês anterior</span></div>
</div>""", unsafe_allow_html=True)
        
    with m2:
        st.markdown("""<div class="glass-card">
<div style="color: #9C9CA3; font-size: 0.85rem; font-weight: 500;">Taxa de Engajamento</div>
<div style="font-size: 2rem; font-weight: 700; color: #FFFFFF; margin: 0.3rem 0;">5.85%</div>
<div><span class="metric-pill-gold">★ +1.2%</span> <span style="color: #9C9CA3; font-size: 0.8rem;">Média da indústria: 3.2%</span></div>
</div>""", unsafe_allow_html=True)
        
    with m3:
        st.markdown("""<div class="glass-card">
<div style="color: #9C9CA3; font-size: 0.85rem; font-weight: 500;">Seguidores Totais</div>
<div style="font-size: 2rem; font-weight: 700; color: #FFFFFF; margin: 0.3rem 0;">48.520</div>
<div><span class="metric-pill-green">↑ +1.240</span> <span style="color: #9C9CA3; font-size: 0.8rem;">novos esta semana</span></div>
</div>""", unsafe_allow_html=True)

    with m4:
        st.markdown("""<div class="glass-card">
<div style="color: #9C9CA3; font-size: 0.85rem; font-weight: 500;">Investimento Meta Ads / ROAS</div>
<div style="font-size: 2rem; font-weight: 700; color: #FFB300; margin: 0.3rem 0;">R$ 4.250 / 4.85x</div>
<div><span class="metric-pill-green">↑ 68% Pago</span> <span style="color: #9C9CA3; font-size: 0.8rem;">32% Orgânico</span></div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 2. GRÁFICOS PRINCIPAIS (PLOTLY DARK THEME)
    # ==========================================
    ch1, ch2 = st.columns([2, 1])
    
    with ch1:
        st.markdown("#### 📈 Crescimento Diário: Orgânico (Instagram) vs Tráfego Pago (Meta Ads)")
        
        dias = ["Jun 1", "Jun 5", "Jun 10", "Jun 15", "Jun 20", "Jun 25", "Jun 30"]
        organico = [12000, 15000, 18000, 22000, 29000, 34000, 41000]
        pago = [30000, 42000, 39000, 51000, 68000, 72000, 89000]

        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(
            x=dias, y=organico, name="Orgânico (Instagram)",
            line=dict(color="#5af8fb", width=3), fill='tonexty'
        ))
        fig1.add_trace(go.Scatter(
            x=dias, y=pago, name="Tráfego Pago (Meta Ads)",
            line=dict(color="#ffb300", width=3), fill='tozeroy'
        ))
        
        fig1.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#9C9CA3"),
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        )
        st.plotly_chart(fig1, use_container_width=True)

    with ch2:
        st.markdown("#### 🎯 Distribuição por Formato de Conteúdo")
        
        labels = ['Reels / Shorts', 'Carrossel', 'Imagem', 'Stories']
        values = [45, 30, 15, 10]
        
        fig2 = go.Figure(data=[go.Pie(
            labels=labels, values=values, hole=.6,
            marker=dict(colors=['#ffb300', '#5af8fb', '#1877f2', '#e89a00'])
        )])
        fig2.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#FFFFFF"),
            margin=dict(l=0, r=0, t=20, b=0),
            showlegend=True,
            legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ==========================================
    # 3. BENTO GRID (TOP POSTS, DEMOGRAFIA, CIDADES)
    # ==========================================
    b1, b2, b3 = st.columns(3)
    
    with b1:
        st.markdown("""<div class="glass-card">
<h4 style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; margin-bottom: 1rem;">🔥 Top Posts de Maior Engajamento</h4>
<div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
    <div style="background: #1e1e24; border-radius: 8px; padding: 0.8rem; font-size: 1.5rem;">📸</div>
    <div>
        <div style="font-weight: 600; font-size: 0.9rem;">Relatório de Resultados Q3</div>
        <div style="color: #9C9CA3; font-size: 0.8rem;">❤️ 12.4k curtidas • 💬 842 comentários</div>
    </div>
</div>
<div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
    <div style="background: #1e1e24; border-radius: 8px; padding: 0.8rem; font-size: 1.5rem;">🎬</div>
    <div>
        <div style="font-weight: 600; font-size: 0.9rem;">Recap Bastidores Lançamento</div>
        <div style="color: #9C9CA3; font-size: 0.8rem;">❤️ 9.2k curtidas • 💬 415 comentários</div>
    </div>
</div>
<div style="display: flex; align-items: center; gap: 1rem;">
    <div style="background: #1e1e24; border-radius: 8px; padding: 0.8rem; font-size: 1.5rem;">🚀</div>
    <div>
        <div style="font-weight: 600; font-size: 0.9rem;">Anúncio do Novo Produto Zenit</div>
        <div style="color: #9C9CA3; font-size: 0.8rem;">❤️ 8.7k curtidas • 💬 320 comentários</div>
    </div>
</div>
</div>""", unsafe_allow_html=True)
        
    with b2:
        st.markdown("""<div class="glass-card">
<h4 style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; margin-bottom: 1rem;">👥 Demografia do Público</h4>
<div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.3rem;">
    <span style="color: #FFB300; font-weight: 600;">Feminino (58%)</span>
    <span style="color: #5AF8FB; font-weight: 600;">Masculino (42%)</span>
</div>
<div style="width: 100%; height: 8px; background: #1e1e24; border-radius: 4px; display: flex; overflow: hidden; margin-bottom: 1.5rem;">
    <div style="width: 58%; background: #FFB300;"></div>
    <div style="width: 42%; background: #5AF8FB;"></div>
</div>

<div style="color: #9C9CA3; font-size: 0.8rem; margin-bottom: 0.5rem;">Faixa Etária Principal:</div>
<div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; font-size: 0.85rem;">
    <span style="width: 50px;">25-34</span>
    <div style="flex: 1; background: #1e1e24; height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="width: 45%; background: #FFB300; height: 100%;"></div>
    </div>
    <span style="font-weight: 700; color: #FFB300;">45%</span>
</div>
<div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; font-size: 0.85rem;">
    <span style="width: 50px;">18-24</span>
    <div style="flex: 1; background: #1e1e24; height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="width: 28%; background: rgba(255,179,0,0.7); height: 100%;"></div>
    </div>
    <span>28%</span>
</div>
<div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem;">
    <span style="width: 50px;">35-44</span>
    <div style="flex: 1; background: #1e1e24; height: 6px; border-radius: 3px; overflow: hidden;">
        <div style="width: 18%; background: rgba(255,179,0,0.5); height: 100%;"></div>
    </div>
    <span>18%</span>
</div>
</div>""", unsafe_allow_html=True)
        
    with b3:
        st.markdown("""<div class="glass-card">
<h4 style="border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 0.5rem; margin-bottom: 1rem;">📍 Principais Cidades / Regiões</h4>
<div style="display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
    <span>🟡 São Paulo, BR</span>
    <span style="font-weight: 700; color: #FFB300;">18.2%</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
    <span>🟡 Rio de Janeiro, BR</span>
    <span style="font-weight: 700; color: #FFB300;">12.5%</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
    <span>🟡 Belo Horizonte, BR</span>
    <span style="font-weight: 700; color: #FFB300;">8.4%</span>
</div>
<div style="display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.5rem 0;">
    <span>🔵 Lisboa, PT</span>
    <span style="font-weight: 700; color: #5AF8FB;">5.1%</span>
</div>
</div>""", unsafe_allow_html=True)
