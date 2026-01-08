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

# --- ROTAS DE AUDITORIA (LOGS) ---
@app.route('/api/get_logs', methods=['GET'])
def get_logs():
    try:
        # Busca os últimos 50 logs para mostrar na aba Histórico
        response = supabase.table("audit_logs").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(response.data)
    except: return jsonify([])

@app.route('/api/undo', methods=['POST'])
def undo_action():
    data = request.json
    log_id = data.get('log_id')
    try:
        # 1. Pega o backup
        log_res = supabase.table("audit_logs").select("*").eq("id", log_id).execute()
        if not log_res.data: return jsonify({"ok": False})
        
        log_entry = log_res.data[0]
        prev_state = log_entry['previous_state']
        target_date = log_entry['target_date']
        
        # 2. Reverte
        if prev_state:
            if 'id' in prev_state: del prev_state['id']
            supabase.table("excecoes").upsert(prev_state).execute()
        else:
            supabase.table("excecoes").delete().eq("data", target_date).execute()
            
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# --- CHAT INTELIGENTE ---
@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not GROQ_API_KEY:
        return jsonify({"ok": False, "reply": "Erro: Chave Groq não configurada."})

    data = request.json
    user_message = data.get('text', '')
    history = data.get('history', [])
    user_name = data.get('user', 'Anônimo') # Pega o nome do usuário
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    system_prompt = f"""
    Você é a IA do Calendário Awake. Hoje é {hoje_str}. Ano base: 2026.
    
    TAREFA:
    1. Acompanhar contexto da conversa.
    2. Identificar datas baseadas em {hoje_str}.
    3. Ações: 'especial' (criar), 'recesso' (bloquear), 'cancelado' (limpar dia).
    4. Formato: "Horário Atividade (Instrutor)".
    
    JSON SCHEMA:
    {{
        "reply": "Resposta curta e natural.",
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
        
        count = 0
        for action in actions:
            try:
                # 1. Validação Simples
                if action['type'] not in ['especial', 'recesso', 'cancelado']: action['type'] = 'especial'
                if not action['description'] and action['type'] != 'cancelado': action['description'] = "Evento"

                # 2. Auditoria (Snapshot do antes)
                existing = supabase.table("excecoes").select("*").eq("data", action['date']).execute()
                prev_state = existing.data[0] if existing.data else None

                # 3. Executa
                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": action['type'],
                    "descricao": action['description']
                }).execute()

                # 4. Salva Log
                supabase.table("audit_logs").insert({
                    "user_name": user_name,
                    "target_date": action['date'],
                    "action_summary": f"{action['type']}: {action['description']}",
                    "previous_state": prev_state
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
        return jsonify({"ok": False, "reply": f"Erro: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
