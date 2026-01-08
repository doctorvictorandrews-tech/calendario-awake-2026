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

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print(f"Erro Config: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

# --- HELPER: EXTRAÇÃO ROBUSTA DE JSON ---
def extract_json_from_text(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except: pass
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

@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro API."})
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])[-5:] # OTIMIZAÇÃO: Mantém apenas as últimas 5 mensagens para economizar tokens
    user_name = d.get('user', 'Usuário')
    
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    # 1. OTIMIZAÇÃO DE CONTEXTO
    try:
        # Pega apenas dados futuros ou recentes para não lotar a memória da IA
        # (Aqui simplificado pegando tudo, mas limitando caracteres se for gigante)
        db_data = supabase.table("excecoes").select("data, descricao").execute().data
        db_context = json.dumps(db_data)
        if len(db_context) > 6000: db_context = db_context[-6000:] # Corta se for muito grande
    except: db_context = "[]"

    sys_prompt = f"""
    Você é a IA do "Awake Calendar 2026". Hoje: {hoje}.
    
    >>> AGENDA PADRÃO:
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    
    >>> MUDANÇAS: {db_context}
    
    >>> REGRAS:
    1. Responda conversa fiada normalmente (sem actions).
    2. Se for alterar agenda, gere JSON.
    3. Tipos: 'c-fer' (Feriado - só titulo), 'c-sh' (Verde), 'c-teca' (Roxo), 'c-esp' (Amarelo).
    
    >>> JSON OUTPUT:
    {{
        "reply": "Resposta...",
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
        # MUDANÇA DE MODELO: Usando o 8b-instant para economizar limite e ser mais rápido
        comp = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role":"system","content":sys_prompt}] + history + [{"role":"user","content":user_msg}], 
            response_format={"type":"json_object"}, 
            temperature=0.2
        )
        
        raw = comp.choices[0].message.content
        ai_resp = extract_json_from_text(raw)
        
        if not ai_resp: return jsonify({"ok":True, "reply": "Erro técnico na resposta da IA. Tente novamente."})

        cnt = 0
        for a in ai_resp.get('actions',[]):
            try:
                t_date = a.get('date')
                if not t_date: continue
                act = a.get('action', 'create')
                
                if act == 'cancel':
                    payload = {"data":t_date, "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}
                else:
                    v_type = a.get('type', 'c-esp')
                    time = a.get('time','')
                    inst = a.get('instructor','')
                    title = a.get('title','')
                    
                    if v_type in ['c-fer','c-com','c-off']:
                        desc_str = title
                        time = "" 
                        inst = ""
                    else:
                        desc_str = f"{time} {title} ({inst})"
                    
                    struct = [{"time":time, "title":title, "instructor":inst, "type":v_type, "details":a.get('details','')}]
                    payload = {"data":t_date, "tipo":v_type, "descricao":desc_str, "detalhes":json.dumps(struct)}

                exist = supabase.table("excecoes").select("*").eq("data", t_date).execute()
                prev = exist.data[0] if exist.data else None
                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({"user_name":user_name, "target_date":t_date, "action_summary":f"IA: {act}", "previous_state":prev}).execute()
                cnt+=1
            except: pass
            
        return jsonify({"ok":True, "reply": ai_resp.get("reply", "Feito."), "actions_count":cnt})
    except Exception as e: 
        # Captura erro de Rate Limit específico para avisar você
        err_msg = str(e)
        if "429" in err_msg:
            return jsonify({"ok":False, "reply": "⚠️ Limite diário da IA atingido. Espere alguns minutos ou use a edição manual."})
        return jsonify({"ok":False, "reply":f"Erro: {err_msg}"})

if __name__ == '__main__': app.run(debug=True)
