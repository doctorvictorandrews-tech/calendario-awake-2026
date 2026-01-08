import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Inicializa Supabase
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Erro Supabase: {e}")

# Inicializa Google Gemini
try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Erro Google AI: {e}")

# Configuração da IA
generation_config = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

# --- CORREÇÃO DO MODELO AQUI ---
# Usamos 'gemini-1.5-flash-latest' para garantir que ele ache a versão ativa
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest", 
    generation_config=generation_config,
)

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify([])

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    if not GOOGLE_API_KEY:
        return jsonify({"ok": False, "reply": "ERRO: Chave API do Google não configurada."})

    data = request.json
    user_message = data.get('text', '')
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # Prompt Blindado
    system_instruction = f"""
    Atue como a IA do Calendário Awake. Hoje: {hoje_str}. Ano base: 2026.
    
    SUA MISSÃO:
    1. Ler a mensagem e identificar datas relativas (ex: "amanhã", "próxima sexta") com base na data de hoje ({hoje_str}).
    2. Identificar a ação: 'especial' (criar aula/evento), 'recesso' (bloquear dia), 'cancelado' (remover).
    3. Formatar a descrição: "Horário Atividade (Instrutor)". Ex: "19h Yoga (Pat)". Se não tiver horário, apenas o nome.
    
    REGRAS CRÍTICAS:
    - Responda SEMPRE em JSON puro.
    - Se for apenas conversa (ex: "oi"), devolva lista de actions vazia [].
    
    SCHEMA JSON DE RESPOSTA:
    {{
        "reply": "Texto simpático de resposta para o humano",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "especial", "description": "19h Yoga (Pat)" }}
        ]
    }}
    """

    try:
        # Envio para o Google
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nUSUÁRIO: {user_message}")
        
        # Limpeza e Parsing do JSON
        try:
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text.replace("```json", "").replace("```", "")
            ai_data = json.loads(clean_text)
        except:
            # Fallback se a IA falhar no JSON
            print(f"FALHA JSON IA: {response.text}")
            return jsonify({"ok": False, "reply": "Entendi, mas tive um erro técnico ao processar. Tente simplificar."})

        reply_text = ai_data.get("reply", "Feito.")
        actions = ai_data.get("actions", [])
        
        # Executa no Banco
        count = 0
        for action in actions:
            try:
                # Normaliza tipo se a IA alucinar
                tipo_safe = action['type']
                if tipo_safe not in ['especial', 'recesso', 'cancelado']: tipo_safe = 'especial'
                
                supabase.table("excecoes").upsert({
                    "data": action['date'],
                    "tipo": tipo_safe,
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
        error_msg = str(e)
        # Se o erro persistir como 404, avisa o usuário para checar a chave
        if "404" in error_msg:
            return jsonify({"ok": False, "reply": "Erro 404: O modelo de IA não foi encontrado. Verifique se a API Key é válida."})
        return jsonify({"ok": False, "reply": f"Erro técnico: {error_msg}"})

if __name__ == '__main__':
    app.run(debug=True)
