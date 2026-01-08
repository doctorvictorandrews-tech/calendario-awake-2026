import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime
import pytz
import re

# ==============================================================================
# 1. CONFIGURAÇÃO (KERNEL)
# ==============================================================================
st.set_page_config(
    page_title="Awake OS",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# ==============================================================================
# 2. DESIGN SYSTEM "CLEAN PRO"
# ==============================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&family=JetBrains+Mono:wght@400&display=swap');

    :root {
        --bg: #0E1117;           /* Fundo Base Streamlit */
        --card-bg: #1A1C24;      /* Fundo do Card */
        --card-border: #2B2F3B;  /* Borda Sutil */
        --text-main: #FFFFFF;
        --text-sub: #9CA3AF;
        --accent: #10B981;       /* Verde Awake */
        --highlight: #D9890D;    /* Dourado Ecofin */
    }

    /* REMOVER BAGUNÇA NATIVA */
    header, footer, #MainMenu { display: none !important; }
    .stApp { background-color: var(--bg); font-family: 'Inter', sans-serif; }
    
    /* INPUT DE COMANDO GIGANTE */
    .stTextInput div[data-baseweb="input"] {
        background-color: #16181D !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
        padding: 10px !important;
    }
    .stTextInput input {
        color: white !important;
        font-size: 18px !important;
        font-family: 'Inter', sans-serif !important;
    }
    .stTextInput label {
        font-size: 16px !important;
        color: var(--text-sub) !important;
        font-weight: 600 !important;
    }

    /* HEADER */
    .header-wrapper {
        display: flex; justify-content: space-between; align-items: flex-end;
        padding-bottom: 20px; border-bottom: 1px solid var(--card-border); margin-bottom: 30px;
    }
    .big-month { font-size: 42px; font-weight: 800; color: white; letter-spacing: -1px; line-height: 1; }
    .year-label { font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--text-sub); text-transform: uppercase; }

    /* CARD DO DIA (Clean & Minimal) */
    .day-box {
        background-color: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 8px;
        min-height: 140px;
        padding: 12px;
        display: flex; flex-direction: column;
        transition: 0.2s;
    }
    .day-box:hover {
        border-color: var(--text-sub);
        background-color: #22252E;
        transform: translateY(-2px);
    }
    
    /* Estados */
    .is-today { border: 1px solid var(--accent); background: rgba(16, 185, 129, 0.05); }
    .is-past { opacity: 0.4; filter: grayscale(1); }
    .is-blur { opacity: 0.15; pointer-events: none; }

    /* Tipografia do Card */
    .day-num { font-size: 20px; font-weight: 700; color: #555; margin-bottom: 10px; display: flex; justify-content: space-between; }
    .is-today .day-num { color: var(--accent); }
    .day-num span { font-size: 10px; background: var(--accent); color: #000; padding: 2px 6px; border-radius: 4px; }

    /* Chips (Eventos) */
    .evt { font-size: 12px; padding: 6px 10px; border-radius: 6px; margin-bottom: 5px; line-height: 1.4; border-left: 3px solid; color: #eee; }
    
    .evt-sh { background: rgba(16, 185, 129, 0.1); border-color: var(--accent); color: #A7F3D0; }
    .evt-teca { background: rgba(139, 92, 246, 0.1); border-color: #8B5CF6; color: #E9D5FF; }
    .evt-special { background: rgba(245, 158, 11, 0.1); border-color: var(--highlight); color: #FDE68A; }
    .evt-off { background: rgba(255,255,255,0.05); border-color: #555; color: #888; border-style: dashed; }
    .evt-fer { background: rgba(239, 68, 68, 0.15); border-color: #EF4444; color: #FECACA; }

    /* Botões Nav */
    .nav-btn {
        background: none; border: 1px solid #333; color: #888; 
        padding: 8px 16px; border-radius: 8px; cursor: pointer; transition: 0.2s;
    }
    .nav-btn:hover { border-color: #fff; color: #fff; background: #222; }

    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. CONEXÃO DATABASE
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
# 4. CÉREBRO (NLP AVANÇADO)
# ==============================================================================
def advanced_parser(text, current_month):
    txt = text.lower()
    
    # 1. Mapa de Meses (Texto -> Número)
    meses_map = {
        "jan":1, "janeiro":1, "fev":2, "fevereiro":2, "mar":3, "março":3, "abr":4, "abril":4,
        "mai":5, "maio":5, "jun":6, "junho":6, "jul":7, "julho":7, "ago":8, "agosto":8,
        "set":9, "setembro":9, "out":10, "outubro":10, "nov":11, "novembro":11, "dez":12, "dezembro":12
    }
    
    # 2. Mapa de Números (Extenso -> Dígito)
    nums_map = {
        "um":1, "dois":2, "três":3, "quatro":4, "cinco":5, "seis":6, "sete":7, "oito":8, "nove":9, "dez":10,
        "vinte":20, "trinta":30, "primeiro":1
    }

    # 3. Detecção de Data
    dia, mes = None, current_month
    
    # Tenta achar nome de mês na frase
    for k, v in meses_map.items():
        if k in txt: mes = v
    
    # Tenta achar "20/01"
    match_slash = re.search(r'(\d{1,2})/(\d{1,2})', txt)
    # Tenta achar "dia 20"
    match_dia_num = re.search(r'\bdia\s+(\d{1,2})', txt)
    # Tenta achar número solto se não tiver os anteriores (arriscado, mas útil)
    match_num_loose = re.search(r'\b(\d{1,2})\b', txt)

    if match_slash:
        dia, mes = int(match_slash.group(1)), int(match_slash.group(2))
    elif match_dia_num:
        dia = int(match_dia_num.group(1))
    elif match_num_loose:
        # Só aceita número solto se parecer um dia válido (1-31) e não for hora
        val = int(match_num_loose.group(1))
        if 1 <= val <= 31 and f"{val}h" not in txt:
            dia = val

    if not dia:
        return {"ok": False, "msg": "Não entendi a data. Tente 'Dia 20' ou '20/01'."}

    try: dt = date(2026, mes, dia)
    except: return {"ok": False, "msg": "Data inválida no calendário."}

    # 4. Detecção de Intenção (Tipo)
    tipo = "especial"
    if any(x in txt for x in ["recesso", "feriado", "folga"]): tipo = "recesso"
    elif any(x in txt for x in ["cancelar", "cancelado", "off", "remover", "tirar", "excluir"]): tipo = "cancelado"

    # 5. Limpeza Cirúrgica da Descrição
    desc = ""
    if tipo == "recesso": desc = "RECESSO"
    elif tipo == "cancelado": desc = "CANCELADO"
    else:
        raw = text # Usa texto original para manter Maiúsculas/Minúsculas
        
        # Remove a data encontrada
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(rf'\bdia\s+{dia}\b', '', raw, flags=re.IGNORECASE)
        raw = re.sub(rf'\b{dia}\b', '', raw) # Remove o número do dia solto

        # Remove mês se houver
        for m_name in meses_map.keys():
            raw = re.sub(rf'\b{m_name}\b', '', raw, flags=re.IGNORECASE)

        # Captura Hora (Ex: 19h, 19:30)
        hora_str = ""
        match_hora = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if match_hora:
            hora_str = match_hora.group(0).replace(":", "h")
            if "h" not in hora_str: hora_str += "h"
            raw = raw.replace(match_hora.group(0), "") # Remove a hora do texto cru

        # Lista de "Lixo" para remover
        garbage = [
            "substitua", "troque", "altere", "mude", "coloque", "insira", "agende",
            "sh", "sound", "healing", "pelo", "pela", "por", "que", "sera", "será", 
            "vai", "ter", "com", "as", "às", "do", "da", "de", "no", "na", "o", "a", "para",
            "experiência", "aula", "sessão"
        ]
        
        # Remove lixo
        clean_pattern = re.compile(r'\b(' + '|'.join(garbage) + r')\b', re.IGNORECASE)
        activity = clean_pattern.sub(' ', raw)
        
        # Identifica Instrutor (Preserva nome)
        instrutores = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana", "Victor"]
        found_instr = None
        for instr in instrutores:
            if instr.lower() in activity.lower():
                found_instr = instr
                # Remove nome do instrutor do meio do texto para por no final
                activity = re.sub(instr, "", activity, flags=re.IGNORECASE)
                break
        
        # Formatação Final
        activity = " ".join(activity.split()).title() # Remove espaços duplos
        final_instr_str = f" ({found_instr})" if found_instr else ""
        
        desc = f"{hora_str} {activity}{final_instr_str}".strip()

    return {"ok": True, "data": dt, "tipo": tipo, "desc": desc}

# ==============================================================================
# 5. EXECUÇÃO DA INTERFACE
# ==============================================================================

# Sessão
if 'mes_idx' not in st.session_state: st.session_state.mes_idx = datetime.now().month

# --- BARRA DE COMANDO (HERO SECTION) ---
st.markdown("<br>", unsafe_allow_html=True)
col_input, col_status = st.columns([4, 1])

with col_input:
    command = st.text_input("Comando Awake", placeholder="Ex: Dia 25 Yoga Sound Bath às 9h com Pat", label_visibility="collapsed")

if command:
    res = advanced_parser(command, st.session_state.mes_idx)
    if res['ok']:
        # Confirmação Visual Imediata
        st.success(f"Entendido! {res['data'].strftime('%d/%m')} será: {res['desc']}")
        st.session_state['pending'] = res
    else:
        st.error(res['msg'])

# Botões de Ação (Aparecem só se houver pendência)
if 'pending' in st.session_state:
    p = st.session_state['pending']
    c1, c2 = st.columns([1, 4])
    if c1.button("✅ SALVAR ALTERAÇÃO", type="primary"):
        save_data(p['data'], p['tipo'], p['desc'])
        del st.session_state['pending']
        st.rerun()
    if c2.button("DESCARTAR"):
        del st.session_state['pending']
        st.rerun()

st.divider()

# --- NAVEGAÇÃO ---
c_prev, c_title, c_next = st.columns([1, 8, 1])

with c_prev:
    if st.button("◀", key="prev", use_container_width=True): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()

with c_next:
    if st.button("▶", key="next", use_container_width=True): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with c_title:
    meses_nomes = {1:"JANEIRO", 2:"FEVEREIRO", 3:"MARÇO", 4:"ABRIL", 5:"MAIO", 6:"JUNHO", 7:"JULHO", 8:"AGOSTO", 9:"SETEMBRO", 10:"OUTUBRO", 11:"NOVEMBRO", 12:"DEZEMBRO"}
    st.markdown(f"""
    <div class="header-wrapper">
        <div class="big-month">{meses_nomes[st.session_state.mes_idx]}</div>
        <div class="year-label">2026 • AWAKE OS</div>
    </div>
    """, unsafe_allow_html=True)

# --- GRID DO CALENDÁRIO ---
cal = calendar.Calendar(firstweekday=6)
dias = list(cal.itermonthdates(2026, st.session_state.mes_idx))
db_data = get_data()

feriados = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 7, 9): "Rev. 32", date(2026, 9, 7): "Independência",
    date(2026, 10, 12): "N. Sra. Aparecida", date(2026, 11, 2): "Finados",
    date(2026, 11, 15): "Proclamação", date(2026, 11, 20): "Consciência",
    date(2026, 12, 25): "Natal"
}

# 1. Cabeçalho Dias
cols_h = st.columns(7)
for i, d in enumerate(["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]):
    cols_h[i].markdown(f"<div style='text-align:center; color:#666; font-size:12px; font-weight:bold; margin-bottom:10px;'>{d}</div>", unsafe_allow_html=True)

# 2. Dias
chunks = [dias[i:i+7] for i in range(0, len(dias), 7)]

for semana in chunks:
    cols = st.columns(7)
    for i, dia in enumerate(semana):
        with cols[i]:
            # Estados
            css_class = "day-box"
            if dia == HOJE: css_class += " is-today"
            if dia < HOJE: css_class += " is-past"
            if dia.month != st.session_state.mes_idx: css_class += " is-blur"
            
            # Conteúdo
            html = ""
            
            # A. DB (Supabase)
            if dia in db_data:
                item = db_data[dia]
                t = item['tipo']
                if t == 'recesso': html += f'<div class="evt evt-off">💤 {item["descricao"]}</div>'
                elif t == 'cancelado': html += f'<div class="evt evt-off" style="text-decoration:line-through">Cancelado</div>'
                else: html += f'<div class="evt evt-special">★ {item["descricao"]}</div>'
            
            # B. Feriado
            elif dia in feriados:
                html += f'<div class="evt evt-fer">🎈 {feriados[dia]}</div>'
            
            # C. Padrão
            elif dia.month == st.session_state.mes_idx:
                wd = dia.weekday()
                if wd == 1 and dia.month not in [1, 7]: html += '<div class="evt evt-teca">Talk Med.</div>'
                
                sh = ""
                if wd==0: sh = "19h SH (Haran)"
                elif wd==1: sh = "19h SH (Karina)"
                elif wd==2: sh = "19h SH (Pat)"
                elif wd==3: sh = "19h SH (Pat)"
                elif wd==4: sh = "19h SH (Haran)"
                elif wd==5: sh = "10h SH (Karina)"
                
                if sh: html += f'<div class="evt evt-sh">{sh}</div>'

            # Badge Hoje
            badge = '<span>HOJE</span>' if dia == HOJE else ''
            
            # Render
            st.markdown(f"""
            <div class="{css_class}">
                <div class="day-num">
                    {dia.day}
                    {badge}
                </div>
                {html}
            </div>
            """, unsafe_allow_html=True)
