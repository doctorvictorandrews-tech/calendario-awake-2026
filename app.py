import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime
from groq import Groq

app = Flask(__name__)

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
            # Salva JSON completo em 'detalhes' para o frontend reconstruir
            # E usa a descricao do primeiro para visualização rápida no banco
            desc = " | ".join([e['desc'] for e in evs])
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": evs[0].get('type','especial'), 
                "descricao": desc, "detalhes": json.dumps(evs)
            }).execute()
            
        supabase.table("audit_logs").insert({"user_name":d.get('user','Manual'),"target_date":dt,"action_summary":"Edição Manual","previous_state":prev}).execute()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

@app.route('/api/chat', methods=['POST'])
def chat():
    d = request.json
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    sys = f"Hoje: {hoje}. Ano 2026. Ações: 'especial','recesso','cancelado'. Formato: 'HHh Nome'. Talk Med SEMPRE Terça. JSON output."
    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":sys}]+d.get('history',[])+[{"role":"user","content":d['text']}], response_format={"type":"json_object"})
        ai = json.loads(comp.choices[0].message.content)
        cnt=0
        for a in ai.get('actions',[]):
            try:
                exist = supabase.table("excecoes").select("*").eq("data", a['date']).execute()
                prev = exist.data[0] if exist.data else None
                supabase.table("excecoes").upsert({"data":a['date'],"tipo":a['type'],"descricao":a['description'],"detalhes":""}).execute()
                supabase.table("audit_logs").insert({"user_name":d.get('user','IA'),"target_date":a['date'],"action_summary":f"{a['type']} IA","previous_state":prev}).execute()
                cnt+=1
            except: pass
        return jsonify({"ok":True, "reply":ai.get("reply","Ok"), "actions_count":cnt})
    except Exception as e: return jsonify({"ok":False,"reply":str(e)})

if __name__ == '__main__': app.run(debug=True)
