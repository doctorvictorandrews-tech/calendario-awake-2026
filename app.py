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
    evs = d['events']
    try:
        exist = supabase.table("excecoes").select("*").eq("data", dt).execute()
        prev = exist.data[0] if exist.data else None
        
        if not evs:
            supabase.table("excecoes").upsert({"data":dt, "tipo":"cancelado", "descricao":"Limpo", "detalhes":""}).execute()
        else:
            # Gera descrição visual simples para o banco
            visuais = []
            for e in evs:
                if e.get('type') in ['c-fer', 'c-com', 'c-off']:
                    visuais.append(e.get('title'))
                else:
                    visuais.append(f"{e.get('time','')} {e.get('title','')} ({e.get('instructor','')})")
            
            visual_desc = " | ".join(visuais)
            
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": evs[0].get('type','especial'), 
                "descricao": visual_desc, 
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
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    try:
        current_data = supabase.table("excecoes").select("data, descricao, tipo").execute().data
        db_context = json.dumps(current_data)
    except: db_context = "[]"

    sys_prompt = f"""
    Você é a IA Assistente do "Calendário Awake 2026". Hoje: {hoje}.
    
    >>> SEU PAPEL:
    1. Você é uma assistente geral e amigável. Pode conversar sobre a vida, filosofia ou dúvidas gerais.
    2. Você é a guardiã do calendário.
    
    >>> AGENDA PADRÃO (Matriz Fixa):
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    
    >>> EXCEÇÕES NO BANCO: {db_context}
    
    >>> REGRAS DE AÇÃO (CRÍTICO):
    - Se o usuário APENAS conversar ou tirar dúvida ("Que dia é hoje?", "Tem aula quarta?"), responda no campo 'reply' e deixe 'actions' como lista VAZIA []. NÃO CADASTRE NADA.
    - Só gere 'actions' se houver uma ORDEM CLARA de modificação ("Marque...", "Cancele...", "Mude...").
    - Se a ordem for ambígua, PERGUNTE antes de agir (retorne actions []).
    
    >>> DADOS:
    - Feriados/Datas Comemorativas: Não precisam de hora/instrutor.
    - Experiências (SH, Talk, Especial): PRECISAM de time, title, instructor.
    
    >>> OUTPUT JSON:
    {{ 
        "reply": "...", 
        "actions": [ {{ "date": "YYYY-MM-DD", "type": "...", "time": "...", "title": "...", "instructor": "...", "rich_details": "..." }} ] 
    }}
    """

    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":sys_prompt}]+history+[{"role":"user","content":user_msg}], response_format={"type":"json_object"}, temperature=0.3)
        ai_resp = json.loads(comp.choices[0].message.content)
        cnt = 0
        
        # Só processa se tiver ações reais
        for a in ai_resp.get('actions',[]):
            try:
                exist = supabase.table("excecoes").select("*").eq("data", a['date']).execute()
                prev = exist.data[0] if exist.data else None
                
                # Monta estrutura
                structured_event = [{
                    "time": a.get('time', ''),
                    "title": a.get('title', 'Evento'),
                    "instructor": a.get('instructor', ''),
                    "details": a.get('rich_details', ''),
                    "type": a.get('type', 'especial')
                }]
                
                # Descrição visual simples
                if a['type'] in ['c-fer', 'c-com', 'recesso']:
                    desc_str = a.get('title', 'Evento')
                else:
                    desc_str = f"{a.get('time')} {a.get('title')} ({a.get('instructor')})"

                payload = {
                    "data": a['date'], 
                    "tipo": a['type'], 
                    "descricao": desc_str, 
                    "detalhes": json.dumps(structured_event)
                }
                
                if a['type'] == 'cancelado':
                    payload = {"data":a['date'], "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}

                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({"user_name":user_name, "target_date":a['date'], "action_summary":f"{a['type']} IA", "previous_state":prev}).execute()
                cnt+=1
            except: pass
            
        return jsonify({"ok":True, "reply": ai_resp.get("reply", "Feito."), "actions_count":cnt})
    except Exception as e: return jsonify({"ok":False,"reply":str(e)})

if __name__ == '__main__': app.run(debug=True)
