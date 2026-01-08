import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
from groq import Groq

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Erro Config: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    # Passamos as chaves para o HTML para o Login funcionar
    return render_template('index.html', supabase_url=SUPABASE_URL, supabase_key=SUPABASE_KEY)

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except: return jsonify([])

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not GROQ_API_KEY:
        return jsonify({"ok": False, "reply": "Erro: Chave Groq não configurada."})

    data = request.json
    user_message = data.get('text', '')
    history = data.get('history', [])
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    system_prompt = f"""
    Você é a IA do Calendário Awake. Hoje é {hoje_str}. Ano base: 2026.
    
    SUA TAREFA:
    1. Acompanhar o contexto.
    2. Identificar datas relativas com base em {hoje_str}.
    3. Intenções: 'especial' (criar), 'recesso' (bloquear), 'cancelado' (remover).
    4. Formatar: "Horário Atividade (Instrutor)".
    
    JSON SCHEMA:
    {{
        "reply": "Resposta natural em português.",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "especial/recesso/cancelado", "description": "Descrição" }}
        ]
    }}
    """

    messages_payload = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=messages_payload,
            temperature=0.5,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )

        ai_data = json.loads(completion.choices[0].message.content)
        reply_text = ai_data.get("reply", "Feito.")
        actions = ai_data.get("actions", [])
        
        valid_count = 0
        
        # --- CAMADA DE SEGURANÇA E VALIDAÇÃO ---
        for action in actions:
            try:
                # 1. Valida Data
                dt_obj = datetime.strptime(action['date'], "%Y-%m-%d")
                if dt_obj.year != 2026: continue # Ignora anos errados

                # 2. Valida Tipo
                tipo_safe = action['type']
                if tipo_safe not in ['especial', 'recesso', 'cancelado']: tipo_safe = 'especial'

                # 3. Valida Descrição (Anti-Vazio)
                desc = action['description'].strip()
                if not desc and tipo_safe != 'cancelado': desc = "Evento sem nome"

                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": tipo_safe,
                    "descricao": desc
                }).execute()
                valid_count += 1
            except Exception as e:
                print(f"Bloqueio de Segurança (Dado inválido): {e}")

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": valid_count
        })

    except Exception as e:
        return jsonify({"ok": False, "reply": f"Erro técnico: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
