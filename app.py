import os
import json
import re
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
from groq import Groq

app = Flask(__name__)

# --- CONFIGURAÇÃO E SEGURANÇA ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"⚠️ ERRO DE CONFIGURAÇÃO: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÃO DE LIMPEZA DE JSON (SALVA-VIDAS) ---
def extract_clean_json(text):
    """ Encontra o primeiro JSON válido { ... } dentro do texto da IA """
    try:
        # Tenta achar o padrão JSON entre chaves
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
        return json.loads(text) # Tenta direto se não achar padrão
    except:
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
                # Se for feriado/aviso, usa só o título. Se for aula, usa formato completo.
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
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

# --- IA COM VISÃO DE RAIO-X ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro: Chave GROQ não configurada."})
    
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    # 1. Contexto do Banco
    try:
        db_data = supabase.table("excecoes").select("data, descricao").execute().data
        db_context = json.dumps(db_data)
    except Exception as e:
        db_context = "[]"
        print(f"Erro DB Context: {e}")

    # 2. Prompt Especializado
    sys_prompt = f"""
    Você é a IA Gerente do Awake Calendar 2026. Hoje: {hoje}.
    
    >>> AGENDA PADRÃO (FIXA):
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    
    >>> EXCEÇÕES NO BANCO: {db_context}
    
    >>> INSTRUÇÕES CRÍTICAS:
    1. **Conversa vs Ação:** Se o usuário falar "Oi", "Tudo bem?", "O que é SH?", RESPONDA gentilmente e retorne "actions": []. NÃO CADASTRE NADA.
    2. **Confirmação:** Se o usuário pedir para alterar a agenda, gere o JSON em "actions".
    3. **Tipos:** - 'c-fer' (Feriado), 'c-com' (Data Comemorativa), 'c-off' (Recesso): Só precisam de 'title'. 'time' e 'instructor' vazios.
       - 'c-sh', 'c-teca', 'c-esp': Precisam de 'time', 'title', 'instructor'.
    
    >>> FORMATO JSON OBRIGATÓRIO:
    {{
        "reply": "Texto de resposta...",
        "actions": [
            {{
                "date": "YYYY-MM-DD",
                "action": "create" (ou "cancel"),
                "type": "c-esp",
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
        
        # 3. Extração Segura
        raw_content = comp.choices[0].message.content
        ai_resp = extract_clean_json(raw_content)
        
        if not ai_resp:
            return jsonify({"ok":True, "reply": "Entendi, mas tive um erro técnico ao processar. Tente ser mais direto."})

        reply_text = ai_resp.get("reply", "Feito.")
        cnt = 0
        
        # 4. Execução
        for a in ai_resp.get('actions', []):
            try:
                t_date = a.get('date')
                if not t_date: continue
                
                # Prepara dados
                act = a.get('action', 'create')
                if act == 'cancel':
                    payload = {"data":t_date, "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}
                else:
                    v_type = a.get('type', 'c-esp')
                    # Limpeza de campos vazios para Feriados
                    if v_type in ['c-fer', 'c-com', 'c-off']:
                        clean_time = ""
                        clean_inst = ""
                        desc_str = a.get('title')
                    else:
                        clean_time = a.get('time', '')
                        clean_inst = a.get('instructor', '')
                        desc_str = f"{clean_time} {a.get('title')} ({clean_inst})"
                    
                    struct = [{
                        "time": clean_time, "title": a.get('title'), 
                        "instructor": clean_inst, "type": v_type, 
                        "details": a.get('details','')
                    }]
                    payload = {"data": t_date, "tipo": v_type, "descricao": desc_str, "detalhes": json.dumps(struct)}

                # Salva
                exist = supabase.table("excecoes").select("*").eq("data", t_date).execute()
                prev = exist.data[0] if exist.data else None
                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({"user_name":user_name, "target_date":t_date, "action_summary":f"IA: {act}", "previous_state":prev}).execute()
                cnt += 1
            except Exception as e_loop:
                print(f"Erro loop: {e_loop}")

        return jsonify({"ok":True, "reply": reply_text, "actions_count":cnt})

    except Exception as e:
        return jsonify({"ok":False, "reply": f"Erro interno do sistema: {str(e)}"})

if __name__ == '__main__': app.run(debug=True)
