import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime, date
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO (LÊ DO RAILWAY) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Inicializa Clientes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GOOGLE_API_KEY)

# Configuração da IA (Gemini)
generation_config = {
    "temperature": 0.4,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
)

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        # Busca eventos do banco
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    data = request.json
    user_message = data.get('text', '')
    # Opcional: passar o mês que o usuário está vendo para contexto
    current_view_month = data.get('month', datetime.now(SP_TZ).month)
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # --- O PROMPT MESTRE ---
    system_instruction = f"""
    Você é a IA Gerente do Calendário da 'Awake Health'. 
    Hoje é {hoje_str}. O ano de referência é 2026.
    
    SUA MISSÃO:
    1. Ler a mensagem do usuário.
    2. Identificar datas (se ele disser "amanhã", "dia 20", "terça que vem", calcule baseado em {hoje_str} e no ano 2026).
    3. Extrair ações de agendamento.
    4. Responder de forma natural e amigável.

    TIPOS DE AÇÃO:
    - 'especial': Aulas, workshops, rituais (Ex: "19h Yoga (Pat)").
    - 'recesso': Feriados ou folgas.
    - 'cancelado': Remover uma aula existente.

    REGRAS DE FORMATAÇÃO:
    - Sempre formate a descrição da aula como: "Horário Atividade (Instrutor)". Ex: "19h Sound Healing (Haran)".
    - Se não houver horário, coloque apenas a atividade.
    - Se for cancelamento, a descrição deve ser "CANCELADO".
    
    RESPOSTA OBRIGATÓRIA EM JSON:
    {{
        "reply": "Sua resposta falada aqui...",
        "actions": [
            {{
                "date": "YYYY-MM-DD",
                "type": "especial" | "recesso" | "cancelado",
                "description": "Descrição formatada"
            }}
        ]
    }}
    """

    try:
        # 1. Envia para o Google
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nUSER: {user_message}")
        
        # 2. Interpreta o JSON
        ai_data = json.loads(response.text)
        reply_text = ai_data.get("reply", "Entendido.")
        actions = ai_data.get("actions", [])
        
        # 3. Executa no Banco de Dados
        success_count = 0
        for action in actions:
            try:
                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": action['type'],
                    "descricao": action['description']
                }).execute()
                success_count += 1
            except:
                continue

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": success_count
        })

    except Exception as e:
        return jsonify({"ok": False, "reply": "Desculpe, tive um erro de conexão com o cérebro da IA."})

if __name__ == '__main__':
    app.run(debug=True)
