from flask import Flask, render_template, request, jsonify
from supabase import create_client
import os
import re
from datetime import datetime, date
import pytz

app = Flask(__name__)

# Configuração Supabase (Railway injeta as variáveis de ambiente)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Fuso Horário
SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    """Busca eventos do banco para o frontend desenhar"""
    try:
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/command', methods=['POST'])
def process_command():
    """Recebe texto, entende e salva"""
    data = request.json
    text = data.get('text', '').lower()
    month_idx = data.get('month', datetime.now().month) # Mês que o usuário está olhando
    
    # --- CÉREBRO NLP (Lógica Python) ---
    
    # 1. Data
    # Procura DD/MM
    match_full = re.search(r'(\d{1,2})/(\d{1,2})', text)
    # Procura "Dia XX"
    match_day = re.search(r'\bdia (\d{1,2})\b', text)
    
    d, m = None, month_idx
    if match_full: d, m = int(match_full.group(1)), int(match_full.group(2))
    elif match_day: d = int(match_day.group(1))
    
    if not d: return jsonify({"ok": False, "msg": "Data não entendida."})
    
    try:
        dt_obj = date(2026, m, d)
        dt_str = dt_obj.strftime("%Y-%m-%d")
    except: return jsonify({"ok": False, "msg": "Data inválida."})

    # 2. Tipo
    tipo = "especial"
    if "recesso" in text: tipo = "recesso"
    elif any(x in text for x in ["cancelar", "off", "remover", "tirar"]): tipo = "cancelado"

    # 3. Descrição
    desc = "CANCELADO" if tipo == "cancelado" else "RECESSO" if tipo == "recesso" else ""
    
    if tipo == "especial":
        raw = text
        raw = re.sub(r'\d{1,2}/\d{1,2}', '', raw)
        raw = re.sub(r'\bdia \d{1,2}\b', '', raw)
        
        # Hora
        hora = ""
        hm = re.search(r'(\d{1,2})[h:](\d{0,2})', raw)
        if hm: 
            hora = hm.group(0).replace(":", "h") + " "
            raw = raw.replace(hm.group(0), "")
            
        stops = ["substitua", "troque", "pelo", "pela", "por", "será", "com", "as", "às", "sh", "sound", "healing", "do", "de", "o", "a", "no", "na"]
        pattern = re.compile(r'\b(' + '|'.join(stops) + r')\b', re.IGNORECASE)
        act = pattern.sub('', raw).strip().title()
        
        # Instrutor
        instrs = ["Karina", "Haran", "Pat", "Teca", "Gabe", "Ana"]
        found = [i for i in instrs if i.lower() in text]
        for i in found: act = act.replace(i, "").replace(i.lower(), "").strip()
        final_inst = f" ({found[0]})" if found else ""
        
        desc = f"{hora}{act}{final_inst}".strip()

    # 4. Salvar no Supabase
    try:
        supabase.table("excecoes").upsert({
            "data": dt_str, "tipo": tipo, "descricao": desc
        }).execute()
        return jsonify({"ok": True, "date": dt_obj.strftime('%d/%m'), "desc": desc})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
