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

@app.route('/api/get_logs', methods=['GET'])
def get_logs():
    try:
        response = supabase.table("audit_logs").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(response.data)
    except: return jsonify([])

@app.route('/api/undo', methods=['POST'])
def undo_action():
    data = request.json
    log_id = data.get('log_id')
    try:
        print(f"Tentando desfazer Log ID: {log_id}")
        
        # 1. Busca o log
        log_res = supabase.table("audit_logs").select("*").eq("id", log_id).execute()
        if not log_res.data: 
            return jsonify({"ok": False, "msg": "Log não encontrado"})
        
        log_entry = log_res.data[0]
        prev_state = log_entry['previous_state']
        target_date = log_entry['target_date']
        
        print(f"Estado anterior para {target_date}: {prev_state}")

        # 2. Restaura
        if prev_state:
            # Limpa chaves que não podem ser inseridas manualmente ou geram conflito
            clean_state = {
                "data": prev_state["data"],
                "tipo": prev_state["tipo"],
                "descricao": prev_state["descricao"]
            }
            supabase.table("excecoes").upsert(clean_state).execute()
        else:
            # Se não tinha nada antes, deleta o que tem lá agora
            supabase.table("excecoes").delete().eq("data", target_date).execute()
            
        return jsonify({"ok": True})
    except Exception as e:
        print(f"Erro CRÍTICO no Undo: {e}")
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro: Sem chave Groq."})

    data = request.json
    user_message = data.get('text', '')
    history = data.get('history', [])
    user_name = data.get('user', 'Anônimo')
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    system_prompt = f"""
    Você é a IA do Calendário Awake. Hoje: {hoje_str}. Ano: 2026.
    
    REGRAS RÍGIDAS DE AGENDA:
    1. Talk Meditation (Teca) ocorre APENAS às TERÇAS-FEIRAS (08h15). Nunca agende Talk Med em outro dia a menos que o usuário EXIJA explicitamente.
    2. Feriados NÃO cancelam aulas automaticamente.
    3. Ao criar aula, use formato: "Horário Nome (Instrutor)". Ex: "08h15 Talk Med. (Teca)".
    
    JSON SCHEMA:
    {{
        "reply": "Resposta curta.",
        "actions": [ {{ "date": "YYYY-MM-DD", "type": "especial/recesso/cancelado", "description": "..." }} ]
    }}
    """

    messages_payload = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", messages=messages_payload,
            temperature=0.5, max_tokens=1024, response_format={"type": "json_object"}
        )
        ai_data = json.loads(completion.choices[0].message.content)
        
        count = 0
        for action in ai_data.get("actions", []):
            try:
                # Snapshot Antes
                existing = supabase.table("excecoes").select("*").eq("data", action['date']).execute()
                prev_state = existing.data[0] if existing.data else None

                # Executa
                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": action['type'],
                    "descricao": action['description']
                }).execute()

                # Log
                supabase.table("audit_logs").insert({
                    "user_name": user_name,
                    "target_date": action['date'],
                    "action_summary": f"{action['type']}: {action['description']}",
                    "previous_state": prev_state
                }).execute()
                count += 1
            except: pass

        return jsonify({"ok": True, "reply": ai_data.get("reply", "Feito."), "actions_count": count})

    except Exception as e: return jsonify({"ok": False, "reply": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
