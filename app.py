import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime, timedelta
import pytz
import re
import time

# --- 1. CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Awake OS | Dark", page_icon="🌑", layout="wide", initial_sidebar_state="collapsed")

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# --- 2. PALETA DE CORES DINÂMICA (AURA DOS MESES) ---
# Cada mês terá uma cor tema diferente sobre o fundo preto
THEMES = {
    1: {"color": "#2E7D32", "name": "Janeiro (Renovação)"},   # Verde Awake
    2: {"color": "#8E24AA", "name": "Fevereiro (Intuição)"},  # Roxo
    3: {"color": "#0288D1", "name": "Março (Fluidez)"},       # Azul
    4: {"color": "#D81B60", "name": "Abril (Paixão)"},        # Rosa
    5: {"color": "#F9A825", "name": "Maio (Abundância)"},     # Dourado
    6: {"color": "#E64A19", "name": "Junho (Energia)"},       # Laranja
    7: {"color": "#00897B", "name": "Julho (Equilíbrio)"},    # Teal
    8: {"color": "#5E35B1", "name": "Agosto (Profundidade)"}, # Indigo
    9: {"color": "#43A047", "name": "Setembro (Cura)"},       # Verde Claro
    10: {"color": "#3949AB", "name": "Outubro (Expansão)"},    # Azul Indigo
    11: {"color": "#C0CA33", "name": "Novembro (Luz)"},       # Lima
    12: {"color": "#C62828", "name": "Dezembro (Celebração)"}  # Vermelho
}

# Controle de Estado do Mês (Para as setas funcionarem)
if 'mes_idx' not in st.session_state:
    st.session_state.mes_idx = datetime.now().month

# Lógica de Navegação
def mudar_mes(delta):
    novo = st.session_state.mes_idx + delta
    if novo > 12: novo = 1
    if novo < 1: novo = 12
    st.session_state.mes_idx = novo

# Pega o tema do mês atual
CURRENT_THEME = THEMES[st.session_state.mes_idx]
ACCENT_COLOR = CURRENT_THEME['color']

# --- 3. CSS "ECOFIN STYLE" (DARK MODE PROFISSIONAL) ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@300;400;600;800&family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400&display=swap');
    
    :root {{
        --bg-body: #050505;
        --bg-surface: #0F0F0F;
        --card-bg: rgba(255, 255, 255, 0.03);
        --text-primary: #FFFFFF;
        --text-secondary: #9CA3AF;
        --accent: {ACCENT_COLOR}; /* Cor Dinâmica */
        --border-light: rgba(255, 255, 255, 0.08);
    }}

    /* Global Override */
    .stApp {{
        background-color: var(--bg-body);
        font-family: 'Inter', sans-serif;
    }}
    
    /* Esconder UI Streamlit */
    #MainMenu, footer, header {{ visibility: hidden; }}
    [data-testid="stSidebar"] {{ background-color: #0A0A0A; border-right: 1px solid var(--border-light); }}
    
    /* HEADER ESTRUTURAL */
    .month-header-wrapper {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 30px 0;
        border-bottom: 1px solid var(--border-light);
        margin-bottom: 30px;
        position: relative;
    }}
    
    /* TÍTULO COM GLOW */
    .month-title {{
        font-family: 'Manrope', sans-serif;
        font-size: 42px;
        font-weight: 800;
        color: white;
        letter-spacing: -1px;
        text-shadow: 0 0 40px {ACCENT_COLOR}66; /* Glow dinâmico */
    }}
    
    .month-subtitle {{
        font-size: 14px;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: 700;
        margin-top: 5px;
    }}

    /* BACKGROUND FX (As "Blobs" do seu exemplo) */
    .ambient-glow {{
        position: fixed;
        top: -10%;
        right: -10%;
        width: 600px;
        height: 600px;
        background: {ACCENT_COLOR};
        filter: blur(150px);
        opacity: 0.15;
        z-index: -1;
        pointer-events: none;
    }}

    /* GRID DO CALENDÁRIO */
    .cal-grid {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
    }}

    .weekday {{
        text-align: center;
        color: var(--text-secondary);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 10px 0;
        font-weight: 600;
    }}

    /* CARD DO DIA (GLASSMORPHISM) */
    .day-card {{
        background: var(--card-bg);
        border: 1px solid var(--border-light);
        border-radius: 12px;
        min-height: 140px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        transition: all 0.3s ease;
        position: relative;
        backdrop-filter: blur(10px);
    }}

    .day-card:hover {{
        border-color: var(--accent);
        transform: translateY(-4px);
        background: rgba(255,255,255,0.06);
        box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }}

    /* ESTADOS */
    .is-today {{
        border: 1px solid var(--accent);
        background: linear-gradient(180deg, {ACCENT_COLOR}11 0%, rgba(0,0,0,0) 100%);
    }}
    
    .is-past {{
        opacity: 0.3;
        filter: grayscale(1);
    }}
    
    .day-num {{
        font-family: 'Manrope', sans-serif;
        font-size: 18px;
        font-weight: 700;
        color: var(--text-secondary);
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
    }}
    
    .is-today .day-num {{ color: white; }}

    /* CHIPS */
    .chip {{
        font-size: 11px;
        padding: 6px 10px;
        border-radius: 6px;
        margin-bottom: 6px;
        color: #ddd;
        background: rgba(255,255,255,0.05);
        border-left: 2px solid #555;
        font-weight: 500;
        line-height: 1.3;
    }}

    /* Variações de Chips */
    .chip-sh {{ border-color: #4CAF50; background: rgba(76, 175, 80, 0.1); color: #A5D6A7; }}
    .chip-teca {{ border-color: #AB47BC; background: rgba(171, 71, 188, 0.1); color: #E1BEE7; }}
    .chip-especial {{ border-color: #FFB300; background: rgba(255, 179, 0, 0.1); color: #FFE082; }}
    .chip-feriado {{ border-color: #EF5350; background: rgba(239, 83, 80, 0.1); color: #EF9A9A; }}
    .chip-recesso {{ border-color: #78909C; background: rgba(120, 144, 156, 0.1); color: #90A4AE; }}

    /* Inputs e Botões Estilo Dark */
    .stChatInput textarea {{ background-color: #1A1A1A !important; color: white !important; border: 1px solid #333 !important; }}
    .stSelectbox div[data-baseweb="select"] > div {{ background-color: #1A1A1A; color: white; border-color: #333; }}
    
    /* Botões de Navegação */
    .nav-btn {{
        background: none;
        border: 1px solid var(--border-light);
        color: white;
        padding: 5px 15px;
        border-radius: 8px;
        cursor: pointer;
        transition: 0.2s;
        font-size: 18px;
    }}
    .nav-btn:hover {{ border-color: var(--accent); color: var(--accent); }}

    </style>
""", unsafe_allow_html=True)

# Efeito de Fundo (Blob)
st.markdown('<div class="ambient-glow"></div>', unsafe_allow_html=True)

# --- 4. CONEXÃO SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except: return None

supabase = init_connection()

# --- 5. LÓGICA DE DADOS E NLP ---
INSTRUTORES = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
MESES_PT = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
FERIADOS_2026 = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 6, 4): "Corpus Christi", date(2026, 7, 9): "Rev. 32", 
    date(2026, 9, 7): "Independência", date(2026, 10, 12): "N. Sra. Aparecida", 
    date(2026, 11, 2): "Finados", date(2026, 11, 15): "Proclamação", 
    date(2026, 11, 20): "Consciência", date(2026, 12, 25): "Natal"
}

def nlp_parser(texto, mes_atual):
    texto = texto.lower()
    # Data
    match_dia = re.search(r'\bdia (\d{1,2})\b', texto)
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', texto)
    
    d, m = None, None
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_dia: d, m = int(match_dia.group(1)), mes_atual
    
    if not d: return {"status": "erro", "msg": "Indique a data (ex: 'dia 20')"}
    
    try: data_obj = date(2026, m, d)
    except: return {"status": "erro", "msg": "Data inválida."}
    
    # Tipo e Descrição
    tipo = "especial"
    if "recesso" in texto: tipo = "recesso"
    elif any(x in texto for x in ["cancelar", "remover", "off"]): tipo = "cancelado"
    
    desc = ""
    if tipo == "recesso": desc = "RECESSO"
    elif tipo == "cancelado": desc = "CANCELADO"
    else:
        # Extração Limpa
        raw = texto
        # Tira data
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw)
        
        # Tira hora mas guarda
        hora = ""
        match_hora = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if match_hora: 
            hora = match_hora.group(0).replace(":", "h") + " "
            raw = raw.replace(match_hora.group(0), "")

        # Tira stop words
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de"]
        for s in stops: raw = re.sub(rf'\b{s}\b', '', raw)
        
        # Formata
        desc = f"{hora}{raw.title()}".strip()
        # Procura instrutor na string original para garantir capitalização correta
        for inst in INSTRUTORES:
            if inst.lower() in texto:
                # Se o nome já não está na descrição (evitar duplicidade)
                if inst not in desc:
                    desc += f" ({inst})"

    return {"status": "ok", "data": data_obj, "tipo": tipo, "desc": desc}

def carregar_dados():
    if not supabase: return {}
    try:
        res = supabase.table("excecoes").select("*").execute()
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except: return {}

def salvar_dados(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({"data": d.strftime("%Y-%m-%d"), "tipo": t, "descricao": desc}).execute()
        st.cache_data.clear()

# --- 6. INTERFACE DE COMANDO (SIDEBAR) ---
with st.sidebar:
    st.markdown("### 🤖 Awake AI")
    st.info("Comandos rápidos: 'Dia 20 Recesso', 'Dia 15 Workshop 19h com Pat'...")
    
    prompt = st.chat_input("Digite o comando...")
    
    if prompt:
        res = nlp_parser(prompt, st.session_state.mes_idx)
        st.session_state['pending'] = res
        
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['status'] == 'ok':
            st.markdown(f"""
            <div style="border:1px solid {ACCENT_COLOR}; padding:15px; border-radius:10px; background:rgba(255,255,255,0.05); margin-bottom:15px">
                <div style="color:#aaa; font-size:12px">CONFIRMAR ALTERAÇÃO</div>
                <div style="font-weight:bold; color:white; font-size:16px">{p['data'].strftime('%d/%m')}</div>
                <div style="color:{ACCENT_COLOR}; font-size:14px">{p['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Aplicar"):
                salvar_dados(p['data'], p['tipo'], p['desc'])
                del st.session_state['pending']
                st.rerun()
            if c2.button("❌ Cancelar"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# --- 7. ÁREA PRINCIPAL (CALENDÁRIO) ---

# HEADER DE NAVEGAÇÃO
col_prev, col_title, col_next = st.columns([1, 6, 1])

with col_prev:
    st.write("") # Spacer
    st.write("") 
    if st.button("◀", key="prev"): mudar_mes(-1); st.rerun()

with col_next:
    st.write("") 
    st.write("")
    if st.button("▶", key="next"): mudar_mes(1); st.rerun()

with col_title:
    # Mostra o Header Personalizado
    st.markdown(f"""
    <div class="month-header-wrapper">
        <div>
            <div class="month-subtitle">Calendário 2026</div>
            <div class="month-title">{CURRENT_THEME['name']}</div>
        </div>
        <div style="text-align:right">
            <div style="color:{ACCENT_COLOR}; font-weight:bold; font-family:'JetBrains Mono'">AWAKE OS v8.0</div>
            <div style="color:#555; font-size:12px">Database Secure</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# CALCULA OS DIAS
cal = calendar.Calendar(firstweekday=6)
dias_mes = list(cal.itermonthdates(2026, st.session_state.mes_idx))
db_excecoes = carregar_dados()

# RENDERIZA O GRID (HTML PURO PARA PRECISÃO)
# 1. Cabeçalho dos dias
html_content = '<div class="cal-grid">'
for d in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]:
    html_content += f'<div class="weekday">{d}</div>'

# 2. Dias
for dia in dias_mes:
    # Define classes CSS
    classes = "day-card"
    if dia.month != st.session_state.mes_idx: classes += " is-past" # Opacidade baixa para outros meses
    elif dia < HOJE: classes += " is-past"
    elif dia == HOJE: classes += " is-today"
    
    # Conteúdo Interno
    inner_html = ""
    
    # A. Checa DB (Exceções)
    if dia in db_excecoes:
        exc = db_excecoes[dia]
        tipo = exc['tipo']
        desc = exc['descricao']
        
        chip_cls = "chip-especial"
        if tipo == "recesso": chip_cls = "chip-recesso"
        elif tipo == "cancelado": 
            inner_html += f'<div class="chip chip-recesso" style="text-decoration:line-through">Cancelado</div>'
        
        if tipo != "cancelado":
            inner_html += f'<div class="chip {chip_cls}">{desc}</div>'

    # B. Checa Feriado
    elif dia in FERIADOS_2026:
        inner_html += f'<div class="chip chip-feriado">🎈 {FERIADOS_2026[dia]}</div>'
        
    # C. Agenda Padrão (Só mostra se for do mês atual)
    elif dia.month == st.session_state.mes_idx:
        wd = dia.weekday()
        # Teca
        if wd == 1 and dia.month not in [1, 7]: 
            inner_html += '<div class="chip chip-teca">08h15 Talk Med.</div>'
        
        # Sound Healing
        sh = ""
        if wd == 0: sh = "19h SH (Haran)"
        elif wd == 1: sh = "19h SH (Karina)"
        elif wd == 2: sh = "19h SH (Pat)"
        elif wd == 3: sh = "19h SH (Pat)"
        elif wd == 4: sh = "19h SH (Haran)"
        elif wd == 5: sh = "10h SH (Karina)"
        
        if sh: inner_html += f'<div class="chip chip-sh">{sh}</div>'

    # Monta o Card
    html_content += f"""
    <div class="{classes}">
        <div class="day-num">
            {dia.day}
            {'<span style="font-size:9px; color:'+ACCENT_COLOR+'">HOJE</span>' if dia == HOJE else ''}
        </div>
        {inner_html}
    </div>
    """

html_content += '</div>'

# INJEÇÃO FINAL
st.markdown(html_content, unsafe_allow_html=True)
