import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime, timedelta
import pytz
import re
import time

# ==============================================================================
# 1. CONFIGURAÇÃO DO KERNEL & SISTEMA
# ==============================================================================
st.set_page_config(
    page_title="Awake OS | Enterprise",
    page_icon="🌑",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Constantes de Ambiente
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# ==============================================================================
# 2. DESIGN SYSTEM & THEME ENGINE (CSS INJECTION)
# ==============================================================================

# Definição de Temas por Mês (Aura Colors)
THEME_COLORS = {
    1: "#10B981", # Jan: Emerald (Renovação)
    2: "#8B5CF6", # Fev: Violet (Intuição)
    3: "#3B82F6", # Mar: Royal Blue (Fluidez)
    4: "#EC4899", # Abr: Pink (Conexão)
    5: "#F59E0B", # Mai: Amber (Abundância)
    6: "#EF4444", # Jun: Red (Energia)
    7: "#06B6D4", # Jul: Cyan (Equilíbrio)
    8: "#6366F1", # Ago: Indigo (Profundidade)
    9: "#84CC16", # Set: Lime (Cura)
    10: "#F97316", # Out: Orange (Expansão)
    11: "#14B8A6", # Nov: Teal (Luz)
    12: "#E11D48", # Dez: Rose (Celebração)
}

# Controle de Sessão
if 'mes_idx' not in st.session_state:
    st.session_state.mes_idx = datetime.now().month

CURRENT_ACCENT = THEME_COLORS[st.session_state.mes_idx]

def inject_custom_css():
    """
    Injeta o CSS profissional com tratamento de escape para evitar erros de renderização.
    """
    css = f"""
    <style>
        /* IMPORTAÇÃO DE TIPOGRAFIA PREMIUM */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Manrope:wght@400;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

        /* VARIÁVEIS GLOBAIS (DESIGN TOKENS) */
        :root {{
            --bg-deep: #050505;
            --bg-surface: #0F0F0F;
            --glass-panel: rgba(255, 255, 255, 0.03);
            --glass-border: rgba(255, 255, 255, 0.06);
            --text-primary: #FFFFFF;
            --text-secondary: #9CA3AF;
            --text-tertiary: #4B5563;
            --accent-glow: {CURRENT_ACCENT};
            --success: #10B981;
            --danger: #EF4444;
            --font-sans: 'Inter', sans-serif;
            --font-display: 'Manrope', sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        /* RESET & BASE */
        .stApp {{
            background-color: var(--bg-deep);
            font-family: var(--font-sans);
            color: var(--text-primary);
        }}
        
        /* Ocultar elementos nativos do Streamlit */
        header, footer, #MainMenu {{ visibility: hidden; }}
        [data-testid="stSidebar"] {{ 
            background-color: #080808; 
            border-right: 1px solid var(--glass-border);
        }}

        /* --- BACKGROUND FX (AMBIENT LIGHTING) --- */
        .ambient-light {{
            position: fixed;
            width: 800px;
            height: 800px;
            background: var(--accent-glow);
            filter: blur(200px);
            opacity: 0.08;
            border-radius: 50%;
            z-index: 0;
            pointer-events: none;
        }}
        .light-1 {{ top: -20%; right: -10%; }}
        .light-2 {{ bottom: -20%; left: -10%; opacity: 0.05; }}

        /* --- COMPONENTES DE UI --- */

        /* 1. Header Navigation */
        .nav-container {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 40px 0 20px 0;
            margin-bottom: 40px;
            border-bottom: 1px solid var(--glass-border);
            position: relative;
            z-index: 10;
        }}
        
        .month-display {{
            font-family: var(--font-display);
            font-size: 48px;
            font-weight: 800;
            letter-spacing: -1.5px;
            line-height: 1;
            background: linear-gradient(180deg, #fff 0%, #aaa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .year-display {{
            font-family: var(--font-mono);
            color: var(--accent-glow);
            font-size: 14px;
            letter-spacing: 2px;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}

        /* 2. Grid System */
        .calendar-wrapper {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 16px;
            position: relative;
            z-index: 5;
        }}

        .weekday-header {{
            text-align: center;
            color: var(--text-tertiary);
            font-family: var(--font-mono);
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            padding-bottom: 10px;
        }}

        /* 3. Cards (O Coração do Design) */
        .day-card {{
            background: var(--glass-panel);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            min-height: 160px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
            backdrop-filter: blur(20px);
            position: relative;
            overflow: hidden;
        }}

        .day-card:hover {{
            transform: translateY(-5px) scale(1.02);
            border-color: var(--accent-glow);
            background: rgba(255,255,255,0.05);
            box-shadow: 0 20px 40px -10px rgba(0,0,0,0.5);
        }}

        /* Estados do Card */
        .state-past {{ opacity: 0.3; filter: grayscale(1); }}
        .state-active {{ 
            border: 1px solid var(--accent-glow); 
            background: linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,0,0,0) 100%);
            box-shadow: 0 0 30px var(--accent-glow)22;
        }}
        .state-other-month {{ opacity: 0.1; pointer-events: none; }}

        /* Conteúdo do Card */
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .day-number {{
            font-family: var(--font-display);
            font-size: 20px;
            font-weight: 700;
            color: var(--text-secondary);
        }}
        
        .state-active .day-number {{ color: #fff; }}

        .today-pill {{
            background: var(--accent-glow);
            color: #000;
            font-size: 9px;
            font-weight: 800;
            padding: 4px 8px;
            border-radius: 100px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        /* Events Chips */
        .event-stack {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .event-chip {{
            font-size: 11px;
            padding: 8px 10px;
            border-radius: 8px;
            background: rgba(255,255,255,0.03);
            border-left: 2px solid #555;
            color: #ccc;
            line-height: 1.3;
            transition: 0.2s;
        }}

        .event-chip:hover {{ background: rgba(255,255,255,0.08); }}

        /* Variantes de Eventos */
        .type-sh {{ border-color: #34D399; color: #D1FAE5; background: rgba(16, 185, 129, 0.1); }}
        .type-teca {{ border-color: #A78BFA; color: #EDE9FE; background: rgba(139, 92, 246, 0.1); }}
        .type-special {{ border-color: var(--accent-glow); color: #fff; background: rgba(255,255,255,0.1); border-left-width: 3px; }}
        .type-feriado {{ border-color: #F87171; color: #FECACA; background: rgba(239, 68, 68, 0.1); }}
        .type-recesso {{ border-color: #4B5563; color: #9CA3AF; border-style: dashed; }}
        
        /* Chat Input Styling */
        .stChatInput textarea {{
            background-color: #111 !important;
            border: 1px solid #333 !important;
            color: white !important;
            border-radius: 12px !important;
        }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ==============================================================================
# 3. BACKEND: SUPABASE & DATA LOGIC
# ==============================================================================

@st.cache_resource
def init_db():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_db()

def get_excecoes_db():
    if not supabase: return {}
    try:
        res = supabase.table("excecoes").select("*").execute()
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except: return {}

def save_excecao(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({
            "data": d.strftime("%Y-%m-%d"), 
            "tipo": t, 
            "descricao": desc
        }).execute()
        st.cache_data.clear()

# ==============================================================================
# 4. INTELLIGENCE ENGINE (NLP)
# ==============================================================================
def nlp_processor(text, current_month):
    text_clean = text.lower()
    
    # 1. Extração de Data
    d, m = None, current_month
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', text_clean)
    match_day = re.search(r'\bdia (\d{1,2})\b', text_clean)
    
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_day: d = int(match_day.group(1))
    
    if not d: return {"ok": False, "msg": "Data não identificada. Use 'Dia 20' ou '20/01'."}
    try: date_obj = date(2026, m, d)
    except: return {"ok": False, "msg": "Data inválida no calendário."}

    # 2. Identificação de Tipo
    tipo = "especial"
    if "recesso" in text_clean: tipo = "recesso"
    elif any(x in text_clean for x in ["cancelar", "off", "remover"]): tipo = "cancelado"

    # 3. Limpeza e Formatação da Descrição
    desc = "CANCELADO" if tipo == "cancelado" else "RECESSO" if tipo == "recesso" else ""
    
    if tipo == "especial":
        # Remove data e palavras inúteis
        raw = text
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw, flags=re.IGNORECASE)
        
        # Extrai hora
        hora = ""
        h_match = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if h_match: 
            hora = h_match.group(0).replace(":", "h") + " "
            raw = raw.replace(h_match.group(0), "")

        # Lista de Stop Words para limpar a frase
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de", "o", "a", "no", "na"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        activity = pattern.sub('', raw).strip().title()
        
        # Instrutores (preserva capitalização e adiciona se não estiver)
        instrutores = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
        found_instr = [i for i in instrutores if i.lower() in text_clean]
        
        # Remove nome do instrutor da atividade para não duplicar
        for i in found_instr: activity = activity.replace(i, "").replace(i.lower(), "").strip()
        
        final_instr = f" ({found_instr[0]})" if found_instr else ""
        desc = f"{hora}{activity}{final_instr}".strip()

    return {"ok": True, "data": date_obj, "tipo": tipo, "desc": desc}

# ==============================================================================
# 5. FRONT-END COMPONENTS (HTML GENERATORS)
# ==============================================================================

def render_header(mes_idx):
    meses = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
    nome_mes = meses[mes_idx]
    
    html = f"""
    <div class="nav-container">
        <div>
            <div class="year-display">AWAKE OS 2026</div>
            <div class="month-display">{nome_mes}</div>
        </div>
        <div style="display:flex; gap:15px; align-items:center;">
            <div style="text-align:right; font-size:12px; color:#555;">
                <span style="color:{CURRENT_ACCENT}">●</span> Database Connected<br>
                <span style="color:#333">v9.0 Enterprise</span>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_card(dia, is_today, is_past, is_other_month, feriado_txt, db_data):
    # Classes CSS
    state_cls = ""
    if is_other_month: state_cls = "state-other-month"
    elif is_today: state_cls = "state-active"
    elif is_past: state_cls = "state-past"

    # Conteúdo (HTML Building)
    content_html = ""
    
    # 1. Banco de Dados (Exceção Manual)
    if db_data:
        tipo = db_data['tipo']
        txt = db_data['descricao']
        
        cls_type = "type-special"
        if tipo == "recesso": cls_type = "type-recesso"
        elif tipo == "cancelado": 
            # Renderiza especial para cancelado
            return f"""
            <div class="day-card {state_cls}">
                <div class="card-header"><div class="day-number">{dia.day}</div></div>
                <div class="event-stack">
                    <div class="event-chip type-recesso" style="text-decoration:line-through">Cancelado</div>
                </div>
            </div>"""
        
        content_html += f'<div class="event-chip {cls_type}">{txt}</div>'

    # 2. Feriados
    elif feriado_txt:
        content_html += f'<div class="event-chip type-feriado">🎈 {feriado_txt}</div>'
    
    # 3. Agenda Padrão (Recorrente)
    elif not is_other_month:
        wd = dia.weekday()
        # Teca (Regra Complexa)
        if wd == 1 and dia.month not in [1, 7]:
            content_html += '<div class="event-chip type-teca">08h15 Talk Med.</div>'
        
        # Sound Healing (Regra Simples)
        sh_txt = ""
        if wd == 0: sh_txt = "19h SH (Haran)"
        elif wd == 1: sh_txt = "19h SH (Karina)"
        elif wd == 2: sh_txt = "19h SH (Pat)"
        elif wd == 3: sh_txt = "19h SH (Pat)"
        elif wd == 4: sh_txt = "19h SH (Haran)"
        elif wd == 5: sh_txt = "10h SH (Karina)"
        
        if sh_txt:
            content_html += f'<div class="event-chip type-sh">{sh_txt}</div>'

    # Montagem Final do Card
    pill_html = '<div class="today-pill">HOJE</div>' if is_today else ''
    
    return f"""
    <div class="day-card {state_cls}">
        <div class="card-header">
            <div class="day-number">{dia.day}</div>
            {pill_html}
        </div>
        <div class="event-stack">
            {content_html}
        </div>
    </div>
    """

# ==============================================================================
# 6. MAIN EXECUTION FLOW
# ==============================================================================

# Injeta CSS (Global)
inject_custom_css()

# Efeitos de Fundo
st.markdown('<div class="ambient-light light-1"></div><div class="ambient-light light-2"></div>', unsafe_allow_html=True)

# --- SIDEBAR (CONTROLE IA) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9626/9626620.png", width=50)
    st.markdown("### Awake Intelligence")
    st.caption("Digite comandos em linguagem natural.")
    
    prompt = st.chat_input("Ex: Dia 25/03 Workshop Tantra 19h")
    
    if prompt:
        res = nlp_processor(prompt, st.session_state.mes_idx)
        st.session_state['pending_action'] = res

    # Card de Confirmação (UI Dark)
    if 'pending_action' in st.session_state:
        act = st.session_state['pending_action']
        if act['ok']:
            st.markdown(f"""
            <div style="background:#111; border:1px solid {CURRENT_ACCENT}; border-radius:12px; padding:15px; margin-bottom:20px;">
                <div style="font-size:10px; color:#888; text-transform:uppercase;">Detectado</div>
                <div style="font-size:18px; font-weight:bold; color:white; margin:5px 0;">{act['data'].strftime('%d/%m')}</div>
                <div style="font-size:14px; color:{CURRENT_ACCENT}; padding-top:5px; border-top:1px solid #333;">{act['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            if c1.button("APLICAR", type="primary", use_container_width=True):
                save_excecao(act['data'], act['tipo'], act['desc'])
                del st.session_state['pending_action']
                st.rerun()
            if c2.button("DESCARTAR", use_container_width=True):
                del st.session_state['pending_action']
                st.rerun()
        else:
            st.error(act['msg'])
            del st.session_state['pending_action']

# --- MAIN LAYOUT ---

# Botões de Navegação (Usando colunas do Streamlit para lógica, mas CSS para estilo)
c_prev, c_main, c_next = st.columns([1, 10, 1])
with c_prev:
    st.write("") 
    st.write("") 
    if st.button("◀", key="nav_prev"): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()

with c_next:
    st.write("") 
    st.write("") 
    if st.button("▶", key="nav_next"): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with c_main:
    # 1. Render Header
    render_header(st.session_state.mes_idx)
    
    # 2. Setup Data
    cal = calendar.Calendar(firstweekday=6)
    dias_mes = list(cal.itermonthdates(2026, st.session_state.mes_idx))
    excecoes = get_excecoes_db()
    
    feriados_fixos = {
        date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
        date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
        date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
        date(2026, 6, 4): "Corpus Christi", date(2026, 7, 9): "Rev. 32", 
        date(2026, 9, 7): "Independência", date(2026, 10, 12): "N. Sra. Aparecida", 
        date(2026, 11, 2): "Finados", date(2026, 11, 15): "Proclamação", 
        date(2026, 11, 20): "Consciência", date(2026, 12, 25): "Natal"
    }

    # 3. Grid Construction (Safe HTML Injection)
    # Primeiro os dias da semana
    grid_html = '<div class="calendar-wrapper">'
    for wd in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]:
        grid_html += f'<div class="weekday-header">{wd}</div>'
    
    # Depois os Cards dos Dias
    for dia in dias_mes:
        is_today = (dia == HOJE)
        is_past = (dia < HOJE)
        is_other = (dia.month != st.session_state.mes_idx)
        
        # Verifica Dados
        db_exc = excecoes.get(dia)
        feriado = feriados_fixos.get(dia)
        
        # Gera HTML do Card Individual
        card_html = render_card(dia, is_today, is_past, is_other, feriado, db_exc)
        grid_html += card_html

    grid_html += '</div>'
    
    # Renderiza Grid Final
    st.markdown(grid_html, unsafe_allow_html=True)
