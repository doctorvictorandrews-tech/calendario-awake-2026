import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime
import pytz
import re
import time

# ==============================================================================
# 1. CONFIGURAÇÃO (KERNEL)
# ==============================================================================
st.set_page_config(
    page_title="Awake OS",
    page_icon="🌑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Configurações de Ambiente
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# ==============================================================================
# 2. SUPABASE (DATABASE)
# ==============================================================================
@st.cache_resource
def init_db():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_db()

def get_data():
    if not supabase: return {}
    try:
        # Traz tudo para garantir performance
        res = supabase.table("excecoes").select("*").execute()
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except: return {}

def save_data(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({
            "data": d.strftime("%Y-%m-%d"), "tipo": t, "descricao": desc
        }).execute()
        st.cache_data.clear()

# ==============================================================================
# 3. DESIGN SYSTEM (CSS ECOFIN STYLE)
# ==============================================================================
st.markdown("""
    <style>
    /* 1. FONTES PREMIUM */
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400&display=swap');

    /* 2. VARIÁVEIS GLOBAIS (DARK THEME) */
    :root {
        --bg-body: #050505;
        --glass: rgba(255, 255, 255, 0.03);
        --border: rgba(255, 255, 255, 0.08);
        --text-main: #FFFFFF;
        --text-muted: #6B7280;
        --accent: #D9890D; /* Gold Ecofin */
        --primary: #10B981; /* Green Awake */
    }

    /* 3. RESET STREAMLIT */
    .stApp { background-color: var(--bg-body); font-family: 'Inter', sans-serif; color: var(--text-main); }
    header, footer, #MainMenu { display: none !important; }
    [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid var(--border); }
    
    /* Inputs Dark */
    .stChatInput textarea, .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
        background-color: #111 !important;
        border: 1px solid #333 !important;
        color: white !important;
        border-radius: 12px !important;
    }

    /* 4. COMPONENTES DO CALENDÁRIO */
    
    /* Header do Mês */
    .month-header {
        font-family: 'Manrope', sans-serif;
        font-size: 42px;
        font-weight: 800;
        background: linear-gradient(180deg, #fff 0%, #666 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 5px;
    }
    
    .year-header {
        font-family: 'JetBrains Mono', monospace;
        color: var(--primary);
        font-size: 14px;
        letter-spacing: 2px;
        text-transform: uppercase;
    }

    /* Card do Dia (A Mágica acontece aqui) */
    .day-container {
        background: var(--glass);
        border: 1px solid var(--border);
        border-radius: 16px;
        min-height: 160px;
        padding: 12px;
        display: flex;
        flex-direction: column;
        transition: all 0.3s ease;
        position: relative;
        backdrop-filter: blur(10px);
    }
    
    .day-container:hover {
        transform: translateY(-5px);
        border-color: var(--primary);
        background: rgba(255,255,255,0.06);
        box-shadow: 0 10px 40px -10px rgba(16, 185, 129, 0.2);
    }

    /* Estados */
    .is-today { border: 1px solid var(--primary); background: rgba(16, 185, 129, 0.05); }
    .is-past { opacity: 0.3; filter: grayscale(1); }
    .is-blur { opacity: 0.1; }

    /* Número do Dia */
    .day-num {
        font-family: 'Manrope', sans-serif;
        font-size: 20px;
        font-weight: 700;
        color: #555;
        margin-bottom: 12px;
        display: flex; 
        justify-content: space-between;
    }
    .is-today .day-num { color: white; }

    /* Tags/Chips */
    .tag {
        font-size: 11px;
        padding: 6px 10px;
        border-radius: 8px;
        margin-bottom: 6px;
        background: rgba(255,255,255,0.05);
        border-left: 2px solid #333;
        color: #ccc;
        font-weight: 500;
        line-height: 1.3;
    }

    /* Cores das Tags */
    .tag-sh { border-color: #10B981; color: #D1FAE5; background: rgba(16, 185, 129, 0.1); }
    .tag-teca { border-color: #8B5CF6; color: #EDE9FE; background: rgba(139, 92, 246, 0.1); }
    .tag-esp { border-color: #F59E0B; color: #FEF3C7; background: rgba(245, 158, 11, 0.1); }
    .tag-fer { border-color: #EF4444; color: #FEE2E2; background: rgba(239, 68, 68, 0.1); }
    .tag-off { border-color: #6B7280; color: #9CA3AF; border-style: dashed; }
    
    /* Botões Nav */
    .nav-btn { font-size: 24px; cursor: pointer; color: #444; transition: 0.3s; background:none; border:none; }
    .nav-btn:hover { color: white; transform: scale(1.2); }
    
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. INTELLIGENCE (NLP)
# ==============================================================================
def parse_command(text, month_idx):
    txt = text.lower()
    # Data
    d, m = None, month_idx
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', txt)
    match_day = re.search(r'\bdia (\d{1,2})\b', txt)
    
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_day: d = int(match_day.group(1))
    
    if not d: return {"ok": False, "msg": "Data não entendida."}
    try: date_obj = date(2026, m, d)
    except: return {"ok": False, "msg": "Data inválida."}
    
    # Tipo
    tipo = "especial"
    if "recesso" in txt: tipo = "recesso"
    elif any(x in txt for x in ["cancelar", "off", "remover"]): tipo = "cancelado"
    
    # Descrição Limpa
    desc = "CANCELADO" if tipo == "cancelado" else "RECESSO" if tipo == "recesso" else ""
    if tipo == "especial":
        raw = text
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw, flags=re.IGNORECASE)
        
        # Hora
        hora = ""
        hm = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if hm: 
            hora = hm.group(0).replace(":", "h") + " "
            raw = raw.replace(hm.group(0), "")
            
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de", "o", "a"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        act = pattern.sub('', raw).strip().title()
        
        # Instrutor
        instrs = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
        found = [i for i in instrs if i.lower() in txt]
        for i in found: act = act.replace(i, "").replace(i.lower(), "").strip()
        final_inst = f" ({found[0]})" if found else ""
        
        desc = f"{hora}{act}{final_inst}".strip()
        
    return {"ok": True, "data": date_obj, "tipo": tipo, "desc": desc}

# ==============================================================================
# 5. EXECUÇÃO PRINCIPAL
# ==============================================================================

# Controle de Mês
if 'mes_idx' not in st.session_state: st.session_state.mes_idx = datetime.now().month

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/11189/11189262.png", width=60)
    st.markdown("### Awake Intelligence")
    
    prompt = st.chat_input("Digite um comando...")
    if prompt:
        res = parse_command(prompt, st.session_state.mes_idx)
        st.session_state['pending'] = res
        
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['ok']:
            st.markdown(f"""
            <div style="background:#111; padding:15px; border-radius:10px; border:1px solid #333; margin-bottom:15px;">
                <div style="color:#666; font-size:10px; text-transform:uppercase;">Detectado</div>
                <div style="color:white; font-weight:bold; font-size:16px;">{p['data'].strftime('%d/%m')}</div>
                <div style="color:#D9890D;">{p['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("SALVAR"):
                save_data(p['data'], p['tipo'], p['desc'])
                del st.session_state['pending']
                st.rerun()
            if c2.button("CANCELAR"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# --- LAYOUT DO CALENDÁRIO ---

# 1. Header Navigation
c1, c2, c3 = st.columns([1, 10, 1])
with c1:
    st.write("")
    if st.button("◀", key="prev"): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()
with c3:
    st.write("")
    if st.button("▶", key="next"): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with c2:
    meses = {1:"JANEIRO", 2:"FEVEREIRO", 3:"MARÇO", 4:"ABRIL", 5:"MAIO", 6:"JUNHO", 7:"JULHO", 8:"AGOSTO", 9:"SETEMBRO", 10:"OUTUBRO", 11:"NOVEMBRO", 12:"DEZEMBRO"}
    st.markdown(f"""
    <div>
        <div class="year-header">Awake OS // 2026</div>
        <div class="month-header">{meses[st.session_state.mes_idx]}</div>
    </div>
    """, unsafe_allow_html=True)

# 2. Dados
cal = calendar.Calendar(firstweekday=6)
dias = list(cal.itermonthdates(2026, st.session_state.mes_idx))
excecoes = get_data()

feriados = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 6, 4): "Corpus Christi", date(2026, 7, 9): "Rev. 32", 
    date(2026, 9, 7): "Independência", date(2026, 10, 12): "N. Sra. Aparecida", 
    date(2026, 11, 2): "Finados", date(2026, 11, 15): "Proclamação", 
    date(2026, 11, 20): "Consciência", date(2026, 12, 25): "Natal"
}

# 3. Renderização (USANDO COLUNAS NATIVAS = SEGURANÇA)
cols_header = st.columns(7)
for i, d in enumerate(["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]):
    cols_header[i].markdown(f"<div style='text-align:center; color:#666; font-size:12px; font-weight:bold; margin-bottom:10px;'>{d}</div>", unsafe_allow_html=True)

# Loop principal - Quebra em semanas (chunks de 7)
chunks = [dias[i:i+7] for i in range(0, len(dias), 7)]

for semana in chunks:
    cols = st.columns(7)
    for i, dia in enumerate(semana):
        with cols[i]:
            # Define estados CSS
            css_class = "day-container"
            if dia == HOJE: css_class += " is-today"
            if dia < HOJE: css_class += " is-past"
            if dia.month != st.session_state.mes_idx: css_class += " is-blur"
            
            # Conteúdo HTML
            html_content = ""
            
            # A. DB
            if dia in excecoes:
                exc = excecoes[dia]
                if exc['tipo'] == 'recesso': html_content += f'<div class="tag tag-off">💤 {exc["descricao"]}</div>'
                elif exc['tipo'] == 'cancelado': html_content += f'<div class="tag tag-off" style="text-decoration:line-through">Cancelado</div>'
                else: html_content += f'<div class="tag tag-esp">★ {exc["descricao"]}</div>'
            
            # B. Feriado
            elif dia in feriados:
                html_content += f'<div class="tag tag-fer">🎈 {feriados[dia]}</div>'
            
            # C. Padrão (só se for do mês atual)
            elif dia.month == st.session_state.mes_idx:
                wd = dia.weekday()
                if wd == 1 and dia.month not in [1, 7]: html_content += '<div class="tag tag-teca">Talk Med.</div>'
                
                sh = ""
                if wd==0: sh = "19h SH (Haran)"
                elif wd==1: sh = "19h SH (Karina)"
                elif wd==2: sh = "19h SH (Pat)"
                elif wd==3: sh = "19h SH (Pat)"
                elif wd==4: sh = "19h SH (Haran)"
                elif wd==5: sh = "10h SH (Karina)"
                
                if sh: html_content += f'<div class="tag tag-sh">{sh}</div>'

            # Badge Hoje
            badge = '<span style="font-size:9px; color:#10B981; font-weight:800;">HOJE</span>' if dia == HOJE else ''
            
            # RENDERIZA CARD
            st.markdown(f"""
            <div class="{css_class}">
                <div class="day-num"><span>{dia.day}</span>{badge}</div>
                {html_content}
            </div>
            """, unsafe_allow_html=True)
