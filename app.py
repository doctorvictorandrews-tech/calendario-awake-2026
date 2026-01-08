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
    # Recebe o histórico da conversa (lista de mensagens anteriores)
    history = data.get('history', []) 
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # Prompt do Sistema (A personalidade e as regras)
    system_prompt = f"""
    Você é a IA do Calendário Awake. Hoje é {hoje_str}. Ano base: 2026.
    
    SUA TAREFA:
    1. Acompanhar a conversa e entender o contexto das mensagens anteriores.
    2. Identificar datas relativas (ex: "amanhã", "próxima sexta") com base em {hoje_str}.
    3. Extrair a intenção: 'especial' (criar aula/evento), 'recesso' (bloquear dia), 'cancelado' (remover).
    4. Formatar descrição: "Horário Atividade (Instrutor)". Ex: "19h Yoga (Pat)".
    
    IMPORTANTE: Responda APENAS com um JSON válido.
    Se o usuário apenas estiver conversando (sem pedir alteração), mande "actions": [].
    
    JSON SCHEMA:
    {{
        "reply": "Sua resposta natural em português, considerando o contexto.",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "especial/recesso/cancelado", "description": "Descrição curta" }}
        ]
    }}
    """

    # Monta a lista completa de mensagens para a IA
    # 1. Sistema (Regras) + 2. Histórico (Contexto) + 3. Mensagem Atual
    messages_payload = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=messages_payload,
            temperature=0.5,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )

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
            except Exception as e:
                print(f"Erro DB: {e}")

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": count
        })

    except Exception as e:
        return jsonify({"ok": False, "reply": f"Erro técnico: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
