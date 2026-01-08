import streamlit as st
from supabase import create_client
import calendar
from datetime import date, datetime, timedelta
import pytz
import re
import time

# --- 1. CONFIGURAÇÃO E DESIGN SYSTEM PRO ---
st.set_page_config(page_title="Awake Calendar", page_icon="🌿", layout="wide", initial_sidebar_state="expanded")

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')
HOJE = datetime.now(SP_TZ).date()

# UI/UX CSS AVANÇADO
st.markdown("""
    <style>
    /* Import Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Reset & Variáveis */
    :root {
        --primary: #2E7D32; 
        --primary-light: #E8F5E9;
        --accent: #F9A825;
        --text: #1F2937;
        --bg-app: #F3F4F6;
        --card-bg: #FFFFFF;
        --border: #E5E7EB;
    }

    /* Global */
    .stApp { background-color: var(--bg-app); font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; color: var(--text); }
    
    /* Esconder Elementos Padrão do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* HEADER CUSTOMIZADO */
    .header-container {
        background: white;
        padding: 20px 30px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 30px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid var(--border);
    }
    
    /* GRID DO CALENDÁRIO (CSS GRID PURO) */
    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 12px;
    }
    
    .weekday-header {
        text-align: center;
        font-weight: 600;
        color: #9CA3AF;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding-bottom: 10px;
    }

    /* CARD DO DIA (App-like) */
    .day-card {
        background: var(--card-bg);
        border-radius: 12px;
        min-height: 150px;
        padding: 12px;
        border: 1px solid var(--border);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        flex-direction: column;
        position: relative;
    }
    
    .day-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        border-color: var(--primary);
    }
    
    .day-number {
        font-weight: 700;
        color: #374151;
        font-size: 1.1rem;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
    }
    
    /* ESTADOS DO DIA */
    .past-day { background-color: #F9FAFB; opacity: 0.7; }
    .today-card { border: 2px solid var(--primary); background-color: #F0FDF4; }
    
    /* CHIPS (EVENTOS) */
    .event-chip {
        font-size: 0.75rem;
        padding: 6px 10px;
        border-radius: 6px;
        margin-bottom: 6px;
        font-weight: 500;
        line-height: 1.3;
        border-left: 3px solid transparent;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }
    
    /* Cores dos Eventos */
    .evt-sh { background: #ECFDF5; color: #065F46; border-left-color: #10B981; }
    .evt-teca { background: #FAF5FF; color: #6B21A8; border-left-color: #A855F7; }
    .evt-special { background: #FFFBEB; color: #92400E; border-left-color: #F59E0B; }
    .evt-feriado { background: #FEF2F2; color: #991B1B; border-left-color: #EF4444; }
    .evt-recesso { background: #F3F4F6; color: #4B5563; border-left-color: #9CA3AF; }

    /* Sidebar Custom */
    [data-testid="stSidebar"] {
        background-color: white;
        border-right: 1px solid var(--border);
    }
    .stChatInput textarea { border-radius: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXÃO COM SUPABASE ---
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

# --- 3. INTELIGÊNCIA ARTIFICIAL (PARSER) ---
# Lista de instrutores conhecidos para ajudar a IA a formatar
INSTRUTORES_CONHECIDOS = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]

def processar_inteligencia_artificial(texto, mes_atual_visivel):
    """
    Transforma texto bagunçado em dados estruturados e limpos.
    Ex: 'Substitua SH dia 20/01 pelo Ritual 19h com Karina' -> '19h Ritual (Karina)'
    """
    texto_orig = texto
    texto = texto.lower()
    
    # 1. Detectar Data (DD/MM ou apenas DD)
    match_data_completa = re.search(r'(\d{1,2})/(\d{1,2})', texto)
    match_dia_apenas = re.search(r'\bdia (\d{1,2})\b', texto)
    
    data_final = None
    
    if match_data_completa:
        d, m = int(match_data_completa.group(1)), int(match_data_completa.group(2))
        data_final = date(2026, m, d)
    elif match_dia_apenas:
        d = int(match_dia_apenas.group(1))
        data_final = date(2026, mes_atual_visivel, d)
    
    if not data_final:
        return {"status": "erro", "msg": "Não entendi a data. Diga 'dia 20' ou '20/01'."}

    # 2. Tipificação
    tipo = "especial"
    if "recesso" in texto: tipo = "recesso"
    elif any(x in texto for x in ["cancelar", "remover", "off", "tirar"]): tipo = "cancelado"
    
    descricao_limpa = ""
    
    if tipo == "recesso":
        descricao_limpa = "RECESSO"
    elif tipo == "cancelado":
        descricao_limpa = "CANCELADO"
    else:
        # 3. Extração Inteligente de Conteúdo
        # Extrair Horário (ex: 19h, 19:00, 19h30)
        hora = ""
        match_hora = re.search(r'(\d{1,2})[h:](\d{0,2})', texto)
        if match_hora:
            hora = match_hora.group(0).replace(":", "h")
            if "h" not in hora: hora += "h"

        # Extrair Instrutor (Procura nomes conhecidos na string original preservando Maiúsculas)
        instrutor_encontrado = ""
        for nome in INSTRUTORES_CONHECIDOS:
            if nome.lower() in texto:
                instrutor_encontrado = nome
                break # Pega o primeiro que achar

        # 4. Limpeza da String (Remove tudo que já usamos e palavras de ligação)
        # Remove data, hora e o nome do instrutor da string para sobrar a atividade
        temp_text = texto_orig
        temp_text = re.sub(r'\d{1,2}/\d{1,2}', '', temp_text) # remove data
        temp_text = re.sub(r'\bdia \d{1,2}\b', '', temp_text, flags=re.IGNORECASE) # remove "dia 20"
        if match_hora: temp_text = temp_text.replace(match_hora.group(0), "") # remove hora
        if instrutor_encontrado: temp_text = re.sub(instrutor_encontrado, "", temp_text, flags=re.IGNORECASE) # remove instrutor

        # Remove palavras de comando e stop words
        stop_words = [
            "substitua", "troque", "altere", "coloque", "insira", "sh", "sound", "healing", "do", "da", "de", 
            "pelo", "pela", "por", "que", "será", "vai", "ser", "com", "as", "às", "ministrada", "aula", "experiência"
        ]
        pattern = re.compile(r'\b(' + '|'.join(stop_words) + r')\b', re.IGNORECASE)
        atividade = pattern.sub(' ', temp_text)
        
        # Limpa espaços extras e capitaliza
        atividade = " ".join(atividade.split()).title()
        
        # 5. Montagem Final (Formato Padrão)
        # Ex: "19h Ritual De Abertura (Karina)"
        descricao_limpa = f"{hora} {atividade}"
        if instrutor_encontrado:
            descricao_limpa += f" ({instrutor_encontrado})"
        
        # Limpeza final de formatação
        descricao_limpa = descricao_limpa.strip()

    return {
        "status": "sucesso",
        "data": data_final,
        "tipo": tipo,
        "desc": descricao_limpa
    }

# --- 4. FUNÇÕES DE DADOS ---

FERIADOS_2026 = {
    date(2026, 1, 1): "Confraternização", date(2026, 1, 25): "Aniv. SP",
    date(2026, 2, 17): "Carnaval", date(2026, 4, 3): "Sexta Santa",
    date(2026, 4, 21): "Tiradentes", date(2026, 5, 1): "Trabalhador",
    date(2026, 6, 4): "Corpus Christi", date(2026, 7, 9): "Rev. 32", 
    date(2026, 9, 7): "Independência", date(2026, 10, 12): "N. Sra. Aparecida", 
    date(2026, 11, 2): "Finados", date(2026, 11, 15): "Proclamação", 
    date(2026, 11, 20): "Consciência", date(2026, 12, 25): "Natal"
}

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
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

# --- 5. INTERFACE DO USUÁRIO ---

# Sidebar (Controle)
with st.sidebar:
    st.markdown("### 🌿 Awake Admin")
    
    # Seletor de Mês (Agora em Português)
    mes_atual = datetime.now().month
    mes_selecionado_idx = st.selectbox(
        "Visualizar Mês", 
        options=list(MESES_PT.keys()), 
        format_func=lambda x: MESES_PT[x],
        index=mes_atual-1
    )
    
    st.divider()
    
    st.markdown("#### 🤖 Assistente")
    st.info("Diga o que mudar. Ex: 'Dia 20 Sound Healing vira Ritual 19h com Karina'")
    
    prompt = st.chat_input("Digite a alteração...")
    
    if prompt:
        resultado = processar_inteligencia_artificial(prompt, mes_selecionado_idx)
        st.session_state['pending'] = resultado
    
    # Card de Confirmação Flutuante
    if 'pending' in st.session_state:
        res = st.session_state['pending']
        if res['status'] == 'sucesso':
            with st.container():
                st.markdown(f"""
                <div style="background:#FFF8E1; padding:15px; border-radius:10px; border:1px solid #F57F17; margin-bottom:15px">
                    <div style="font-size:0.8rem; color:#777">ALTERAÇÃO DETECTADA</div>
                    <div style="font-weight:bold; color:#333">{res['data'].strftime('%d/%m')}</div>
                    <div style="font-size:1.1rem; color:#2E7D32; font-weight:bold; margin-top:5px">{res['desc']}</div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2 = st.columns(2)
                if c1.button("✅ Aplicar", use_container_width=True):
                    salvar(res['data'], res['tipo'], res['desc'])
                    del st.session_state['pending']
                    st.rerun()
                if c2.button("❌ Cancelar", use_container_width=True):
                    del st.session_state['pending']
                    st.rerun()
        else:
            st.error(res['msg'])
            del st.session_state['pending']

# Área Principal
nome_mes = MESES_PT[mes_selecionado_idx].upper()

# Renderização do Grid
cal = calendar.Calendar(firstweekday=6)
dias_mes = list(cal.itermonthdates(2026, mes_selecionado_idx))
excecoes_db = carregar_dados()

# Header Bonito
st.markdown(f"""
<div class="header-container">
    <div style="font-size: 1.8rem; font-weight: 800; color: #1B5E20; letter-spacing: -1px;">
        {nome_mes} <span style="font-weight:300; color:#9CA3AF">2026</span>
    </div>
    <div style="font-size: 0.9rem; color: #6B7280; font-weight:500">
        Awake Health
    </div>
</div>
""", unsafe_allow_html=True)

# Grid Headers
cols = st.columns(7)
dias_semana = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]
html_headers = "".join([f'<div class="weekday-header">{d}</div>' for d in dias_semana])
st.markdown(f'<div class="calendar-grid" style="margin-bottom:10px">{html_headers}</div>', unsafe_allow_html=True)

# Grid Dias
html_grid = '<div class="calendar-grid">'

for dia in dias_mes:
    # Lógica de Visual (CSS Classes)
    css_class = "day-card"
    if dia.month != mes_selecionado_idx:
        css_class += " past-day" # Usa mesmo estilo de passado para dias de outro mês
        opacity_style = "opacity: 0.4;"
    else:
        opacity_style = ""
        if dia < HOJE: css_class += " past-day"
        if dia == HOJE: css_class += " today-card"

    # Conteúdo do Card
    conteudo_html = ""
    
    # 1. Checa Exceções (DB)
    if dia in excecoes_db:
        exc = excecoes_db[dia]
        tipo = exc['tipo']
        desc = exc['descricao']
        
        classe_chip = "evt-special"
        if tipo == "recesso": classe_chip = "evt-recesso"
        if tipo == "cancelado": 
            conteudo_html += f'<div class="event-chip evt-recesso" style="text-decoration:line-through">Cancelado</div>'
        else:
            conteudo_html += f'<div class="event-chip {classe_chip}">{desc}</div>'

    # 2. Checa Feriados
    elif dia in FERIADOS_2026:
        conteudo_html += f'<div class="event-chip evt-feriado">🎈 {FERIADOS_2026[dia]}</div>'

    # 3. Regras Padrão (Se não houver exceção nem feriado)
    elif dia.month == mes_selecionado_idx: # Só mostra agenda padrão se for dia do mês atual
        wd = dia.weekday()
        # Regra Teca
        if wd == 1 and dia.month not in [1, 7]:
            conteudo_html += '<div class="event-chip evt-teca">08h15 Talk Med.</div>'
        
        # Regra Sound Healing
        sh_text = ""
        if wd == 0: sh_text = "19h SH (Haran)"
        elif wd == 1: sh_text = "19h SH (Karina)"
        elif wd == 2: sh_text = "19h SH (Pat)"
        elif wd == 3: sh_text = "19h SH (Pat)"
        elif wd == 4: sh_text = "19h SH (Haran)"
        elif wd == 5: sh_text = "10h SH (Karina)"
        
        if sh_text:
            conteudo_html += f'<div class="event-chip evt-sh">{sh_text}</div>'

    # Monta o HTML do dia
    day_num_color = "#2E7D32" if dia == HOJE else "#374151"
    html_grid += f"""
    <div class="{css_class}" style="{opacity_style}">
        <div class="day-number" style="color:{day_num_color}">
            {dia.day}
            {f'<span style="font-size:0.6rem; color:#2E7D32">HOJE</span>' if dia == HOJE else ''}
        </div>
        {conteudo_html}
    </div>
    """

html_grid += '</div>'
st.markdown(html_grid, unsafe_allow_html=True)
