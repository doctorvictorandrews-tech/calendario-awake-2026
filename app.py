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
            # Monta descrição visual para legado
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

# --- INTELIGÊNCIA SIMPLIFICADA (ESTRATÉGIA DO PIPE | ) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro API."})
    d = request.json
    
    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")
    
    try:
        db_data = supabase.table("excecoes").select("data, descricao").execute().data
        db_context = json.dumps(db_data)
    except: db_context = "[]"

    # PROMPT: Pedimos para a IA usar o formato "HORA|TITULO|INSTRUTOR"
    # É muito difícil ela errar isso.
    sys_prompt = f"""
    Você é a IA do "Awake Calendar 2026". Hoje: {hoje}.
    
    >>> AGENDA PADRÃO:
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    
    >>> MUDANÇAS NO BANCO: {db_context}
    
    >>> COMANDOS:
    1. Responda dúvidas normalmente.
    2. Se for para ALTERAR a agenda, use o JSON abaixo.
    
    >>> IMPORTANTE SOBRE DADOS (Regra do Separador):
    Para preencher o campo 'content', use o formato: "HORA|TITULO|INSTRUTOR".
    Exemplo: "19:00|Yoga|Ana" ou "08:00|Meditação|Gui".
    Se for feriado ou cancelamento, coloque apenas o NOME.
    
    >>> JSON OUTPUT:
    {{
        "reply": "Resposta...",
        "actions": [
            {{
                "date": "YYYY-MM-DD",
                "action": "create" (ou "cancel"),
                "type": "c-sh" (ou c-teca, c-esp, c-fer, c-off),
                "content": "HORA|TITULO|INSTRUTOR"
            }}
        ]
    }}
    """

    try:
        comp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":sys_prompt}]+d.get('history',[])+[{"role":"user","content":d['text']}], response_format={"type":"json_object"}, temperature=0.2)
        ai_resp = json.loads(comp.choices[0].message.content)
        cnt = 0
        
        for a in ai_resp.get('actions',[]):
            try:
                target_date = a['date']
                act = a.get('action')
                content = a.get('content', '')
                v_type = a.get('type', 'c-esp')
                
                # PYTHON FAZ O TRABALHO PESADO DE ESTRUTURAR
                if act == 'cancel':
                    payload = {"data":target_date, "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}
                else:
                    # Quebra a string "19:00|Yoga|Pat"
                    parts = content.split('|')
                    
                    if len(parts) >= 3:
                        # Formato completo (Experiência)
                        time, title, instructor = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        struct = [{"time": time, "title": title, "instructor": instructor, "type": v_type, "details": ""}]
                        desc_str = f"{time} {title} ({instructor})"
                    else:
                        # Formato simples (Feriado/Aviso)
                        title = parts[0].strip()
                        struct = [{"time": "", "title": title, "instructor": "", "type": v_type, "details": ""}]
                        desc_str = title

                    payload = {
                        "data": target_date, "tipo": v_type,
                        "descricao": desc_str, 
                        "detalhes": json.dumps(struct) # Salva estruturado para o Frontend
                    }

                exist = supabase.table("excecoes").select("*").eq("data", target_date).execute()
                prev = exist.data[0] if exist.data else None
                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({"user_name":d.get('user','Usuario'),"target_date":target_date,"action_summary":f"IA: {act}","previous_state":prev}).execute()
                cnt+=1
            except Exception as loop_err: print(f"Erro loop: {loop_err}")
            
        return jsonify({"ok":True, "reply": ai_resp.get("reply", "Feito."), "actions_count":cnt})
    except Exception as e: return jsonify({"ok":False,"reply":str(e)})

if __name__ == '__main__': app.run(debug=True)
