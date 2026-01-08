import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
import google.generativeai as genai

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
# Se as chaves não existirem, o app não quebra, mas avisa nos logs
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

# Configuração Rígida para JSON
generation_config = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json", # Força a IA a falar "código"
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
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify([]) # Retorna lista vazia em caso de erro para não travar o front

@app.route('/api/chat', methods=['POST'])
def chat_with_ai():
    # Verifica se a chave existe antes de tentar
    if not GOOGLE_API_KEY:
        return jsonify({"ok": False, "reply": "ERRO CRÍTICO: Chave GOOGLE_API_KEY não encontrada no Railway."})

    data = request.json
    user_message = data.get('text', '')
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # Prompt Blindado
    system_instruction = f"""
    Atue como a IA do Calendário Awake. Hoje: {hoje_str}. Ano base: 2026.
    
    1. Identifique datas relativas (amanhã, próxima terça) baseadas em {hoje_str}.
    2. Ações possíveis: 'especial' (aulas/eventos), 'recesso', 'cancelado'.
    3. Descrição: "Horário Atividade (Instrutor)".
    
    IMPORTANTE: Responda SOMENTE em JSON seguindo este esquema exato:
    {{
        "reply": "Texto da resposta para o usuário",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "string", "description": "string" }}
        ]
    }}
    """

    try:
        # Envio para o Google
        chat = model.start_chat(history=[])
        response = chat.send_message(f"{system_instruction}\n\nUSUÁRIO DIZ: {user_message}")
        
        # Debug no Log do Railway (Para você ver o que a IA respondeu)
        print(f"RESPOSTA IA RAW: {response.text}")

        # Tenta ler o JSON
        try:
            ai_data = json.loads(response.text)
        except:
            # Se falhar o JSON, tenta limpar a string (às vezes vem com ```json no inicio)
            clean_text = response.text.replace("```json", "").replace("```", "")
            ai_data = json.loads(clean_text)

        reply_text = ai_data.get("reply", "Feito.")
        actions = ai_data.get("actions", [])
        
        # Executa no Banco
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
                print(f"Erro ao salvar no banco: {e}")

        return jsonify({
            "ok": True,
            "reply": reply_text,
            "actions_count": count
        })

    except Exception as e:
        # AQUI ESTÁ A CORREÇÃO: Mostra o erro real para você
        error_msg = str(e)
        print(f"ERRO PYTHON: {error_msg}")
        return jsonify({"ok": False, "reply": f"ERRO TÉCNICO: {error_msg}"})

if __name__ == '__main__':
    app.run(debug=True)
