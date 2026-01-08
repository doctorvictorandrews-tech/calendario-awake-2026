from flask import Flask, render_template, request, jsonify
from supabase import create_client
import os
import re
from datetime import datetime, date, timedelta
import pytz
import dateparser
from unidecode import unidecode

app = Flask(__name__)

# Configuração Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        # Busca sem cache para garantir tempo real
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/command', methods=['POST'])
def process_command():
    data = request.json
    raw_text = data.get('text', '')
    
    # --- MOTOR DE INTELIGÊNCIA ARTIFICIAL (NLP) ---
    
    # 1. Identificar a DATA (O passo mais difícil)
    # Configurações para entender "próxima terça", "amanhã", "dia 20"
    settings = {
        'PREFER_DATES_FROM': 'future',
        'DATE_ORDER': 'DMY',
        'RELATIVE_BASE': datetime.now(SP_TZ),
        'PREFER_DAY_OF_MONTH': 'current'
    }
    
    # Pré-processamento para ajudar o parser
    text_for_date = raw_text.lower()
    # Se o usuário digitou apenas "dia 20", o dateparser precisa saber o mês atual se não especificado
    if re.search(r'\bdia \d{1,2}\b', text_for_date) and "/" not in text_for_date:
        mes_atual_nome = datetime.now(SP_TZ).strftime("%B") # Ex: January
        # Tradução manual rápida para ajudar o parser se necessário, mas ele entende PT
    
    dt_obj = dateparser.parse(text_for_date, languages=['pt'], settings=settings)
    
    # Fallback: Se ele não entendeu, tenta regex bruta de DD/MM
    if not dt_obj:
        match = re.search(r'(\d{1,2})/(\d{1,2})', raw_text)
        if match:
            try:
                dt_obj = datetime(2026, int(match.group(2)), int(match.group(1)))
            except: pass

    if not dt_obj:
        return jsonify({"ok": False, "msg": "Não entendi a data. Tente 'Dia 20' ou 'Amanhã'."})

    # Forçar ano 2026 se a intenção for clara (Opcional, ou deixa dinâmico)
    # dt_obj = dt_obj.replace(year=2026) 
    dt_str = dt_obj.strftime("%Y-%m-%d")
    dt_display = dt_obj.strftime("%d/%m")

    # 2. Identificar TIPO DE AÇÃO
    clean_text = unidecode(raw_text.lower())
    tipo = "especial"
    if any(x in clean_text for x in ["recesso", "feriado", "folga"]): tipo = "recesso"
    elif any(x in clean_text for x in ["cancelar", "remover", "tirar", "off", "sem aula"]): tipo = "cancelado"

    # 3. Extrair CONTEÚDO (Quem, O Que, Que Horas)
    desc = "CANCELADO"
    if tipo == "recesso": desc = "RECESSO"
    
    if tipo == "especial":
        # Remove a data da frase para sobrar só a atividade
        # Estratégia: Remover números de dia e nomes de meses/dias da semana
        rest = raw_text
        # Remove hora (guarda para formatar)
        hora = ""
        hora_match = re.search(r'(\d{1,2})[h:](\d{0,2})', rest, re.IGNORECASE)
        if hora_match:
            h = hora_match.group(1)
            m = hora_match.group(2)
            if m and m != "00": hora = f"{h}h{m}"
            else: hora = f"{h}h"
            # Remove a hora do texto original para não duplicar
            rest = rest.replace(hora_match.group(0), "")

        # Lista de palavras para limpar ("Lixo")
        garbage = [
            "no dia", "dia", "em", "na", "para", "o", "a", "as", "às", "de", "do", "da",
            "substitua", "troque", "altere", "coloque", "por", "pelo", "pela", 
            "sh", "sound", "healing", "vai ter", "será", "com", "ministrada"
        ]
        
        # Remove data detectada (aproximação)
        date_str_input = re.search(r'\d{1,2}/\d{1,2}', rest)
        if date_str_input: rest = rest.replace(date_str_input.group(0), "")
        rest = re.sub(r'\bdia \d{1,2}\b', '', rest, flags=re.IGNORECASE)

        # Limpa palavras de ligação
        for g in garbage:
            pattern = re.compile(r'\b' + re.escape(g) + r'\b', re.IGNORECASE)
            rest = pattern.sub('', rest)

        # Identifica Instrutor (Fuzzy Search Manual)
        known_instructors = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana", "Victor"]
        instrutor_found = ""
        
        for inst in known_instructors:
            if unidecode(inst.lower()) in unidecode(rest.lower()):
                instrutor_found = inst
                # Remove o nome do instrutor da atividade para formatar bonito no final
                pattern = re.compile(re.escape(inst), re.IGNORECASE)
                rest = pattern.sub('', rest)
        
        # O que sobrou é a atividade
        atividade = " ".join(rest.split()).title() # Remove espaços extras e capitaliza
        if not atividade: atividade = "Evento Especial"

        # Monta a string final perfeita
        if instrutor_found:
            desc = f"{hora} {atividade} ({instrutor_found})".strip()
        else:
            desc = f"{hora} {atividade}".strip()

    # 4. Salvar
    try:
        supabase.table("excecoes").upsert({
            "data": dt_str, "tipo": tipo, "descricao": desc
        }).execute()
        return jsonify({"ok": True, "date": dt_display, "desc": desc})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
