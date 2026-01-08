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
    page_title="Awake Calendar",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# ==============================================================================
# 2. CONEXÃO COM BANCO DE DADOS (SUPABASE)
# ==============================================================================
@st.cache_resource
def init_db():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except: return None

supabase = init_db()

# REMOVIDO @st.cache_data para garantir leitura em tempo real
def get_data():
    if not supabase: return {}
    try:
        # Busca dados frescos do banco
        res = supabase.table("excecoes").select("*").execute()
        # Converte para dicionário {data: dados}
        return {datetime.strptime(i['data'], "%Y-%m-%d").date(): i for i in res.data}
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return {}

def save_data(d, t, desc):
    if supabase:
        supabase.table("excecoes").upsert({
            "data": d.strftime("%Y-%m-%d"), 
            "tipo": t, 
            "descricao": desc
        }).execute()
        # Pequena pausa para garantir que o banco processou antes de recarregar
        time.sleep(0.5) 
        return True
    return False

# ==============================================================================
# 3. DESIGN SYSTEM (CLEAN / WHITE)
# ==============================================================================
st.markdown("""
    <style>
    /* Fontes Nativas Modernas */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --primary: #2E7D32;       /* Verde Awake */
        --bg-app: #F3F4F6;        /* Cinza Claro Fundo */
        --bg-card: #FFFFFF;       /* Branco Card */
        --text-main: #1F2937;     /* Cinza Escuro */
        --text-light: #6B7280;    /* Cinza Médio */
        --border: #E5E7EB;        /* Borda Suave */
    }

    /* Reset Geral */
    .stApp { background-color: var(--bg-app); font-family: 'Inter', sans-serif; color: var(--text-main); }
    header, footer, #MainMenu { display: none !important; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid var(--border); }
    
    /* Header Navigation */
    .nav-header {
        display: flex; justify-content: space-between; align-items: center;
        background: white; padding: 20px 30px; border-radius: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; border: 1px solid var(--border);
    }
    .month-title { font-size: 24px; font-weight: 700; color: #111827; letter-spacing: -0.5px; }
    .year-title { color: var(--text-light); font-weight: 400; font-size: 24px; margin-left: 8px; }

    /* Grid Layout */
    .weekday { text-align: center; font-size: 12px; font-weight: 600; color: var(--text-light); text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.5px; }

    /* Card do Dia */
    .day-card {
        background-color: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px;
        min-height: 140px;
        display: flex; flex-direction: column;
        transition: all 0.2s;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    .day-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: var(--primary);
        z-index: 10;
    }

    /* Estados */
    .is-today { border: 2px solid var(--primary); background-color: #F0FDF4; }
    .is-past { background-color: #F9FAFB; opacity: 0.6; }
    .is-blur { opacity: 0.3; background-color: #F3F4F6; }

    /* Número do Dia */
    .day-num { font-size: 14px; font-weight: 600; color: var(--text-main); margin-bottom: 8px; display: flex; justify-content: space-between; }
    .is-today .day-num { color: var(--primary); }

    /* Chips (Eventos) */
    .chip { font-size: 11px; padding: 4px 8px; border-radius: 4px; margin-bottom: 4px; font-weight: 500; border-left: 3px solid #ccc; line-height: 1.3; }
    
    .c-sh { background: #ECFDF5; color: #065F46; border-color: #10B981; }
    .c-teca { background: #F5F3FF; color: #5B21B6; border-color: #8B5CF6; }
    .c-esp { background: #FFFBEB; color: #92400E; border-color: #F59E0B; }
    .c-fer { background: #FEF2F2; color: #991B1B; border-color: #EF4444; }
    .c-off { background: #F3F4F6; color: #6B7280; border-color: #9CA3AF; text-decoration: line-through; }
    .c-rec { background: #EFF6FF; color: #1E40AF; border-color: #3B82F6; }

    /* Badge Hoje */
    .badge-today { background: var(--primary); color: white; font-size: 9px; padding: 2px 6px; border-radius: 10px; }

    /* Chat Input Styling */
    .stChatInput textarea { background-color: white !important; color: black !important; border: 1px solid #E5E7EB !important; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. INTELLIGENCE (NLP)
# ==============================================================================
def parse_command(text, month_idx):
    text_clean = text.lower()
    
    # 1. Data
    d, m = None, month_idx
    # Tenta DD/MM
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', text_clean)
    # Tenta "Dia XX"
    match_day = re.search(r'\bdia (\d{1,2})\b', text_clean)
    
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_day: d = int(match_day.group(1))
    
    if not d: return {"ok": False, "msg": "Indique a data (Ex: Dia 20 ou 20/01)"}
    try: dt = date(2026, m, d)
    except: return {"ok": False, "msg": "Data inválida."}
    
    # 2. Tipo
    tipo = "especial"
    if "recesso" in text_clean: tipo = "recesso"
    elif any(x in text_clean for x in ["cancelar", "off", "remover", "tirar"]): tipo = "cancelado"
    
    # 3. Descrição
    desc = "CANCELADO" if tipo == "cancelado" else "RECESSO" if tipo == "recesso" else ""
    
    if tipo == "especial":
        # Remove data e palavras de ligação
        raw = text
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw, flags=re.IGNORECASE)
        
        # Extrai hora (ex: 19h, 19:00)
        hora = ""
        hm = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if hm: 
            hora = hm.group(0).replace(":", "h") + " "
            raw = raw.replace(hm.group(0), "")
            
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de", "o", "a", "no", "na"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        act = pattern.sub('', raw).strip().title()
        
        # Identifica Instrutor
        instrs = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
        found = [i for i in instrs if i.lower() in text_clean]
        
        # Limpa nome do instrutor da atividade para não duplicar
        for i in found: act = act.replace(i, "").replace(i.lower(), "").strip()
        
        final_inst = f" ({found[0]})" if found else ""
        desc = f"{hora}{act}{final_inst}".strip()
        
    return {"ok": True, "data": dt, "tipo": tipo, "desc": desc}

# ==============================================================================
# 5. EXECUÇÃO PRINCIPAL
# ==============================================================================

# Controle de Mês
if 'mes_idx' not in st.session_state: st.session_state.mes_idx = datetime.now().month

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🌿 Awake Admin")
    st.caption("Comandos Inteligentes")
    
    prompt = st.chat_input("Ex: Dia 20 Workshop 19h com Pat")
    
    if prompt:
        res = parse_command(prompt, st.session_state.mes_idx)
        st.session_state['pending'] = res
        
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['ok']:
            # Cartão de Confirmação na Sidebar
            st.success(f"Detectado: {p['data'].strftime('%d/%m')}")
            st.markdown(f"**{p['desc']}**")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar"):
                if save_data(p['data'], p['tipo'], p['desc']):
                    st.toast("Salvo com sucesso!", icon="🎉")
                    del st.session_state['pending']
                    st.rerun()
            if c2.button("❌ Cancelar"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# --- ÁREA PRINCIPAL ---

# Header com Navegação
col_prev, col_main, col_next = st.columns([1, 15, 1])

with col_prev:
    st.write("")
    if st.button("◀", key="p"): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()

with col_next:
    st.write("")
    if st.button("▶", key="n"): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with col_main:
    meses = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
    st.markdown(f"""
    <div class="nav-header">
        <div>
            <span class="month-title">{meses[st.session_state.mes_idx]}</span>
            <span class="year-title">2026</span>
        </div>
        <div style="font-size:12px; color:#aaa">Awake Health OS</div>
    </div>
    """, unsafe_allow_html=True)

# Lógica do Calendário
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

# Cabeçalhos Dias da Semana
cols = st.columns(7)
for i, d in enumerate(["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]):
    cols[i].markdown(f"<div class='weekday'>{d}</div>", unsafe_allow_html=True)

# Grid de Dias
chunks = [dias[i:i+7] for i in range(0, len(dias), 7)]
for semana in chunks:
    cols = st.columns(7)
    for i, dia in enumerate(semana):
        with cols[i]:
            # Lógica de Visual
            css = "day-card"
            badge = ""
            
            if dia == HOJE: 
                css += " is-today"
                badge = "<span class='badge-today'>HOJE</span>"
            elif dia < HOJE: 
                css += " is-past"
            
            if dia.month != st.session_state.mes_idx: 
                css += " is-blur"
            
            # Conteúdo
            html = ""
            
            # A. DB (Exceção)
            if dia in excecoes:
                exc = excecoes[dia]
                t = exc['tipo']
                desc = exc['descricao']
                
                if t == 'recesso': html += f'<div class="chip c-rec">💤 {desc}</div>'
                elif t == 'cancelado': html += f'<div class="chip c-off">Cancelado</div>'
                else: html += f'<div class="chip c-esp">★ {desc}</div>'
                
            # B. Feriado
            elif dia in feriados:
                html += f'<div class="chip c-fer">🎈 {feriados[dia]}</div>'
                
            # C. Padrão (Sound Healing / Teca)
            elif dia.month == st.session_state.mes_idx:
                wd = dia.weekday()
                # Teca
                if wd == 1 and dia.month not in [1, 7]: 
                    html += '<div class="chip c-teca">Talk Med.</div>'
                
                # Sound Healing
                sh = ""
                if wd==0: sh = "19h SH (Haran)"
                elif wd==1: sh = "19h SH (Karina)"
                elif wd==2: sh = "19h SH (Pat)"
                elif wd==3: sh = "19h SH (Pat)"
                elif wd==4: sh = "19h SH (Haran)"
                elif wd==5: sh = "10h SH (Karina)"
                
                if sh: html += f'<div class="chip c-sh">{sh}</div>'

            # Render
            st.markdown(f"""
            <div class="{css}">
                <div class="day-num"><span>{dia.day}</span>{badge}</div>
                <div>{html}</div>
            </div>
            """, unsafe_allow_html=True)
