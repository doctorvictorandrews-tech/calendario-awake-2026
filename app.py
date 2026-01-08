import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
from groq import Groq

app = Flask(__name__)

# --- CONFIGURAÇÃO (LÊ DO RAILWAY) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Inicializa conexões com tratamento de erro básico
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    groq_client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Erro de Configuração: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

# --- ROTAS DE INTERFACE ---
@app.route('/')
def home():
    return render_template('index.html')

# --- ROTAS DE DADOS (CALENDÁRIO) ---
@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify([])

# --- ROTAS DE AUDITORIA E LOGS ---
@app.route('/api/get_logs', methods=['GET'])
def get_logs():
    try:
        # Pega os últimos 50 logs ordenados por data
        response = supabase.table("audit_logs").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/undo', methods=['POST'])
def undo_action():
    data = request.json
    log_id = data.get('log_id')
    
    try:
        # 1. Busca o registro de log
        log_res = supabase.table("audit_logs").select("*").eq("id", log_id).execute()
        if not log_res.data:
            return jsonify({"ok": False, "msg": "Log não encontrado."})
        
        log_entry = log_res.data[0]
        prev_state = log_entry['previous_state'] # O "backup" de como era antes
        target_date = log_entry['target_date']
        
        # 2. Restaura o estado anterior
        if prev_state:
            # Se havia um evento antes, coloca ele de volta
            # (Removemos a chave 'id' se existir para evitar conflito na reinserção)
            if 'id' in prev_state: del prev_state['id']
            supabase.table("excecoes").upsert(prev_state).execute()
        else:
            # Se não havia nada (era padrão), deleta a exceção atual
            supabase.table("excecoes").delete().eq("data", target_date).execute()
            
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# --- ROTA DE INTELIGÊNCIA (GROQ LLAMA 3) ---
@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not GROQ_API_KEY:
        return jsonify({"ok": False, "reply": "Erro Crítico: Chave GROQ não configurada no Railway."})

    data = request.json
    user_message = data.get('text', '')
    user_name = data.get('user', 'Anônimo') # Quem está fazendo a alteração
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # Prompt do Sistema (Cérebro da IA)
    system_prompt = f"""
    Você é a 'Awake AI', gerente do calendário. 
    Hoje é: {hoje_str}. O ano de referência é 2026.
    
    SUA TAREFA:
    1. Interpretar a solicitação do usuário em linguagem natural.
    2. Calcular datas relativas (ex: "amanhã", "próxima terça") baseadas em {hoje_str} e no ano 2026.
    3. Extrair a ação: 'especial' (criar aula/evento), 'recesso' (bloquear dia), 'cancelado' (remover).
    4. Formatar descrição como: "Horário Atividade (Instrutor)". Ex: "19h Yoga (Pat)".
    
    IMPORTANTE: Responda APENAS um JSON válido. Sem texto extra.
    
    JSON SCHEMA:
    {{
        "reply": "Sua resposta natural e curta para o usuário.",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "tipo_da_acao", "description": "Texto final do card" }}
        ]
    }}
    """

    try:
        # Envio para a Groq
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"USUÁRIO ({user_name}): {user_message}"}
            ],
            temperature=0.5,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )

        # Processamento da Resposta
        response_content = completion.choices[0].message.content
        ai_data = json.loads(response_content)
        
        reply_text = ai_data.get("reply", "Feito.")
        actions = ai_data.get("actions", [])
        
        count = 0
        for action in actions:
            try:
                target_dt = action['date']
                
                # 1. AUDITORIA: Salvar como estava antes (Snapshot)
                existing = supabase.table("excecoes").select("*").eq("data", target_dt).execute()
                prev_state = existing.data[0] if existing.data else None
                
                # 2. EXECUÇÃO: Aplicar a mudança
                # Normaliza tipo para evitar erros
                tipo_safe = action['type']
                if tipo_safe not in ['especial', 'recesso', 'cancelado']: tipo_safe = 'especial'

                supabase.table("excecoes").upsert({
                    "data": target_dt,
                    "tipo": tipo_safe,
                    "descricao": action['description']
                }).execute()
                
                # 3. REGISTRO: Gravar no Log quem fez o quê
                supabase.table("audit_logs").insert({
                    "user_name": user_name,
                    "target_date": target_dt,
                    "action_summary": f"Definiu: {action['description']}",
                    "previous_state": prev_state
                }).execute()
                
                count += 1
            except Exception as e:
                print(f"Erro ao salvar ação: {e}")

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": count
        })

    except Exception as e:
        return jsonify({"ok": False, "reply": f"Erro técnico na IA: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
