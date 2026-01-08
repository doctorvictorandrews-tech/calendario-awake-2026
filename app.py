import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime
import pytz
import re
import difflib # Biblioteca para Fuzzy Matching (Correção de typos)
import unicodedata

# ==============================================================================
# 1. CONFIGURAÇÃO (KERNEL)
# ==============================================================================
st.set_page_config(
    page_title="Awake OS",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# ==============================================================================
# 2. CÉREBRO DE INTELIGÊNCIA (NLP AVANÇADO)
# ==============================================================================

class AwakeBrain:
    def __init__(self):
        self.instructors = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana", "Victor"]
        self.months_map = {
            "jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "março": 3,
            "abr": 4, "abril": 4, "mai": 5, "maio": 5, "jun": 6, "junho": 6,
            "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "setembro": 9,
            "out": 10, "outubro": 10, "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12
        }
        self.stop_words = [
            "o", "a", "os", "as", "um", "uma", "de", "do", "da", "em", "no", "na", "para", "por", "com",
            "será", "vai", "ter", "haver", "mudar", "alterar", "trocar", "colocar", "inserir", "agendar",
            "substituir", "pelo", "pela", "ministrada", "aula", "experiência", "sessão", "prática",
            "dia", "hoje", "amanhã", "sh", "sound", "healing"
        ]

    def normalize_text(self, text):
        # Remove acentos e deixa minúsculo
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('utf-8')
        return text.lower()

    def extract_date(self, text, current_month):
        text_norm = self.normalize_text(text)
        today = date.today()
        year = today.year + 1 if today.month == 12 and current_month == 1 else today.year # Lógica básica de ano
        if current_month < today.month: year = 2026 # Força 2026 conforme solicitado

        # 1. Tenta formato DD/MM
        match_slash = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})', text_norm)
        if match_slash:
            return date(year, int(match_slash.group(2)), int(match_slash.group(1)))

        # 2. Tenta "Dia 20" ou apenas "20" se o contexto for claro
        # Procura por meses por extenso (ex: "20 de janeiro")
        for month_name, month_num in self.months_map.items():
            pattern = f"(\\d{{1,2}})\\s*(de)?\\s*{month_name}"
            match_ext = re.search(pattern, text_norm)
            if match_ext:
                return date(year, month_num, int(match_ext.group(1)))

        # 3. Tenta apenas "Dia 20" (Assume mês atual da visualização)
        match_day = re.search(r'\bdia\s+(\d{1,2})\b', text_norm)
        if match_day:
            return date(year, current_month, int(match_day.group(1)))
        
        return None

    def extract_instructor(self, text):
        # Usa Fuzzy Matching para achar instrutor mesmo com erro de digitação
        # Ex: "Carina" -> "Karina"
        words = text.split()
        found = None
        
        # Verifica palavra por palavra
        for word in words:
            # Limpa pontuação
            clean_word = re.sub(r'[^\w\s]', '', word)
            matches = difflib.get_close_matches(clean_word, self.instructors, n=1, cutoff=0.75)
            if matches:
                found = matches[0]
                break
        return found

    def extract_time(self, text):
        # Pega 19h, 19:00, 19:30, 08h15
        match = re.search(r'(\d{1,2})[h:](\d{0,2})', text.lower())
        if match:
            h = match.group(1)
            m = match.group(2)
            if m and m != "00": return f"{h}h{m}"
            return f"{h}h"
        return ""

    def parse(self, text, view_month_idx):
        if not text: return {"ok": False}
        
        # 1. Detectar Data
        dt = self.extract_date(text, view_month_idx)
        if not dt: return {"ok": False, "msg": "Não entendi a data. Tente 'Dia 20' ou '20/01'."}

        # 2. Detectar Intenção (Tipo)
        text_lower = text.lower()
        tipo = "especial"
        if any(x in text_lower for x in ["recesso", "feriado", "folga"]): tipo = "recesso"
        elif any(x in text_lower for x in ["cancelar", "remover", "excluir", "off", "sem aula", "tirar"]): tipo = "cancelado"

        desc = ""
        if tipo == "recesso": desc = "RECESSO"
        elif tipo == "cancelado": desc = "CANCELADO"
        else:
            # 3. Extração Inteligente de Descrição
            # Remove a data do texto original para não sujar
            clean_text = re.sub(r'\d{1,2}/\d{1,2}', '', text)
            clean_text = re.sub(r'\bdia\s+\d{1,2}\b', '', clean_text, flags=re.IGNORECASE)
            
            # Extrai Hora e Instrutor
            hora = self.extract_time(clean_text)
            instrutor = self.extract_instructor(clean_text)
            
            # Limpeza de Stopwords (Remove "substitua", "pelo", etc)
            words = clean_text.split()
            filtered_words = []
            
            # Regex para limpar hora do texto (para não duplicar)
            time_pattern = re.compile(r'(\d{1,2})[h:](\d{0,2})', re.IGNORECASE)
            
            for w in words:
                w_norm = self.normalize_text(w)
                # Pula se for stopword, se for o nome do instrutor ou se for hora
                if w_norm in self.stop_words: continue
                if instrutor and w_norm in self.normalize_text(instrutor): continue
                if time_pattern.match(w): continue
                if w_norm.isdigit(): continue # Remove números soltos
                
                filtered_words.append(w)
            
            # Reconstrói a atividade
            activity = " ".join(filtered_words).strip().title()
            # Correção para "De" (ex: Ritual De Abertura)
            activity = re.sub(r'\bDe\b', 'de', activity)
            
            # Montagem Final
            final_instr_str = f" ({instrutor})" if instrutor else ""
            desc = f"{hora} {activity}{final_instr_str}".strip()
            
            # Remove espaços duplos
            desc = re.sub(r'\s+', ' ', desc)

        return {"ok": True, "data": dt, "tipo": tipo, "desc": desc}

brain = AwakeBrain()

# ==============================================================================
# 3. SUPABASE & DATABASE
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
# 4. DESIGN SYSTEM (ECOFIN DARK STYLE)
# ==============================================================================
# Controle de Mês
if 'mes_idx' not in st.session_state: st.session_state.mes_idx = datetime.now().month

THEMES = {
    1: "#10B981", 2: "#8B5CF6", 3: "#3B82F6", 4: "#EC4899",
    5: "#F59E0B", 6: "#EF4444", 7: "#06B6D4", 8: "#6366F1",
    9: "#84CC16", 10: "#F97316", 11: "#14B8A6", 12: "#E11D48"
}
CURRENT_ACCENT = THEMES[st.session_state.mes_idx]

st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;800&family=Inter:wght@300;400;600&family=JetBrains+Mono:wght@400&display=swap');

    :root {{
        --bg-body: #050505;
        --glass: rgba(255, 255, 255, 0.03);
        --border: rgba(255, 255, 255, 0.08);
        --accent: {CURRENT_ACCENT};
        --primary: #10B981;
    }}

    .stApp {{ background-color: var(--bg-body); font-family: 'Inter', sans-serif; color: white; }}
    header, footer, #MainMenu {{ display: none !important; }}
    [data-testid="stSidebar"] {{ background-color: #0A0A0A; border-right: 1px solid var(--border); }}
    
    /* Inputs */
    .stChatInput textarea, .stTextInput input {{
        background-color: #111 !important; border: 1px solid #333 !important; color: white !important; border-radius: 12px !important;
    }}

    /* Calendar Grid */
    .day-container {{
        background: var(--glass);
        border: 1px solid var(--border);
        border-radius: 16px;
        min-height: 160px;
        padding: 12px;
        display: flex; flex-direction: column;
        transition: 0.3s;
        backdrop-filter: blur(10px);
    }}
    .day-container:hover {{
        transform: translateY(-5px); border-color: var(--accent); background: rgba(255,255,255,0.06);
    }}
    .is-today {{ border: 1px solid var(--primary); background: rgba(16, 185, 129, 0.05); }}
    .is-blur {{ opacity: 0.2; filter: grayscale(1); }}
    
    .day-num {{ font-family: 'Manrope', sans-serif; font-size: 20px; font-weight: 700; color: #555; margin-bottom: 12px; display:flex; justify-content:space-between; }}
    .is-today .day-num {{ color: white; }}
    
    /* Chips */
    .tag {{ font-size: 11px; padding: 6px 10px; border-radius: 8px; margin-bottom: 6px; background: rgba(255,255,255,0.05); border-left: 2px solid #333; color: #ccc; }}
    .tag-sh {{ border-color: #10B981; color: #D1FAE5; background: rgba(16, 185, 129, 0.1); }}
    .tag-teca {{ border-color: #8B5CF6; color: #EDE9FE; background: rgba(139, 92, 246, 0.1); }}
    .tag-esp {{ border-color: var(--accent); color: white; background: rgba(255,255,255,0.1); border-left: 3px solid var(--accent); }}
    .tag-fer {{ border-color: #EF4444; color: #FEE2E2; background: rgba(239, 68, 68, 0.1); }}
    .tag-off {{ border-color: #6B7280; color: #9CA3AF; border-style: dashed; }}

    /* Header Mês */
    .month-header {{
        font-family: 'Manrope', sans-serif; font-size: 42px; font-weight: 800;
        background: linear-gradient(180deg, #fff 0%, {CURRENT_ACCENT} 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    
    /* Glow */
    .ambient-glow {{
        position: fixed; top: -20%; right: -10%; width: 600px; height: 600px;
        background: var(--accent); filter: blur(250px); opacity: 0.15; z-index: -1; pointer-events: none;
    }}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="ambient-glow"></div>', unsafe_allow_html=True)

# ==============================================================================
# 5. EXECUÇÃO
# ==============================================================================

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/12128/12128373.png", width=60)
    st.markdown("### Awake Brain AI")
    st.caption("Digite comandos naturais...")
    
    prompt = st.chat_input("Ex: Trocar dia 20 para Ritual 19h")
    
    if prompt:
        res = brain.parse(prompt, st.session_state.mes_idx)
        st.session_state['pending'] = res
        
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['ok']:
            st.markdown(f"""
            <div style="background:#111; padding:15px; border-radius:10px; border:1px solid {CURRENT_ACCENT}; margin-bottom:15px;">
                <div style="color:#aaa; font-size:10px; text-transform:uppercase;">Detectado</div>
                <div style="color:white; font-weight:bold; font-size:16px;">{p['data'].strftime('%d/%m')}</div>
                <div style="color:{CURRENT_ACCENT}; font-size:14px; margin-top:5px;">{p['desc']}</div>
            </div>
            """, unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            if c1.button("✅ CONFIRMAR"):
                save_data(p['data'], p['tipo'], p['desc'])
                del st.session_state['pending']
                st.rerun()
            if c2.button("❌ DESCARTAR"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# --- MAIN ---
c1, c2, c3 = st.columns([1, 10, 1])
with c1:
    st.write("")
    if st.button("◀", key="p"): 
        st.session_state.mes_idx = 12 if st.session_state.mes_idx == 1 else st.session_state.mes_idx - 1
        st.rerun()
with c3:
    st.write("")
    if st.button("▶", key="n"): 
        st.session_state.mes_idx = 1 if st.session_state.mes_idx == 12 else st.session_state.mes_idx + 1
        st.rerun()

with c2:
    meses_txt = {1:"JANEIRO", 2:"FEVEREIRO", 3:"MARÇO", 4:"ABRIL", 5:"MAIO", 6:"JUNHO", 7:"JULHO", 8:"AGOSTO", 9:"SETEMBRO", 10:"OUTUBRO", 11:"NOVEMBRO", 12:"DEZEMBRO"}
    st.markdown(f'<div class="month-header">{meses_txt[st.session_state.mes_idx]} <span style="font-size:16px; color:#555">2026</span></div>', unsafe_allow_html=True)

# CALENDÁRIO
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

# Grid Header
cols = st.columns(7)
for i, d in enumerate(["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]):
    cols[i].markdown(f"<div style='text-align:center; color:#666; font-size:12px; font-weight:bold; margin-bottom:10px;'>{d}</div>", unsafe_allow_html=True)

# Grid Body
chunks = [dias[i:i+7] for i in range(0, len(dias), 7)]
for semana in chunks:
    cols = st.columns(7)
    for i, dia in enumerate(semana):
        with cols[i]:
            css = "day-container"
            if dia == HOJE: css += " is-today"
            if dia.month != st.session_state.mes_idx: css += " is-blur"
            
            html = ""
            # A. DB
            if dia in excecoes:
                exc = excecoes[dia]
                t = exc['tipo']
                if t == 'recesso': html += f'<div class="tag tag-off">💤 {exc["descricao"]}</div>'
                elif t == 'cancelado': html += f'<div class="tag tag-off" style="text-decoration:line-through">Cancelado</div>'
                else: html += f'<div class="tag tag-esp">★ {exc["descricao"]}</div>'
            # B. Feriado
            elif dia in feriados:
                html += f'<div class="tag tag-fer">🎈 {feriados[dia]}</div>'
            # C. Padrão
            elif dia.month == st.session_state.mes_idx:
                wd = dia.weekday()
                if wd==1 and dia.month not in [1,7]: html += '<div class="tag tag-teca">Talk Med.</div>'
                sh = ""
                if wd==0: sh = "19h SH (Haran)"
                elif wd==1: sh = "19h SH (Karina)"
                elif wd==2: sh = "19h SH (Pat)"
                elif wd==3: sh = "19h SH (Pat)"
                elif wd==4: sh = "19h SH (Haran)"
                elif wd==5: sh = "10h SH (Karina)"
                if sh: html += f'<div class="tag tag-sh">{sh}</div>'

            badge = f'<span style="font-size:9px; color:{CURRENT_ACCENT}; font-weight:800;">HOJE</span>' if dia == HOJE else ''
            st.markdown(f"""
            <div class="{css}">
                <div class="day-num"><span>{dia.day}</span>{badge}</div>
                {html}
            </div>
            """, unsafe_allow_html=True)
