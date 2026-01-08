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
except: pass

SP_TZ = pytz.timezone('America/Sao_Paulo')

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
    evs = d['events'] # Agora vem lista de objetos {time, title, instructor...}
    try:
        exist = supabase.table("excecoes").select("*").eq("data", dt).execute()
        prev = exist.data[0] if exist.data else None
        
        if not evs:
            supabase.table("excecoes").upsert({"data":dt, "tipo":"cancelado", "descricao":"Limpo", "detalhes":""}).execute()
        else:
            # Cria uma string visual para o campo 'descricao' (retrocompatibilidade)
            # Ex: "19:00 SH (Haran) | 20:00 Yoga (Pat)"
            visual_desc = " | ".join([f"{e.get('time','')} {e.get('title','')} ({e.get('instructor','')})" for e in evs])
            
            # Salva o JSON estruturado completo em 'detalhes'
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": evs[0].get('type','especial'), 
                "descricao": visual_desc, 
                "detalhes": json.dumps(evs)
            }).execute()
            
        supabase.table("audit_logs").insert({"user_name":d.get('user','Manual'),"target_date":dt,"action_summary":"Edição Estruturada","previous_state":prev}).execute()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro API."})
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    try:
        # Contexto do Banco
        current_data = supabase.table("excecoes").select("data, descricao, tipo").execute().data
        db_context = json.dumps(current_data)
    except: db_context = "[]"

    sys_prompt = f"""
    Você é a IA do Awake OS. Hoje: {hoje}.
    
    >>> AGENDA PADRÃO (Matriz):
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    
    >>> DB ATUAL: {db_context}
    
    >>> INSTRUÇÃO CRÍTICA DE DADOS:
    Ao criar eventos, você DEVE separar os dados.
    Formato JSON de cada ação:
    {{
        "date": "YYYY-MM-DD",
        "type": "especial" (ou "recesso"/"cancelado"),
        "time": "HH:MM" (ex: "19:00"),
        "title": "Nome da Experiência" (ex: "Sound Healing"),
        "instructor": "Nome do Instrutor" (ex: "Haran"),
        "rich_details": "HTML com detalhes (opcional)"
    }}
    
    Para cancelamentos, 'time', 'title' e 'instructor' podem ser vazios.
    Se o usuário pedir algo vago ("Agende Yoga sábado"), infira horário e instrutor se possível ou invente algo lógico para preencher os campos obrigatórios.
    
    >>> OUTPUT JSON:
    {{ "reply": "...", "actions": [...] }}
    """

    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":sys_prompt}]+history+[{"role":"user","content":user_msg}], response_format={"type":"json_object"}, temperature=0.3)
        ai_resp = json.loads(comp.choices[0].message.content)
        cnt = 0
        
        for a in ai_resp.get('actions',[]):
            try:
                exist = supabase.table("excecoes").select("*").eq("data", a['date']).execute()
                prev = exist.data[0] if exist.data else None
                
                # Monta a estrutura para salvar no banco
                # Se for cancelado, salva simples. Se for evento, salva estruturado.
                if a['type'] == 'cancelado':
                    payload = {"data":a['date'], "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}
                else:
                    # Cria lista de eventos (suporta múltiplos no futuro, agora 1 por ação)
                    structured_event = [{
                        "time": a.get('time', '00:00'),
                        "title": a.get('title', 'Evento'),
                        "instructor": a.get('instructor', 'Equipe'),
                        "details": a.get('rich_details', ''),
                        "type": a.get('type', 'especial')
                    }]
                    desc_str = f"{a.get('time')} {a.get('title')} ({a.get('instructor')})"
                    payload = {
                        "data": a['date'], 
                        "tipo": a['type'], 
                        "descricao": desc_str, 
                        "detalhes": json.dumps(structured_event)
                    }

                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({"user_name":user_name, "target_date":a['date'], "action_summary":f"{a['type']} IA", "previous_state":prev}).execute()
                cnt+=1
            except Exception as e: print(f"Erro Loop IA: {e}")
            
        return jsonify({"ok":True, "reply": ai_resp.get("reply", "Feito."), "actions_count":cnt})
    except Exception as e: return jsonify({"ok":False,"reply":str(e)})

if __name__ == '__main__': app.run(debug=True)
