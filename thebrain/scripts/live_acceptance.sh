#!/usr/bin/env bash
# Live acceptance smoke against a running Julian + real configured model.
# Does not start/stop processes, install dependencies, or mutate global settings.
set -Eeuo pipefail
BASE_URL="${JULIAN_TEST_BASE_URL:-http://127.0.0.1:8080}"
PYTHON_BIN="${JULIAN_TEST_PYTHON:-python3}"
OUT_DIR="${JULIAN_TEST_OUTPUT_DIR:-./logs/live-acceptance}"
mkdir -p "$OUT_DIR"
REPORT="$OUT_DIR/report.json"

"$PYTHON_BIN" - "$BASE_URL" "$REPORT" <<'PY'
import json,sys,time,urllib.request,urllib.error,uuid
base, report_path = sys.argv[1:]
report={"base_url":base,"checks":[],"started_at":time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
def record(name,passed,details):
    report['checks'].append({"name":name,"passed":bool(passed),"details":details})
def request(path, method='GET', payload=None, timeout=180):
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(base+path,data=data,method=method,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        body=r.read()
        try: return r.status,json.loads(body)
        except Exception: return r.status,body.decode('utf-8','replace')
try:
    code,health=request('/api/health',timeout=8)
    model=health.get('model',{}) if isinstance(health,dict) else {}
    ready=code==200 and health.get('status')=='ok' and model.get('status')=='reachable'
    record('backend_database_and_real_model_health',ready,{"http_status":code,"health":health})
    if not ready: raise RuntimeError('Live model/backend readiness failed. Do not proceed to acceptance chat; inspect health response and logs.')

    code,caps=request('/api/capabilities',timeout=8)
    names={c.get('name') for c in caps.get('capabilities',[])}
    needed={'research','open_url','memory_retrieval','chat_response','coding_assistant','file_analysis'}
    record('capability_registry',code==200 and needed.issubset(names),{"http_status":code,"missing":sorted(needed-names),"names":sorted(names)})

    msg='Balas persis dengan kalimat: JULIAN_LIVE_ACCEPTANCE_OK. Jangan tambahkan apa pun.'
    code,chat=request('/api/chat','POST',{"message":msg,"mode":"chat"},timeout=240)
    answer=chat.get('answer','') if isinstance(chat,dict) else ''
    trace=chat.get('trace_id') if isinstance(chat,dict) else None
    chat_ok=code==200 and chat.get('status') in ('completed','partial') and 'JULIAN_LIVE_ACCEPTANCE_OK' in answer and bool(trace)
    record('real_model_chat_and_orchestration',chat_ok,{"http_status":code,"status":chat.get('status'),"route":chat.get('route'),"answer":answer,"trace_id":trace,"warnings":chat.get('warnings',[])})
    if trace:
        audit_code,audit=request('/api/audit/'+trace,timeout=10)
        events=audit.get('events',[]) if isinstance(audit,dict) else []
        stages={e.get('stage') for e in events}
        audit_ok=audit_code==200 and {'interpret','plan','execute','verify','explain'}.issubset(stages)
        record('trace_audit_lifecycle',audit_ok,{"http_status":audit_code,"stages":sorted(stages),"event_count":len(events)})
        history_code,history=request('/api/conversations/'+chat['conversation_id'],timeout=10)
        roles=[m.get('role') for m in history.get('messages',[])] if isinstance(history,dict) else []
        record('conversation_history',history_code==200 and 'user' in roles and 'assistant' in roles,{"http_status":history_code,"roles":roles})

    research_text='Cari sumber untuk menjawab: siapa presiden Amerika Serikat pada 1 Januari 2020 dan 1 Februari 2021? Sertakan URL, kutipan verbatim yang benar-benar ada di halaman, dan tanggal akses. Jangan menebak jika sumber gagal dibuka.'
    try:
        rcode,rr=request('/api/chat','POST',{"message":research_text,"mode":"research"},timeout=240)
        evid=rr.get('evidence',[]) if isinstance(rr,dict) else []
        readable=[e for e in evid if e.get('open_status')=='opened' and e.get('content_status')=='read' and e.get('content_excerpt')]
        ver=rr.get('verification',{}) if isinstance(rr,dict) else {}
        # The test passes either with readable evidence and an explicit verification result, or a truthful stage failure.
        explicit_failure=rr.get('status') in ('failed','partial') and bool(rr.get('warnings')) and any(term in rr.get('answer','').lower() for term in ('belum bisa','belum berhasil','belum ada','failed','tidak akan mengarang'))
        research_ok=rcode==200 and ((len(readable)>0 and ver.get('semantic_entailment_verified') is False) or explicit_failure)
        record('live_research_evidence_or_truthful_failure',research_ok,{"http_status":rcode,"status":rr.get('status'),"readable_source_count":len(readable),"verification":ver,"warnings":rr.get('warnings',[]),"answer_excerpt":rr.get('answer','')[:1600]})
    except Exception as exc:
        record('live_research_evidence_or_truthful_failure',False,{"error":type(exc).__name__+': '+str(exc)})
except Exception as exc:
    record('live_acceptance_setup',False,{"error":type(exc).__name__+': '+str(exc)})
report['finished_at']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
report['passed']=all(c['passed'] for c in report['checks'])
with open(report_path,'w',encoding='utf-8') as f: json.dump(report,f,ensure_ascii=False,indent=2)
print(json.dumps(report,ensure_ascii=False,indent=2))
raise SystemExit(0 if report['passed'] else 1)
PY
