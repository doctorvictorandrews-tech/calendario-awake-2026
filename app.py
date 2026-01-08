import os
import json
import pytz
from flask import Flask, render_template, request, jsonify
from supabase import create_client
from datetime import datetime, timedelta
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
            desc = " | ".join([e['desc'] for e in evs])
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": evs[0].get('type','especial'), 
                "descricao": desc, "detalhes": json.dumps(evs)
            }).execute()
            
        supabase.table("audit_logs").insert({"user_name":d.get('user','Manual'),"target_date":dt,"action_summary":"Edição Manual","previous_state":prev}).execute()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"ok":False,"msg":str(e)})

# --- O CÉREBRO NOVO (SUPER INTELLIGENCE) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY: return jsonify({"ok": False, "reply": "Erro de chave API."})
    
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')
    
    hoje = datetime.now(SP_TZ)
    hoje_str = hoje.strftime("%Y-%m-%d (%A)")
    
    # 1. INJETAR CONTEXTO (VISÃO DE RAIO-X)
    # Buscamos o que JÁ EXISTE no banco para a IA saber do que estamos falando.
    # Pegamos eventos do mês atual e próximo para não estourar o token limit (embora Llama 3 aguente muito).
    try:
        current_data = supabase.table("excecoes").select("data, descricao, tipo").execute().data
        calendar_context = json.dumps(current_data)
    except:
        calendar_context = "[]"

    # 2. PROMPT DE ENGENHARIA AVANÇADA (Chain of Thought)
    sys_prompt = f"""
    Você é a IA Sênior do Awake OS (Calendário 2026). Hoje: {hoje_str}.
    
    >>> ESTADO ATUAL DO CALENDÁRIO (O QUE JÁ EXISTE NO BANCO):
    {calendar_context}
    
    >>> SEU OBJETIVO:
    Gerenciar a agenda com precisão cirúrgica. Você tem "Superpoderes":
    1. Você VÊ o calendário acima. Se o usuário pedir para cancelar algo, verifique se existe.
    2. Se o usuário pedir para marcar algo num dia que já tem evento (e não for feriado), AVISE o conflito na sua resposta ("reply"), mas faça a ação se parecer intencional.
    3. Talk Meditation é EXCLUSIVO de Terça-feira (08h15). Se pedirem em outro dia, RECUSE educadamente, a menos que digam "Tenho certeza".
    4. Feriados NUNCA são removidos automaticamente.
    
    >>> FORMATO DE RESPOSTA (JSON OBRIGATÓRIO):
    {{
        "thought_process": "Pense passo a passo aqui. Ex: O usuário quer X. O dia Y já tem Z. Logo...",
        "reply": "Sua resposta final para o usuário (curta e amigável).",
        "actions": [
            {{ "date": "YYYY-MM-DD", "type": "especial/recesso/cancelado", "description": "Resumo curto", "detalhes": "HTML completo com formatação se necessário" }}
        ]
    }}
    
    Observação sobre 'detalhes': Se for um evento novo, crie um texto rico (HTML simples com <p>, <b>) descrevendo o evento de forma atraente para preencher o card.
    """

    try:
        # Envia para a Groq com o contexto completo
        comp = client.chat.completions.create(
            model="llama-3.3-70b-versatile", 
            messages=[{"role":"system","content":sys_prompt}] + history + [{"role":"user","content":user_msg}], 
            response_format={"type":"json_object"},
            temperature=0.3 # Baixamos a temperatura para ser mais preciso e menos criativo/alucinado
        )
        
        ai_resp = json.loads(comp.choices[0].message.content)
        reply = ai_resp.get("reply", "Feito.")
        thoughts = ai_resp.get("thought_process", "") # Podemos logar isso no terminal para debug
        print(f"IA PENSOU: {thoughts}")
        
        cnt = 0
        for a in ai_resp.get('actions',[]):
            try:
                exist = supabase.table("excecoes").select("*").eq("data", a['date']).execute()
                prev = exist.data[0] if exist.data else None
                
                # A IA agora gera o 'detalhes' também, enriquecendo o card
                detalhes_ia = a.get('detalhes', '')
                if not detalhes_ia: detalhes_ia = f"<p>{a['description']}</p>"
                
                supabase.table("excecoes").upsert({
                    "data":a['date'],
                    "tipo":a['type'],
                    "descricao":a['description'],
                    "detalhes": detalhes_ia
                }).execute()
                
                supabase.table("audit_logs").insert({
                    "user_name":user_name,
                    "target_date":a['date'],
                    "action_summary":f"{a['type']} (IA)",
                    "previous_state":prev
                }).execute()
                cnt+=1
            except Exception as e: print(f"Erro Ação IA: {e}")
            
        return jsonify({"ok":True, "reply": reply, "actions_count":cnt})
        
    except Exception as e: return jsonify({"ok":False,"reply":f"Erro no Cérebro: {str(e)}"})

if __name__ == '__main__': app.run(debug=True)
