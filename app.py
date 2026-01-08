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
    print(f"Erro de Configuração: {e}")

SP_TZ = pytz.timezone('America/Sao_Paulo')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_events', methods=['GET'])
def get_events():
    try:
        response = supabase.table("excecoes").select("*").execute()
        return jsonify(response.data)
    except:
        return jsonify([])

@app.route('/api/get_logs', methods=['GET'])
def get_logs():
    try:
        response = supabase.table("audit_logs").select("*").order("created_at", desc=True).limit(50).execute()
        return jsonify(response.data)
    except:
        return jsonify([])

@app.route('/api/undo', methods=['POST'])
def undo():
    d = request.json
    try:
        log = supabase.table("audit_logs").select("*").eq("id", d['log_id']).execute().data
        if not log:
            return jsonify({"ok": False})
        prev = log[0]['previous_state']
        if prev:
            clean = {k: v for k, v in prev.items() if k not in ['id', 'created_at']}
            supabase.table("excecoes").upsert(clean).execute()
        else:
            supabase.table("excecoes").delete().eq("data", log[0]['target_date']).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

@app.route('/api/save_day', methods=['POST'])
def save_day():
    d = request.json
    dt = d['date']
    evs = d['events']
    try:
        exist = supabase.table("excecoes").select("*").eq("data", dt).execute()
        prev = exist.data[0] if exist.data else None

        if not evs:
            supabase.table("excecoes").upsert({
                "data": dt, "tipo": "cancelado", "descricao": "Limpo", "detalhes": ""
            }).execute()
        else:
            visuais = []
            for e in evs:
                if e.get('type') in ['c-fer', 'c-com', 'c-off']:
                    visuais.append(e.get('title'))
                else:
                    visuais.append(f"{e.get('time','')} {e.get('title','')} ({e.get('instructor','')})")

            supabase.table("excecoes").upsert({
                "data": dt,
                "tipo": evs[0].get('type', 'especial'),
                "descricao": " | ".join(visuais),
                "detalhes": json.dumps(evs)
            }).execute()

        supabase.table("audit_logs").insert({
            "user_name": d.get('user', 'Manual'),
            "target_date": dt,
            "action_summary": "Edição Manual",
            "previous_state": prev
        }).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)})

# --- HELPER: EXTRAÇÃO ROBUSTA DE JSON ---
def extract_json_from_text(text):
    """
    Tenta encontrar um objeto JSON válido dentro de uma string de texto.
    Resolve o problema da IA adicionar texto antes ou depois do JSON.
    """
    try:
        # Tenta parse direto
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Busca o padrão JSON {...} usando Regex (dotall para pegar quebras de linha)
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
        except Exception:
            pass
    return None

# --- CÉREBRO DA IA (MODO DUAL: GESTORA + EXPERT) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    if not GROQ_API_KEY:
        return jsonify({"ok": False, "reply": "Erro API: Chave não configurada."})
    
    d = request.json
    user_msg = d['text']
    history = d.get('history', [])
    user_name = d.get('user', 'Usuário')

    hoje = datetime.now(SP_TZ).strftime("%Y-%m-%d (%A)")

    # 1. Recupera o que já mudou no calendário
    try:
        current_data = supabase.table("excecoes").select("data, descricao").execute().data
        db_context = json.dumps(current_data)
    except:
        db_context = "[]"

    # 2. O PROMPT MESTRE
    sys_prompt = f"""
    Você é a IA do "Awake Calendar 2026". Hoje é {hoje}.

    >>> SUAS DUAS FUNÇÕES:
    1. **Gestora de Agenda (PRIORIDADE MÁXIMA):** Se o usuário falar sobre datas, eventos, aulas ou horários, você deve gerenciar o calendário com precisão absoluta.
    2. **Assistente Expert:** Se o usuário perguntar sobre filosofia, bem-estar, textos para posts ou dúvidas gerais, use sua inteligência ilimitada para ajudar, mantendo um tom profissional e acolhedor.

    >>> CONHECIMENTO DO TEMPO (MATRIZ FIXA):
    - Seg: 19h SH (Haran)
    - Ter: 08h15 Talk Med. (Teca) | 19h SH (Karina)
    - Qua/Qui: 19h SH (Pat)
    - Sex: 10h SH (Haran)
    - Sáb: 10h SH (Karina) | 15h SH (Karina)
    *Nota: SH = Sound Healing. Feriados e Datas Comemorativas já estão carregados no visual.*

    >>> CONTEXTO ATUAL (ALTERAÇÕES NO BANCO):
    {db_context}

    >>> COMO AGIR:
    - O usuário perguntou algo aleatório? ("Como meditar?") -> Responda no 'reply' e mande 'actions': [].
    - O usuário mandou alterar a agenda? -> Gere o JSON em 'actions'.
    - O usuário perguntou da agenda? ("O que tem dia 21?") -> Consulte a Matriz Fixa + Contexto Atual e responda no 'reply'.

    >>> FORMATO DE AÇÃO (Somente se houver alteração):
    {{
        "date": "YYYY-MM-DD",
        "action": "create" (para criar aula/experiência), "cancel" (para cancelar dia), "info" (para feriados/avisos sem hora),
        "type": "c-sh" (Verde/SH), "c-teca" (Roxo/Talk), "c-esp" (Amarelo/Geral), "c-fer" (Feriado), "c-off" (Recesso),
        "time": "HH:MM" (obrigatório para create),
        "title": "Nome" (obrigatório),
        "instructor": "Nome" (obrigatório para create),
        "details": "Texto rico/HTML se necessário"
    }}

    >>> RESPOSTA JSON OBRIGATÓRIA:
    {{
        "reply": "Sua resposta falada aqui...",
        "actions": [ ... lista de ações ou vazio ... ]
    }}
    """

    try:
        comp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt}] + history + [{"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        raw_content = comp.choices[0].message.content
        print(f"RAW AI RESPONSE: {raw_content}") # Log para debug no terminal

        # 3. EXTRAÇÃO ROBUSTA DE JSON (A CORREÇÃO PRINCIPAL)
        ai_resp = extract_json_from_text(raw_content)

        if ai_resp is None:
             # Fallback caso a extração falhe totalmente, evita o erro genérico
             return jsonify({"ok": True, "reply": "Entendi, mas tive um pequeno problema técnico ao processar sua solicitação. Poderia repetir de forma mais direta?", "actions_count": 0})

        cnt = 0

        for a in ai_resp.get('actions', []):
            try:
                target_date = a['date']
                act = a.get('action', 'create')

                # Prepara Payload
                if act == 'cancel':
                    payload = {"data": target_date, "tipo": "cancelado", "descricao": "Cancelado", "detalhes": ""}
                else:
                    # Define tipo visual
                    v_type = a.get('type', 'c-esp')

                    # Se for feriado/aviso, não precisa de hora/instrutor no visual
                    if act == 'info' or v_type in ['c-fer', 'c-com', 'c-off']:
                        desc_str = a.get('title')
                        struct = [{"title": a.get('title'), "type": v_type, "details": a.get('details', '')}]
                    else:
                        # Evento completo
                        desc_str = f"{a.get('time')} {a.get('title')} ({a.get('instructor')})"
                        struct = [{
                            "time": a.get('time', ''), "title": a.get('title', ''),
                            "instructor": a.get('instructor', ''), "type": v_type,
                            "details": a.get('details', '')
                        }]

                    payload = {
                        "data": target_date, "tipo": v_type,
                        "descricao": desc_str, "detalhes": json.dumps(struct)
                    }

                # Executa no Banco
                exist = supabase.table("excecoes").select("*").eq("data", target_date).execute()
                prev = exist.data[0] if exist.data else None
                supabase.table("excecoes").upsert(payload).execute()
                supabase.table("audit_logs").insert({
                    "user_name": user_name,
                    "target_date": target_date,
                    "action_summary": f"IA: {a.get('title', '')}",
                    "previous_state": prev
                }).execute()
                cnt += 1
            except Exception as e:
                print(f"Erro ao processar ação: {e}")
                pass

        return jsonify({"ok": True, "reply": ai_resp.get("reply", "Feito."), "actions_count": cnt})
    except Exception as e:
        print(f"Erro Crítico Chat: {e}")
        return jsonify({"ok": False, "reply": f"Erro interno: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)
