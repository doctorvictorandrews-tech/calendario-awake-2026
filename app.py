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

# Inicializa
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Groq(api_key=GROQ_API_KEY)

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

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
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # Prompt do Sistema (Llama 3 entende muito bem isso)
    system_prompt = f"""
    Você é a IA do Calendário Awake. Hoje é {hoje_str}. Ano 2026.
    
    TAREFA:
    1. Analise a frase do usuário.
    2. Identifique intenção de agendamento (aula, recesso, cancelar).
    3. Responda em JSON ESTRITO.

    REGRAS:
    - Se o usuário disser datas relativas ("amanhã"), calcule baseado em {hoje_str}.
    - Tipos: 'especial', 'recesso', 'cancelado'.
    - Descrição: "Horário Atividade (Instrutor)".

    JSON DE SAÍDA:
    {{
        "reply": "Sua resposta curta e amigável em português",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "tipo", "description": "descrição" }}
        ]
    }}
    """

    try:
        completion = client.chat.completions.create(
            model="llama3-70b-8192", # Modelo muito inteligente e rápido
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            temperature=0.5,
            max_tokens=1024,
            response_format={"type": "json_object"} # Garante que volta JSON
        )

        # Processamento
        response_content = completion.choices[0].message.content
        ai_data = json.loads(response_content)
        
        reply_text = ai_data.get("reply", "Feito.")
        actions = ai_data.get("actions", [])
        
        count = 0
        for action in actions:
            try:
                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": action['type'],
                    "descricao": action['description']
                }).execute()
                count += 1
            except: pass

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": count
        })

    except Exception as e:
        return jsonify({"ok": False, "reply": f"Erro Groq: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
