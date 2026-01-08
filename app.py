import streamlit as st
from supabase import create_client, Client
import pandas as pd
import calendar
from datetime import date, datetime, timedelta
import pytz
import re
import time

# --- 1. CONFIGURAÇÃO ---
st.set_page_config(page_title="Awake OS | Supabase", page_icon="🧿", layout="wide")

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# Design System (Mantendo o visual "Glass" e "Mobile First")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');
    :root { --primary: #2E7D32; --gold: #F9A825; --bg: #F5F7F9; }
    .stApp { font-family: 'DM Sans', sans-serif; background-color: var(--bg); }
    
    .day-card {
        background: white; border-radius: 12px; padding: 10px; min-height: 140px;
        border: 1px solid #E0E0E0; box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        transition: all 0.2s; position: relative; display: flex; flex-direction: column;
    }
    .day-card:hover { border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 8px 16px rgba(46,125,50,0.1); }
    
    .day-past { opacity: 0.5; background: #FAFAFA; border-style: dashed; }
    .day-today { border: 2px solid var(--primary); background: #F1F8E9; }
    
    .chip { font-size: 0.75rem; padding: 4px 8px; border-radius: 6px; margin-bottom: 4px; border-left: 3px solid #ccc; background: #fff; line-height:1.2; }
    .chip-sh { border-color: var(--primary); background: #E8F5E9; color: #1B5E20; }
    .chip-teca { border-color: #8E24AA; background: #F3E5F5; color: #4A148C; }
    .chip-especial { border-color: var(--gold); background: #FFF8E1; color: #F57F17; }
    .chip-feriado { border-color: #D32F2F; background: #FFEBEE; color: #B71C1C; }
    .chip-recesso { border-color: #90A4AE; background: #ECEFF1; color: #546E7A; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO COM SUPABASE ---

@st.cache_resource
def init_connection():
    url = st.secrets["supabase_url"]
    key = st.secrets["supabase_key"]
    return create_client(url, key)

supabase = init_connection()

# Funções de Banco de Dados
def carregar_excecoes():
    try:
        # Busca todos os dados da tabela 'excecoes'
        response = supabase.table("excecoes").select("*").execute()
        dados = response.data
        if not dados: return {}
        
        # Converte lista de dicts para um formato fácil de buscar: {data_obj: dados}
        mapa = {}
        for item in dados:
            d = datetime.strptime(item['data'], "%Y-%m-%d").date()
            mapa[d] = item
        return mapa
    except Exception as e:
        st.error(f"Erro DB: {e}")
        return {}

def salvar_excecao(data_obj, tipo, desc):
    try:
        dados = {
            "data": data_obj.strftime("%Y-%m-%d"),
            "tipo": tipo,
            "descricao": desc
        }
        # Upsert: Se existe atualiza, se não existe cria
        supabase.table("excecoes").upsert(dados).execute()
        st.cache_data.clear() # Limpa cache se houver
        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")
        return False

# Carrega dados ao iniciar
excecoes_map = carregar_excecoes()

# --- 3. LÓGICA DE NEGÓCIO ---

FERIADOS_2026 = {
    date(2026, 1, 1): "Confraternização Universal",
    date(2026, 1, 25): "Aniversário de SP",
    date(2026, 2, 17): "Carnaval",
    date(2026, 4, 3): "Sexta-feira Santa",
    date(2026, 4, 21): "Tiradentes",
    date(2026, 5, 1): "Dia do Trabalhador",
    date(2026, 7, 9): "Rev. Constitucionalista",
    date(2026, 9, 7): "Independência",
    date(2026, 10, 12): "N. Sra. Aparecida",
    date(2026, 11, 2): "Finados",
    date(2026, 11, 15): "Proc. República",
    date(2026, 11, 20): "Consciência Negra",
    date(2026, 12, 25): "Natal"
}

def nlp_parser(texto):
    texto_low = texto.lower()
    match = re.search(r'(\d{1,2})/(\d{1,2})', texto)
    if match:
        try:
            d, m = int(match.group(1)), int(match.group(2))
            data_alvo = date(2026, m, d)
            aviso = "⚠️ Você está alterando o **PASSADO**!" if data_alvo < HOJE else ""
            
            tipo = "especial"
            if "recesso" in texto_low: tipo = "recesso"
            elif any(x in texto_low for x in ["cancelar", "off", "remover"]): tipo = "cancelado"
            
            # Limpeza inteligente da string
            desc = re.sub(r'\d{1,2}/\d{1,2}', '', texto)
            stop_words = ["dia", "em", "no", "na", "para", "mudar", "alterar", "troque", "pela", "experiência", "ministrada", "por", "as", "às", "o", "a"]
            pattern = re.compile(r'\b(' + '|'.join(stop_words) + r')\b', re.IGNORECASE)
            desc = pattern.sub('', desc).strip().title()
            
            if tipo == "cancelado": desc = "CANCELADO"
            if tipo == "recesso": desc = "RECESSO"

            return {"status": "ok", "data": data_alvo, "tipo": tipo, "desc": desc, "aviso": aviso}
        except:
            return {"status": "error", "msg": "Data inválida."}
    return {"status": "error", "msg": "Use o formato DD/MM (ex: 20/01)."}

# --- 4. UI ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/4494/4494475.png", width=50)
    st.markdown("### Awake Gestão")
    st.caption("Database: Supabase (Permanente)")
    
    prompt = st.chat_input("Digite a alteração aqui...")
    
    if prompt:
        res = nlp_parser(prompt)
        st.session_state['pending'] = res

    if 'pending' in st.session_state:
        p = st.session_state['pending']
        if p['status'] == 'ok':
            if p['aviso']: st.warning(p['aviso'])
            st.info(f"Definir **{p['data'].strftime('%d/%m')}** como: **{p['desc']}**")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Confirmar"):
                if salvar_excecao(p['data'], p['tipo'], p['desc']):
                    st.success("Salvo!")
                    del st.session_state['pending']
                    time.sleep(0.5)
                    st.rerun()
            if c2.button("❌ Cancelar"):
                del st.session_state['pending']
                st.rerun()
        else:
            st.error(p['msg'])
            del st.session_state['pending']

# --- 5. RENDERIZADOR ---

mes_sel = st.selectbox("Mês", range(1, 13), format_func=lambda x: calendar.month_name[x].upper())
st.divider()

cal = calendar.Calendar(firstweekday=6)
dias = list(cal.itermonthdates(2026, mes_sel))
chunks = [dias[i:i+7] for i in range(0, len(dias), 7)]

# Headers
cols = st.columns(7)
for d in ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]:
    cols[dias.index(next(x for x in dias if x.weekday() == ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"].index(d) )) % 7].markdown(f"**{d}**")

# Grid
for semana in chunks:
    cols = st.columns(7)
    for i, dia in enumerate(semana):
        with cols[i]:
            if dia.month != mes_sel:
                st.markdown("<div style='height:140px; opacity:0.1; background:#ddd; border-radius:10px'></div>", unsafe_allow_html=True)
                continue
            
            css = "day-card"
            html = ""
            if dia < HOJE: css += " day-past"
            if dia == HOJE: css += " day-today"; html += "<div style='position:absolute; top:-8px; right:10px; background:#2E7D32; color:white; font-size:0.6em; padding:2px 5px; border-radius:4px'>HOJE</div>"

            # 1. Busca no Banco de Dados (Supabase)
            if dia in excecoes_map:
                exc = excecoes_map[dia]
                tipo = exc['tipo']
                desc = exc['descricao']
                if tipo == 'recesso': html += f"<div class='chip chip-recesso'>💤 {desc}</div>"
                elif tipo == 'cancelado': html += f"<div class='chip' style='text-decoration:line-through; color:#aaa'>Cancelado</div>"
                else: html += f"<div class='chip chip-especial'>★ {desc}</div>"
            
            # 2. Feriados
            elif dia in FERIADOS_2026:
                html += f"<div class='chip chip-feriado'>🎈 {FERIADOS_2026[dia]}</div>"
            
            # 3. Padrão (Regras Fixas)
            else:
                ds = dia.weekday()
                # Regras hardcoded para performance, mas podem vir do banco também
                if ds == 0: html += "<div class='chip chip-sh'>19h SH (Haran)</div>"
                if ds == 1: 
                    html += "<div class='chip chip-sh'>19h SH (Karina)</div>"
                    if dia.month not in [1, 7]: html += "<div class='chip chip-teca'>08h15 Talk Med.</div>"
                if ds == 2: html += "<div class='chip chip-sh'>19h SH (Pat)</div>"
                if ds == 3: html += "<div class='chip chip-sh'>19h SH (Pat)</div>"
                if ds == 4: html += "<div class='chip chip-sh'>19h SH (Haran)</div>"
                if ds == 5: html += "<div class='chip chip-sh'>10h SH (Karina)</div>"

            st.markdown(f"<div class='{css}'><div style='font-weight:bold; color:#B0BEC5; margin-bottom:5px'>{dia.day}</div>{html}</div>", unsafe_allow_html=True)
