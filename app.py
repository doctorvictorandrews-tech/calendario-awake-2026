import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime
import pytz
import re
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Awake Calendar", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# --- 2. UI/UX PREMIUM (APPLE STYLE) ---
st.markdown("""
    <style>
    /* Reset e Fontes Nativas (Estilo Apple/System) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
    
    :root {
        --primary: #2E7D32;
        --bg-color: #F5F5F7; /* Cinza Apple */
        --card-bg: #FFFFFF;
        --text-main: #1D1D1F;
        --text-secondary: #86868B;
        --border-color: #D2D2D7;
    }

    .stApp {
        background-color: var(--bg-color);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Esconde elementos nativos do Streamlit */
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E5E5E5; }

    /* HEADER */
    .header-box {
        background: white;
        padding: 24px 32px;
        border-radius: 18px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        margin-bottom: 24px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .month-title { font-size: 24px; font-weight: 600; color: var(--text-main); letter-spacing: -0.5px; }
    .year-subtitle { color: var(--text-secondary); font-weight: 400; }

    /* GRID SYSTEM */
    .calendar-container {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
        margin-bottom: 40px;
    }
    
    .weekday-label {
        text-align: center;
        color: var(--text-secondary);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }

    /* CARD DO DIA */
    .day-card {
        background: var(--card-bg);
        border-radius: 14px;
        padding: 10px;
        min-height: 140px;
        border: 1px solid rgba(0,0,0,0.05);
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        display: flex;
        flex-direction: column;
    }
    
    .day-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 24px rgba(0,0,0,0.08);
        border-color: var(--primary);
        z-index: 10;
    }

    .day-number {
        font-size: 16px;
        font-weight: 600;
        color: var(--text-main);
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* ESTADOS */
    .is-today { border: 2px solid var(--primary); background-color: #F2FDF5; }
    .is-past { opacity: 0.5; background-color: #Fbfbfb; filter: grayscale(0.8); }
    .is-other-month { opacity: 0.2; background-color: #eeeeee; }

    /* CHIPS (EVENTOS) */
    .chip {
        font-size: 10px;
        padding: 6px 10px;
        border-radius: 8px;
        margin-bottom: 5px;
        font-weight: 500;
        line-height: 1.4;
        display: flex;
        align-items: center;
    }
    
    /* Cores Semânticas */
    .c-sh { background: #E8F5E9; color: #1B5E20; border-left: 3px solid #2E7D32; }
    .c-teca { background: #F3E5F5; color: #6A1B9A; border-left: 3px solid #8E24AA; }
    .c-especial { background: #FFF8E1; color: #F57F17; border-left: 3px solid #FFCA28; }
    .c-feriado { background: #FFEBEE; color: #C62828; border-left: 3px solid #EF5350; }
    .c-recesso { background: #ECEFF1; color: #546E7A; border-left: 3px solid #B0BEC5; }
    
    .today-badge {
        background-color: var(--primary);
        color: white;
        font-size: 9px;
        padding: 2px 6px;
        border-radius: 100px;
        font-weight: 700;
        text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. CONEXÃO SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except: return None

supabase = init_connection()

# --- 4. INTELIGÊNCIA NLP ---
INSTRUTORES = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]

def nlp_parser(texto, mes_visivel):
    texto_orig = texto
    texto = texto.lower()
    
    # Data
    d, m = None, None
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', texto)
    match_dia = re.search(r'\bdia (\d{1,2})\b', texto)
    
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_dia: d, m = int(match_dia.group(1)), mes_visivel
    
    if not d: return {"status": "erro", "msg": "Indique a data (ex: dia 20 ou 20/01)"}
    try: data_obj = date(2026, m, d)
    except: return {"status": "erro", "msg": "Data inválida."}

    # Tipo
    tipo = "especial"
    if "recesso" in texto: tipo = "recesso"
    elif any(x in texto for x in ["cancelar", "remover", "off"]): tipo = "cancelado"

    desc = ""
    if tipo == "recesso": desc = "RECESSO"
    elif tipo == "cancelado": desc = "CANCELADO"
    else:
        # Hora
        hora = ""
        match_hora = re.search(r'(\d{1,2})[h:](\d{0,2})', texto)
        if match_hora: hora = match_hora.group(0).replace(":", "h") + " "
        
        # Instrutor
        instrutor = ""
        for nome in INSTRUTORES:
            if nome.lower() in texto: instrutor = f" ({nome})"
        
        # Limpeza
        raw = texto_orig
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw, flags=re.IGNORECASE)
        if match_hora: raw = raw.replace(match_hora.group(0), "")
        
        stops = ["substitua", "troque", "pelo", "pela", "por", "que", "será", "com", "as", "às", "o", "a", "sh", "sound", "healing", "do", "de", "da"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        act = pattern.sub('', raw).strip().title()
        
        desc = f"{hora}{act}{instrutor}".strip()
        # Remove parenteses duplicados se houver erro de parsing
        desc = desc.replace("()", "")

    return {"status": "ok", "data": data_obj, "tipo": tipo, "desc": desc}

# --- 5. LÓGICA DE DADOS ---
FERIADOS = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 6, 4): "Corpus Christi", date(2026, 7, 9): "Rev. 32", 
    date(2026, 9, 7): "Independência", date(2026, 10, 12): "N. Sra. Aparecida", 
    date(2026, 11, 2): "Finados", date(2026, 11, 15): "Proclamação", 
    date(2026, 11, 20): "Consciência", date(2026, 12, 25): "Natal"
}
MESES = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}

def get_db():
    if not supabase: return {}
    try:
        res = supabase.table("excecoes").select("*").execute()
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except: return {}

def save_db(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({"data": d.strftime("%Y-%m-%d"), "tipo": t, "descricao": desc}).execute()
        st.cache_data.clear()

# --- 6. RENDERIZAÇÃO ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9370/9370278.png", width=40)
    st.markdown("### Awake Admin")
    
    mes_idx = st.selectbox("Mês", list(MESES.keys()), format_func=lambda x: MESES[x], index=datetime.now().month-1)
    
    st.markdown("---")
    st.markdown("**Comando Inteligente**")
    prompt = st.chat_input("Ex: Dia 20 Sound Healing vira Ritual 19h com Karina")
    
    if prompt:
        res = nlp_parser(prompt, mes_idx)
        st.session_state['p'] = res
    
    if 'p' in st.session_state:
        r = st.session_state['p']
        if r['status'] == 'ok':
            st.info(f"📅 {r['data'].strftime('%d/%m')}\n\n📝 {r['desc']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar"):
                save_db(r['data'], r['tipo'], r['desc'])
                del st.session_state['p']
                st.rerun()
            if c2.button("❌ Cancelar"):
                del st.session_state['p']
                st.rerun()
        else:
            st.error(r['msg'])
            del st.session_state['p']

# MAIN VIEW
db = get_db()
cal = calendar.Calendar(firstweekday=6)
dias = list(cal.itermonthdates(2026, mes_idx))

# Header
st.markdown(f"""
<div class="header-box">
    <div>
        <div class="month-title">{MESES[mes_idx]} <span class="year-subtitle">2026</span></div>
    </div>
    <div style="color:var(--primary); font-weight:600; font-size:14px">Awake Health</div>
</div>
""", unsafe_allow_html=True)

# Grid - Dias da Semana
st.markdown('<div class="calendar-container" style="margin-bottom:10px">' + 
"".join([f'<div class="weekday-label">{d}</div>' for d in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]]) + 
'</div>', unsafe_allow_html=True)

# Grid - Dias
html = '<div class="calendar-container">'
for dia in dias:
    # Classes CSS
    cls = "day-card"
    if dia.month != mes_idx: cls += " is-other-month"
    elif dia < HOJE: cls += " is-past"
    elif dia == HOJE: cls += " is-today"
    
    # Conteúdo
    content = ""
    
    # 1. DB (Prioridade)
    if dia in db:
        item = db[dia]
        t, d_txt = item['tipo'], item['descricao']
        c_cls = "c-especial"
        if t == "recesso": c_cls = "c-recesso"
        elif t == "cancelado": 
            content += f'<div class="chip c-recesso" style="text-decoration:line-through">Cancelado</div>'
        
        if t != "cancelado":
            content += f'<div class="chip {c_cls}">{d_txt}</div>'
            
    # 2. Feriado
    elif dia in FERIADOS:
        content += f'<div class="chip c-feriado">🎈 {FERIADOS[dia]}</div>'
        
    # 3. Padrão
    elif dia.month == mes_idx:
        w = dia.weekday()
        # Regra Teca
        if w == 1 and dia.month not in [1, 7]: content += '<div class="chip c-teca">08h15 Talk Med.</div>'
        # Regra SH
        sh = None
        if w == 0: sh = "19h SH (Haran)"
        elif w == 1: sh = "19h SH (Karina)"
        elif w == 2: sh = "19h SH (Pat)"
        elif w == 3: sh = "19h SH (Pat)"
        elif w == 4: sh = "19h SH (Haran)"
        elif w == 5: sh = "10h SH (Karina)"
        
        if sh: content += f'<div class="chip c-sh">{sh}</div>'

    # Montagem do HTML
    badge_hoje = '<span class="today-badge">HOJE</span>' if dia == HOJE else ''
    html += f"""
    <div class="{cls}">
        <div class="day-number">
            {dia.day}
            {badge_hoje}
        </div>
        {content}
    </div>
    """

html += '</div>'

# RENDERIZAÇÃO FINAL (O SEGREDO PARA NÃO MOSTRAR CÓDIGO)
st.markdown(html, unsafe_allow_html=True)
