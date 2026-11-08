"""Account-scoped research API with persistent task ownership and BYOK."""
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from research_accounts import router, user, db, BOX, DATA
from llm_policy import Ledger, SCOPE, scoped_credentials, ENDPOINTS, process_alive, operator_key
import hashlib, os
LEDGER=Ledger(DATA/'llm-quota.sqlite')

app=FastAPI(title='DeepInsight',version='2.0.0')
app.include_router(router)

@app.on_event('startup')
def recover_interrupted_tasks():
    with db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS task_workers(task_id TEXT PRIMARY KEY,pid INTEGER NOT NULL)')
        # Result persistence precedes settlement; reconcile that crash window first.
        for row in conn.execute("SELECT id,user_id FROM tasks WHERE status='completed'"):
            LEDGER.finish(row['user_id'],row['id'],True,row['id'])
        for row in conn.execute("SELECT t.id,t.user_id,w.pid FROM tasks t JOIN task_workers w ON w.task_id=t.id WHERE t.status='running'"):
            if not process_alive(row['pid']):
                conn.execute("UPDATE tasks SET status='failed',result='服务重启，请重新提交问题。' WHERE id=?",(row['id'],))
                LEDGER.finish(row['user_id'],row['id'],False)
    LEDGER.recover()

STATIC=Path(__file__).parent/'static'
app.mount('/brand', StaticFiles(directory=STATIC/'brand'), name='brand')

@app.get('/favicon.ico', include_in_schema=False)
def product_favicon():
    from fastapi.responses import FileResponse
    return FileResponse(STATIC/'brand'/'favicon.ico', media_type='image/x-icon')

@app.middleware('http')
async def private_responses(request, call_next):
    response=await call_next(request)
    if request.url.path not in ('/styles.css','/app.js'):
        response.headers['Cache-Control']='no-store'
    return response

@app.get('/dashboard')
def dashboard(request:Request):
    try: current=user(request)
    except HTTPException: return RedirectResponse('/login',303)
    content=(STATIC/'workspace.html').read_text(encoding='utf-8')
    account='<meta name="account-id" content="'+current['id']+'">'
    content=content.replace('</head>',account+'</head>')
    controls='<div class="sidebar-account"><a href="/account">模型设置</a><form action="/logout" method="post"><button type="submit">退出登录</button></form></div>'
    return HTMLResponse(content.replace('</aside>',controls+'</aside>',1))

@app.get('/health')
def health(request:Request):
    try:
        current=user(request)
        configured=bool(current['key']) or (LEDGER.status(current['id'])['remaining']>0 and bool(operator_key()))
    except HTTPException:configured=False
    return {'status':'ok','service':'deepinsight-agent','llm_available':configured,'model':'qwen3.7-flash','langfuse_enabled':False}

class AnalyzeRequest(BaseModel):
    query:str=Field(min_length=1,max_length=2000)

def run_task(task_id, query, key, provider, owner, reserved=False):
    try:
        from main import DeepInsightEngine
        from openai import OpenAI
        engine=DeepInsightEngine()
        endpoint,model=ENDPOINTS[provider]
        engine._client=OpenAI(api_key=key,base_url=endpoint,timeout=90,max_retries=1)
        engine.model_name=model
        result=engine.chat(query,task_id)
        if not result or not result.strip() or result.startswith('❌'):raise RuntimeError('empty or failed analysis')
        status='completed'
    except Exception:
        result='分析未完成，请检查个人 Key、接口额度和网络后重试。'
        status='failed'
    with db() as conn:
        conn.execute('UPDATE tasks SET status=?,result=?,finished_at=? WHERE id=?',(status,result,datetime.now(timezone.utc).isoformat(),task_id))
    if reserved:LEDGER.finish(owner,task_id,status=='completed',task_id if status=='completed' else None)

@app.post('/analyze')
def analyze(body:AnalyzeRequest,request:Request):
    current=user(request)
    operation=request.headers.get('Idempotency-Key') or uuid.uuid4().hex
    if len(operation)>128:raise HTTPException(422,'操作编号过长')
    task_id=hashlib.sha256((current['id']+':'+operation).encode()).hexdigest()
    created=datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        old=conn.execute('SELECT query,status,created_at FROM tasks WHERE id=? AND user_id=?',(task_id,current['id'])).fetchone()
        if old:
            if old['query']!=body.query:raise HTTPException(409,'操作编号与请求不匹配')
            if old['status']!='failed':return {'task_id':task_id,'status':old['status'],'created_at':old['created_at']}
        running=conn.execute("SELECT count(*) FROM tasks WHERE user_id=? AND status='running'",(current['id'],)).fetchone()[0]
        if running>=1:raise HTTPException(429,'已有分析正在进行，请稍后提交。')
        scope={'owner':current['id'],'id':task_id,'fingerprint':hashlib.sha256(body.query.encode()).hexdigest()}
        token=SCOPE.set(scope)
        try:
            personal=(current['provider'],BOX.decrypt(current['key'].encode()).decode()) if current['key'] else None
            provider,key=scoped_credentials(personal,LEDGER)
        finally:SCOPE.reset(token)
        try:
            conn.execute('INSERT OR REPLACE INTO tasks(id,user_id,query,status,created_at) VALUES(?,?,?,?,?)',(task_id,current['id'],body.query,'running',created))
            conn.execute('INSERT OR REPLACE INTO task_workers VALUES(?,?)',(task_id,os.getpid()))
        except BaseException:
            if scope.get('reserved'):LEDGER.finish(current['id'],task_id,False)
            raise
    try:threading.Thread(target=run_task,args=(task_id,body.query,key,provider,current['id'],scope.get('reserved',False)),daemon=True).start()
    except BaseException:
        if scope.get('reserved'):LEDGER.finish(current['id'],task_id,False)
        with db() as conn:conn.execute("UPDATE tasks SET status='failed' WHERE id=?",(task_id,))
        raise
    return {'task_id':task_id,'status':'running','created_at':created}

@app.get('/result/{task_id}')
def result(task_id:str,request:Request):
    current=user(request)
    with db() as conn:
        row=conn.execute('SELECT * FROM tasks WHERE id=? AND user_id=?',(task_id,current['id'])).fetchone()
    if not row: raise HTTPException(404,'任务不存在。')
    response={k:row[k] for k in ('status','created_at','finished_at')}
    response['task_id']=row['id']
    if row['status']=='completed':response['result']=row['result']
    if row['status']=='failed':response['error']=row['result']
    return response

@app.get('/model-status')
def model_status(request:Request):
    current=user(request)
    return {'configured':bool(current['key']),**LEDGER.status(current['id'])}

@app.get('/tasks')
def tasks(request:Request):
    current=user(request)
    with db() as conn:
        return [dict(row) for row in conn.execute('SELECT id,query,status,created_at,finished_at FROM tasks WHERE user_id=? ORDER BY created_at DESC LIMIT 100',(current['id'],))]

app.mount('/',StaticFiles(directory=str(STATIC)),name='static')

