import streamlit as st
from supabase import create_client, Client
import calendar
from datetime import date, datetime, timedelta
import pytz
import re
import time

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Awake OS", page_icon="🧿", layout="wide")

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# CSS e Estilo
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    :root { --primary: #2E7D32; --bg: #F5F7F9; }
    .stApp { font-family: 'DM Sans', sans-serif; background-color: var(--bg); }
    
    .day-card {
        background: white; border-radius: 12px; padding: 10px; min-height: 140px;
        border: 1px solid #E0E0E0; position: relative; display: flex; flex-direction: column;
    }
    .day-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); transition: all 0.2s; }
    .day-past { opacity: 0.6; background: #FAFAFA; border-style: dashed; }
    .day-today { border: 2px solid var(--primary); background: #F1F8E9; }
    
    .chip { font-size: 0.75rem; padding: 4px 8px; border-radius: 6px; margin-bottom: 4px; border-left: 3px solid #ccc; background: #fff; }
    .chip-sh { border-color: #2E7D32; background: #E8F5E9; color: #1B5E20; }
    .chip-teca { border-color: #8E24AA; background: #F3E5F5; color: #4A148C; }
    .chip-especial { border-color: #F9A825; background: #FFF8E1; color: #F57F17; }
    .chip-feriado { border-color: #D32F2F; background: #FFEBEE; color: #B71C1C; }
    .chip-recesso { border-color: #90A4AE; background: #ECEFF1; color: #546E7A; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

# --- LÓGICA DE DADOS ---
FERIADOS_2026 = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 7, 9): "Rev. 32", date(2026, 9, 7): "Independência",
    date(2026, 10, 12): "N. Sra. Aparecida", date(2026, 11, 2): "Finados",
    date(2026, 11, 15): "Proclamação", date(2026, 11, 20): "Consciência",
    date(2026, 12, 25): "Natal"
}

def carregar_dados():
    if not supabase: return {}
    try:
        response = supabase.table("excecoes").select("*").execute()
        mapa = {}
        for item in response.data:
            d = datetime.strptime(item['data'], "%Y-%m-%d").date()
            mapa[d] = item
        return mapa
    except: return {}

def salvar(data, tipo, desc):
    if not supabase: return False
    try:
        supabase.table("excecoes").upsert({
            "data": data.strftime("%Y-%m-%d"), "tipo": tipo, "descricao": desc
        }).execute()
        st.cache_data.clear()
        return True
    except: return False

# --- UI INTERFACE ---
with st.sidebar:
    st.title("Awake Gestão")
    st.caption(f"Hoje: {HOJE.strftime('%d/%m')}")
    
    prompt = st.chat_input("Ex: Dia 20/03 Workshop Tantra")
    
    if prompt:
        match = re.search(r'(\d{1,2})/(\d{1,2})', prompt)
        if match:
            try:
                d, m = int(match.group(1)), int(match.group(2))
                dt = date(2026, m, d)
                tipo = "recesso" if "recesso" in prompt.lower() else "cancelado" if "cancelar" in prompt.lower() else "especial"
                desc = re.sub(r'\d{1,2}/\d{1,2}', '', prompt).replace("dia","").replace("recesso","").strip().title()
                if tipo == "recesso": desc = "RECESSO"
                st.session_state['pending'] = {"dt": dt, "tipo": tipo, "desc": desc}
            except: st.error("Data inválida")
    
    if 'pending' in st.session_state:
        p = st.session_state['pending']
        st.info(f"Alterar {p['dt'].strftime('%d/%m')} para: {p['desc']}?")
        c1, c2 = st.columns(2)
        if c1.button("✅ Sim"):
            salvar(p['dt'], p['tipo'], p['desc'])
            del st.session_state['pending']
            st.rerun()
        if c2.button("❌ Não"):
            del st.session_state['pending']
            st.rerun()

# --- CALENDÁRIO ---
excecoes = carregar_dados()
mes = st.selectbox("Mês", range(1, 13), format_func=lambda x: calendar.month_name[x].upper())
cal = calendar.Calendar(firstweekday=6)
dias = list(cal.itermonthdates(2026, mes))

cols = st.columns(7)
for d in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]: cols[dias.index(next(x for x in dias if x.weekday() == ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"].index(d)))%7].markdown(f"**{d}**")

for chunk in [dias[i:i+7] for i in range(0, len(dias), 7)]:
    cols = st.columns(7)
    for i, dia in enumerate(chunk):
        with cols[i]:
            if dia.month != mes: 
                st.markdown("<div style='height:140px; opacity:0.1; background:#ddd; border-radius:12px'></div>", unsafe_allow_html=True)
                continue
            
            html = ""
            css = "day-card"
            if dia < HOJE: css += " day-past"
            if dia == HOJE: css += " day-today"

            # 1. Exceção
            if dia in excecoes:
                exc = excecoes[dia]
                t = exc['tipo']
                html += f"<div class='chip {'chip-recesso' if t=='recesso' else 'chip-especial'}'>{exc['descricao']}</div>"
            # 2. Feriado
            elif dia in FERIADOS_2026:
                html += f"<div class='chip chip-feriado'>🎈 {FERIADOS_2026[dia]}</div>"
            # 3. Padrão
            else:
                wd = dia.weekday()
                if wd==0: html += "<div class='chip chip-sh'>19h SH (Haran)</div>"
                if wd==1: 
                    html += "<div class='chip chip-sh'>19h SH (Karina)</div>"
                    if dia.month not in [1,7]: html += "<div class='chip chip-teca'>08h15 Talk Med.</div>"
                if wd==2: html += "<div class='chip chip-sh'>19h SH (Pat)</div>"
                if wd==3: html += "<div class='chip chip-sh'>19h SH (Pat)</div>"
                if wd==4: html += "<div class='chip chip-sh'>19h SH (Haran)</div>"
                if wd==5: html += "<div class='chip chip-sh'>10h SH (Karina)</div>"

            st.markdown(f"<div class='{css}'><div style='font-weight:bold;color:#aaa'>{dia.day}</div>{html}</div>", unsafe_allow_html=True)
