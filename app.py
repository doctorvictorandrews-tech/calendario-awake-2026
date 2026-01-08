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

# AGENDA PADRÃO (A "Matriz" que a IA precisa conhecer)
AGENDA_PADRAO = {
    0: [], # Domingo
    1: [{"time": "19:00", "title": "Sound Healing", "instructor": "Haran"}], # Seg
    2: [{"time": "08:15", "title": "Talk Meditation", "instructor": "Teca"}, {"time": "19:00", "title": "Sound Healing", "instructor": "Karina"}], # Ter
    3: [{"time": "19:00", "title": "Sound Healing", "instructor": "Pat"}], # Qua
    4: [{"time": "19:00", "title": "Sound Healing", "instructor": "Pat"}], # Qui
    5: [{"time": "10:00", "title": "Sound Healing", "instructor": "Haran"}], # Sex
    6: [{"time": "10:00", "title": "Sound Healing", "instructor": "Karina"}, {"time": "15:00", "title": "Sound Healing", "instructor": "Karina"}] # Sab
}

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
            # Se a lista veio vazia, é cancelamento total do dia
            supabase.table("excecoes").upsert({"data":dt, "tipo":"cancelado", "descricao":"Cancelado", "detalhes":""}).execute()
        else:
            # Gera descrição visual simples
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

# --- INTELIGÊNCIA ARTIFICIAL BLINDADA ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro API."})
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    
    hoje_dt = datetime.now(SP_TZ)
    hoje_str = hoje_dt.strftime("%Y-%m-%d (%A)")
    
    # 1. RECUPERA CONTEXTO DO BANCO (O que já mudou)
    try:
        db_data = supabase.table("excecoes").select("data, descricao, tipo").execute().data
        # Otimização: Transforma em dicionário para o prompt ficar menor e mais limpo
        db_summary = {item['data']: item['descricao'] for item in db_data}
        db_context_str = json.dumps(db_summary, indent=2)
    except:
        db_context_str = "{}"

    # 2. PROMPT DE ENGENHARIA (O CÉREBRO)
    sys_prompt = f"""
    Você é a IA Gerente do Awake Calendar. Hoje é {hoje_str}. Ano 2026.
    
    >>> SEU CONHECIMENTO DO TEMPO (AGENDA PADRÃO FIXA):
    - Segunda: 19h SH (Haran)
    - Terça: 08h15 Talk Med. (Teca) [exceto Jan/Jul] | 19h SH (Karina)
    - Quarta: 19h SH (Pat)
    - Quinta: 19h SH (Pat)
    - Sexta: 10h SH (Haran)
    - Sábado: 10h SH (Karina) | 15h SH (Karina)
    - Domingo: Livre
    
    >>> O QUE JÁ FOI ALTERADO (EXCEÇÕES NO BANCO):
    {db_context_str}
    
    >>> SUAS REGRAS DE OURO:
    1. INTELIGÊNCIA: Se o usuário pedir para cancelar algo, verifique na Agenda Padrão se existe. Se ele pedir para marcar num horário ocupado, avise.
    2. CONVERSA: Se o usuário só der "Oi" ou perguntar algo, responda gentilmente e NÃO gere 'actions'.
    3. COMANDOS: Só gere 'actions' se houver intenção clara de mudança na agenda.
    4. DADOS: Feriados/Datas Comemorativas são apenas rótulos (não precisam de hora/instrutor). Experiências precisam.
    
    >>> FORMATO DE RESPOSTA (JSON APENAS):
    {{
        "reply": "Texto de resposta para o usuário.",
        "actions": [
            {{
                "date": "YYYY-MM-DD",
                "action": "create" (ou "cancel" / "recess"),
                "type": "c-sh" (para Sound Healing), "c-teca" (Talk), "c-esp" (Especial), "c-fer" (Feriado),
                "time": "HH:MM",
                "title": "Nome do Evento",
                "instructor": "Nome",
                "details": "Texto rico HTML (opcional)"
            }}
        ]
    }}
    """

    try:
        comp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role":"system","content":sys_prompt}] + history + [{"role":"user","content":user_msg}], 
            response_format={"type":"json_object"}, 
            temperature=0.2 # Temperatura baixa = Mais precisão, menos erro
        )
        ai_resp = json.loads(comp.choices[0].message.content)
        cnt = 0
        
        # PROCESSAMENTO PYTHON (BLINDAGEM CONTRA ERRO DA IA)
        for action in ai_resp.get('actions', []):
            try:
                target_date = action.get('date')
                act_type = action.get('action')
                
                # Snapshot para Undo
                exist = supabase.table("excecoes").select("*").eq("data", target_date).execute()
                prev = exist.data[0] if exist.data else None
                
                payload = {}
                
                if act_type == 'cancel':
                    payload = {"data": target_date, "tipo": "cancelado", "descricao": "Cancelado pela IA", "detalhes": ""}
                
                elif act_type in ['create', 'recess']:
                    # O Python garante que a estrutura está correta, mesmo se a IA falhar
                    clean_type = action.get('type', 'c-esp')
                    clean_time = action.get('time', '')
                    clean_title = action.get('title', 'Evento')
                    clean_inst = action.get('instructor', '')
                    clean_det = action.get('details', '')
                    
                    # Cria a lista de eventos estruturada
                    structured_event = [{
                        "time": clean_time,
                        "title": clean_title,
                        "instructor": clean_inst,
                        "details": clean_det,
                        "type": clean_type
                    }]
                    
                    # Monta descrição visual
                    if clean_type in ['c-fer', 'c-com', 'c-off']:
                        vis_desc = clean_title
                    else:
                        vis_desc = f"{clean_time} {clean_title} ({clean_inst})"
                        
                    payload = {
                        "data": target_date,
                        "tipo": clean_type if act_type == 'create' else 'recesso',
                        "descricao": vis_desc,
                        "detalhes": json.dumps(structured_event)
                    }

                if payload:
                    supabase.table("excecoes").upsert(payload).execute()
                    supabase.table("audit_logs").insert({
                        "user_name": user_name,
                        "target_date": target_date,
                        "action_summary": f"IA: {act_type} - {action.get('title','')}",
                        "previous_state": prev
                    }).execute()
                    cnt += 1
                    
            except Exception as loop_err:
                print(f"Erro no loop da IA: {loop_err}")
                continue

        return jsonify({"ok":True, "reply": ai_resp.get("reply", "Processado."), "actions_count":cnt})

    except Exception as e:
        print(f"Erro Crítico IA: {e}")
        return jsonify({"ok":False, "reply": "Desculpe, tive um erro técnico. Tente reformular."})

if __name__ == '__main__': app.run(debug=True)
