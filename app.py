import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime
import pytz
import re

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Awake OS",
    page_icon="🌑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. VARIÁVEIS DE AMBIENTE
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# Cores por Mês (Aura)
THEMES = {
    1: "#10B981", 2: "#8B5CF6", 3: "#3B82F6", 4: "#EC4899",
    5: "#F59E0B", 6: "#EF4444", 7: "#06B6D4", 8: "#6366F1",
    9: "#84CC16", 10: "#F97316", 11: "#14B8A6", 12: "#E11D48"
}

# Estado da Sessão (Navegação)
if 'mes_idx' not in st.session_state:
    st.session_state.mes_idx = datetime.now().month

CURRENT_ACCENT = THEMES[st.session_state.mes_idx]

# 3. CONEXÃO DATABASE (SUPABASE)
@st.cache_resource
def init_db():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_db()

def get_data():
    if not supabase: return {}
    try:
        res = supabase.table("excecoes").select("*").execute()
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except: return {}

def save_data(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({
            "data": d.strftime("%Y-%m-%d"), "tipo": t, "descricao": desc
        }).execute()
        st.cache_data.clear()

# 4. INTELLIGENCE ENGINE (NLP)
def smart_parser(text, month_idx):
    text_clean = text.lower()
    # Data
    d, m = None, month_idx
    match_f = re.search(r'(\d{1,2})/(\d{1,2})', text_clean)
    match_d = re.search(r'\bdia (\d{1,2})\b', text_clean)
    
    if match_f: d, m = int(match_f.group(1)), int(match_f.group(2))
    elif match_d: d = int(match_d.group(1))
    
    if not d: return {"ok": False, "msg": "Data não encontrada. Use 'Dia 20' ou '20/01'."}
    try: dt = date(2026, m, d)
    except: return {"ok": False, "msg": "Data inválida."}
    
    # Tipo
    tipo = "especial"
    if "recesso" in text_clean: tipo = "recesso"
    elif any(x in text_clean for x in ["cancelar", "off", "remover"]): tipo = "cancelado"
    
    # Descrição
    desc = "CANCELADO" if tipo == "cancelado" else "RECESSO" if tipo == "recesso" else ""
    if tipo == "especial":
        raw = text
        # Remove data
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw, flags=re.IGNORECASE)
        # Extrai hora
        hora = ""
        hm = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if hm: 
            hora = hm.group(0).replace(":", "h") + " "
            raw = raw.replace(hm.group(0), "")
        
        # Limpa palavras
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de", "o", "a", "no", "na"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        act = pattern.sub('', raw).strip().title()
        
        # Instrutor
        instrs = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
        found = [i for i in instrs if i.lower() in text_clean]
        for i in found: act = act.replace(i, "").replace(i.lower(), "").strip()
        
        final_inst = f" ({found[0]})" if found else ""
        desc = f"{hora}{act}{final_inst}".strip()
        
    return {"ok": True, "data": dt, "tipo": tipo, "desc": desc}

# 5. CSS INJECTION (O SEGREDO DO DESIGN)
def inject_css():
    # CSS Estático (Seguro)
    css_static = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700;800&family=Inter:wght@300;400;600&display=swap');
        
        :root {
            --bg: #050505;
            --surface: #121212;
            --border: rgba(255,255,255,0.08);
            --text-main: #FFFFFF;
            --text-dim: #9CA3AF;
        }
        
        /* Reset Global */
        .stApp { background-color: var(--bg); font-family: 'Inter', sans-serif; color: var(--text-main); }
        header, footer, #MainMenu { display: none !important; }
        
        /* Sidebar Dark */
        [data-testid="stSidebar"] { background-color: #0A0A0A; border-right: 1px solid var(--border); }
        
        /* Inputs Customizados */
        .stChatInput textarea, .stTextInput input {
            background-color: #1A1A1A !important;
            border: 1px solid #333 !important;
            color: white !important;
            border-radius: 8px !important;
        }
        
        /* Header Navigation */
        .nav-header {
            display: flex; justify-content: space-between; align-items: flex-end;
            padding: 40px 0 20px; border-bottom: 1px solid var(--border); margin-bottom: 30px;
        }
        .app-title { font-family: 'Manrope', sans-serif; font-size: 14px; color: var(--text-dim); letter-spacing: 3px; text-transform: uppercase; }
        .month-title { font-family: 'Manrope', sans-serif; font-size: 48px; font-weight: 800; line-height: 1; letter-spacing: -1px; margin-top: 10px; }
        
        /* Grid Layout */
        .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 12px; }
        .weekday { text-align: center; color: var(--text-dim); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; padding-bottom: 10px; font-weight: 600; }
        
        /* Card Design */
        .day-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid var(--border);
            border-radius: 12px;
            min-height: 150px;
            padding: 12px;
            display: flex; flex-direction: column;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            backdrop-filter: blur(10px);
        }
        .day-card:hover {
            background: rgba(255,255,255,0.06);
            transform: translateY(-4px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        }
        
        .day-num { font-family: 'Manrope', sans-serif; font-size: 18px; font-weight: 700; color: #555; margin-bottom: 10px; display: flex; justify-content: space-between; }
        .is-today .day-num { color: white; }
        
        /* Chips */
        .chip { font-size: 11px; padding: 6px 10px; border-radius: 6px; margin-bottom: 6px; background: rgba(255,255,255,0.05); color: #ddd; border-left: 2px solid #555; line-height: 1.3; }
    </style>
    """
    
    # CSS Dinâmico (Cores)
    css_dynamic = f"""
    <style>
        :root {{ --accent: {CURRENT_ACCENT}; }}
        .month-title {{
            background: linear-gradient(180deg, #FFFFFF 0%, {CURRENT_ACCENT} 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .is-today {{ border: 1px solid var(--accent); background: linear-gradient(180deg, var(--accent)11 0%, rgba(0,0,0,0) 100%); }}
        .day-card:hover {{ border-color: var(--accent); }}
        
        /* Variantes de Chip Dinâmicas */
        .chip-sp {{ border-color: var(--accent); background: linear-gradient(90deg, var(--accent)22, transparent); }}
        .chip-teca {{ border-color: #A78BFA; background: rgba(139,92,246,0.1); color: #E9D5FF; }}
        .chip-sh {{ border-color: #34D399; background: rgba(16,185,129,0.1); color: #D1FAE5; }}
        .chip-feriado {{ border-color: #F87171; background: rgba(239,68,68,0.1); color: #FECACA; }}
        .chip-recesso {{ border-color: #6B7280; border-style: dashed; opacity: 0.7; }}
        
        /* Glow Ambiental */
        .glow-fx {{
            position: fixed; top: -20%; right: -10%; width: 600px; height: 600px;
            background: var(--accent); filter: blur(250px); opacity: 0.15; z-index: -1; pointer-events: none;
        }}
    </style>
    """
    
    st.markdown(css_static + css_dynamic, unsafe_allow_html=True)
    st.markdown('<div class="glow-fx"></div>', unsafe_allow_html=True)

# 6. RENDER COMPONENTS
def render_calendar():
    meses = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
    
    # 1. Header
    st.markdown(f"""
    <div class="nav-header">
        <div>
            <div class="app-title">Awake OS // Enterprise</div>
            <div class="month-title">{meses[st.session_state.mes_idx]}</div>
        </div>
        <div style="text-align:right; font-size:12px; color:#666;">
            Database Connected<br><span style="color:{CURRENT_ACCENT}">● Online</span>
        </div>
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

    # 3. Grid Builder (Lista Segura)
    html_parts = ['<div class="cal-grid">']
    
    # Headers
    for d in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]:
        html_parts.append(f'<div class="weekday">{d}</div>')
        
    # Cards
    for dia in dias:
        # Classes
        classes = "day-card"
        if dia == HOJE: classes += " is-today"
        if dia.month != st.session_state.mes_idx or dia < HOJE: classes += " is-past"
        if dia.month != st.session_state.mes_idx: 
             # Opacidade extra para outro mês
             style = 'style="opacity:0.2;"'
        else:
             style = ''

        # Conteúdo
        content = ""
        
        # A. DB
        if dia in excecoes:
            exc = excecoes[dia]
            if exc['tipo'] == 'recesso':
                content += f'<div class="chip chip-recesso">💤 {exc["descricao"]}</div>'
            elif exc['tipo'] == 'cancelado':
                content += '<div class="chip chip-recesso" style="text-decoration:line-through">Cancelado</div>'
            else:
                content += f'<div class="chip chip-sp">★ {exc["descricao"]}</div>'
                
        # B. Feriado
        elif dia in feriados:
            content += f'<div class="chip chip-feriado">🎈 {feriados[dia]}</div>'
            
        # C. Padrão
        elif dia.month == st.session_state.mes_idx:
            wd = dia.weekday()
            # Teca
            if wd == 1 and dia.month not in [1, 7]: content += '<div class="chip chip-teca">08h15 Talk Med.</div>'
            # SH
            sh = ""
            if wd == 0: sh = "19h SH (Haran)"
            elif wd == 1: sh = "19h SH (Karina)"
            elif wd == 2: sh = "19h SH (Pat)"
            elif wd == 3: sh = "19h SH (Pat)"
            elif wd == 4: sh = "19h SH (Haran)"
            elif wd == 5: sh = "10h SH (Karina)"
            if sh: content += f'<div class="chip chip-sh">{sh}</div>'

        # Montagem
        badge = '<span style="font-size:9px; font-weight:800; color:var(--accent)">HOJE</span>' if dia == HOJE else ''
        card = f"""
        <div class="{classes}" {style}>
            <div class="day-num"><span>{dia.day}</span>{badge}</div>
            <div style="display:flex; flex-direction:column; gap:4px;">{content}</div>
        </div>
        """
        html_parts.append(card)
        
    html_parts.append('</div>')
    
    # Render Final Seguro
    st.markdown("".join(html_parts), unsafe_allow_html=True)

# 7. EXECUÇÃO
inject_css()

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2040/2040504.png", width=40)
    st.caption("Awake Intelligence v10.0")
    
    prompt = st.chat_input("Ex: Dia 20 Workshop de Tantra 19h")
    
    if prompt:
        res = smart_parser(prompt, st.session_state.mes_idx)
        st.session_state['pending'] = res
        
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['ok']:
            st.markdown(f"""
            <div style="background:#111; padding:15px; border-radius:10px; border:1px solid {CURRENT_ACCENT}; margin-bottom:15px;">
                <div style="color:#aaa; font-size:10px">DETECTADO</div>
                <div style="color:white; font-weight:bold">{p['data'].strftime('%d/%m')}</div>
                <div style="color:{CURRENT_ACCENT}">{p['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("✅ SALVAR"):
                save_data(p['data'], p['tipo'], p['desc'])
                del st.session_state['pending']
                st.rerun()
            if c2.button("❌ DESCARTAR"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# Main
c1, c2, c3 = st.columns([1, 10, 1])
with c1:
    st.write("")
    st.write("")
    if st.button("◀", key="prev"): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()
with c3:
    st.write("")
    st.write("")
    if st.button("▶", key="next"): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with c2:
    render_calendar()
