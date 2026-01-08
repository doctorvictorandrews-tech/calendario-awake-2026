import os
import json
import re
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

# Inicialização segura
supabase = None
client = None

try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"⚠️ AVISO DE CONFIGURAÇÃO: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÃO DE AUTO-REPARO DE JSON ---
def extract_json(text):
    """
    Tenta encontrar um JSON válido dentro de uma resposta de texto da IA.
    Muitas vezes a IA responde: 'Claro! Aqui está: { ... }'. Isso quebra o parser.
    Essa função ignora o texto e pega só o { ... }.
    """
    try:
        # Tenta parse direto
        return json.loads(text)
    except:
        # Tenta achar o primeiro '{' e o último '}'
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                json_str = text[start:end]
                return json.loads(json_str)
        except Exception as e:
            print(f"Falha ao extrair JSON: {e}")
            return None
    return None

@app.route('/')
def home(): return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try: return jsonify(supabase.table("excecoes").select("*").execute().data)
    except: return jsonify([])

@app.route('/api/get_logs', methods=['GET'])
def get_logs():
    try: return jsonify(supabase.table("audit_logs").select("*").order("created_at", desc=True).limit(50).execute().data)
    except: return jsonify([])

@app.route('/api/undo', methods=['POST'])
def undo():
    d = request.json
    try:
        log = supabase.table("audit_logs").select("*").eq("id", d['log_id']).execute().data
        if not log: return jsonify({"ok":False})
        prev = log[0]['previous_state']
        if prev:
            # Limpeza de campos de sistema antes de restaurar
            clean = {k:v for k,v in prev.items() if k not in ['id','created_at']}
            supabase.table("excecoes").upsert(clean).execute()
        else:
            supabase.table("excecoes").delete().eq("data", log[0]['target_date']).execute()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route('/api/save_day', methods=['POST'])
def save_day():
    d = request.json
    dt = d['date']
    evs = d['events']
    try:
        exist = supabase.table("excecoes").select("*").eq("data", dt).execute()
        prev = exist.data[0] if exist.data else None
        
        if not evs:
            supabase.table("excecoes").upsert({"data":dt, "tipo":"cancelado", "descricao":"Limpo", "detalhes":""}).execute()
        else:
            visuais = []
            for e in evs:
                if e.get('type') in ['c-fer', 'c-com', 'c-off']:
                    visuais.append(e.get('title'))
                else:
                    visuais.append(f"{e.get('time','')} {e.get('title','')} ({e.get('instructor','')})")
            
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": evs[0].get('type','especial'), 
                "descricao": " | ".join(visuais), 
                "detalhes": json.dumps(evs)
            }).execute()
            
        supabase.table("audit_logs").insert({"user_name":d.get('user','Manual'),"target_date":dt,"action_summary":"Edição Manual","previous_state":prev}).execute()
        return jsonify({"ok":True})
    except Exception as e: 
        print(f"Erro Save Day: {e}")
        return jsonify({"ok":False,"msg":str(e)})

# --- CÉREBRO DA IA (COM TRATAMENTO DE ERRO MELHORADO) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not client: return jsonify({"ok": False, "reply": "Erro: Chave Groq não configurada no servidor."})
    if not supabase: return jsonify({"ok": False, "reply": "Erro: Banco de Dados desconectado."})

    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    # 1. Recupera Contexto (Fail-safe)
    try:
        current_data = supabase.table("excecoes").select("data, descricao").execute().data
        db_context = json.dumps(current_data)
    except Exception as e:
        print(f"Erro ao ler banco: {e}")
        db_context = "[]"

    # 2. Prompt (Reforçado para JSON puro)
    sys_prompt = f"""
    Você é a IA do "Awake Calendar 2026". Hoje é {hoje}.
    
    >>> AGENDA PADRÃO (FIXA):
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)

    >>> BANCO DE DADOS (ALTERAÇÕES): {db_context}

    >>> INSTRUÇÕES:
    1. Responda ao usuário. Se ele pedir para alterar a agenda, gere o JSON em 'actions'.
    2. Se for dúvida ou conversa, deixe 'actions' vazio [].
    3. IMPORTANTE: Retorne APENAS o JSON válido. Nada de texto antes ou depois.

    >>> JSON SCHEMA:
    {{
        "reply": "Resposta em texto...",
        "actions": [
            {{
                "date": "YYYY-MM-DD",
                "action": "create" | "cancel" | "info",
                "type": "c-sh" | "c-teca" | "c-esp" | "c-fer" | "c-off",
                "time": "HH:MM",
                "title": "Titulo",
                "instructor": "Nome",
                "details": "HTML opcional"
            }}
        ]
    }}
    """

    try:
        comp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role":"system","content":sys_prompt}] + history + [{"role":"user","content":user_msg}], 
            response_format={"type":"json_object"}, 
            temperature=0.2
        )
        
        raw_content = comp.choices[0].message.content
        print(f"IA RAW RESPONSE: {raw_content}") # Log para debug no terminal

        # 3. EXTRAÇÃO ROBUSTA DE JSON
        ai_resp = extract_json(raw_content)
        
        if not ai_resp:
            # Se falhar totalmente, retorna resposta de erro mas mantém o chat vivo
            return jsonify({"ok": True, "reply": "Entendi, mas tive um problema técnico ao processar a ação. Tente novamente de forma mais direta.", "actions_count": 0})

        reply_text = ai_resp.get("reply", "Feito.")
        actions = ai_resp.get("actions", [])
        
        cnt = 0
        
        # 4. EXECUÇÃO SEGURA
        for a in actions:
            try:
                target_date = a.get('date')
                if not target_date: continue # Pula se não tiver data

                act = a.get('action', 'create')
                
                # Payload Builder
                if act == 'cancel':
                    payload = {"data":target_date, "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}
                else:
                    v_type = a.get('type', 'c-esp')
                    clean_time = a.get('time', '')
                    clean_title = a.get('title', 'Evento')
                    clean_inst = a.get('instructor', '')
                    
                    # Lógica para Feriados/Avisos
                    if act == 'info' or v_type in ['c-fer', 'c-com', 'c-off']:
                        desc_str = clean_title
                        struct = [{"title": clean_title, "type": v_type, "details": a.get('details','')}]
                    else:
                        # Evento completo
                        desc_str = f"{clean_time} {clean_title} ({clean_inst})"
                        struct = [{
                            "time": clean_time, "title": clean_title, 
                            "instructor": clean_inst, "type": v_type, 
                            "details": a.get('details','')
                        }]
                    
                    payload = {
                        "data": target_date, "tipo": v_type,
                        "descricao": desc_str, "detalhes": json.dumps(struct)
                    }

                # Banco
                exist = supabase.table("excecoes").select("*").eq("data", target_date).execute()
                prev = exist.data[0] if exist.data else None
                
                supabase.table("excecoes").upsert(payload).execute()
                
                # Log
                supabase.table("audit_logs").insert({
                    "user_name": user_name, 
                    "target_date": target_date, 
                    "action_summary": f"IA: {clean_title if act!='cancel' else 'Cancelamento'}", 
                    "previous_state": prev
                }).execute()
                
                cnt+=1
            except Exception as e_loop:
                print(f"Erro na ação individual: {e_loop}")
                continue # Continua para a próxima ação se uma falhar
            
        return jsonify({"ok":True, "reply": reply_text, "actions_count":cnt})

    except Exception as e:
        print(f"ERRO CRÍTICO ROUTE CHAT: {e}")
        return jsonify({"ok":False, "reply": f"Erro interno: {str(e)}"})

if __name__ == '__main__': app.run(debug=True)
