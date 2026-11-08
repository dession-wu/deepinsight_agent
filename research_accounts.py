"""Independent accounts, private keys and revocable sessions for DeepInsight."""
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import parse_qs
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DATA = Path(os.environ.get('ACCOUNT_DATA_DIR', '/app/private'))
DATA.mkdir(parents=True, exist_ok=True)
KEY = DATA / 'encryption.key'
if not KEY.exists():
    with KEY.open('xb') as stream:
        stream.write(Fernet.generate_key())
    KEY.chmod(0o600)
BOX = Fernet(KEY.read_bytes())
COOKIE = '__Host-research_session'
router = APIRouter()

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

def db():
    conn = sqlite3.connect(DATA / 'accounts.sqlite', timeout=30,factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn

with db() as conn:
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,key TEXT,provider TEXT DEFAULT 'deepseek');
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),query TEXT NOT NULL,status TEXT NOT NULL,result TEXT,created_at TEXT NOT NULL,finished_at TEXT);
    CREATE TABLE IF NOT EXISTS attempts(ip TEXT NOT NULL,created REAL NOT NULL);
    ''')


def user(request):
    token = hashlib.sha256(request.cookies.get(COOKIE, '').encode()).hexdigest()
    with db() as conn:
        row = conn.execute('SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=? AND s.expires>?', (token,time.time())).fetchone()
    if not row:
        raise HTTPException(401, '请先登录')
    return dict(row)

def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()

async def form(request):
    if request.headers.get('origin') != 'https://research.podnotes.cloud':
        raise HTTPException(403, '请从本产品页面提交')
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(413)
    return {k:v[0] for k,v in parse_qs(body.decode()).items()}

def throttle(request):
    # Gateway replaces, rather than trusts, the incoming client address header.
    ip=request.headers.get('x-real-ip', request.client.host)
    with db() as conn:
        conn.execute('DELETE FROM attempts WHERE created<?',(time.time()-600,))
        count=conn.execute('SELECT count(*) FROM attempts WHERE ip=?',(ip,)).fetchone()[0]
        if count>=20:
            raise HTTPException(429,'操作频繁，请十分钟后重试')
        conn.execute('INSERT INTO attempts VALUES(?,?)',(ip,time.time()))

STYLE=':root{color-scheme:light;--canvas:#f5f7fa;--paper:#fff;--ink:#202e3c;--muted:#657484;--line:#dce3eb;--action:#245c67;--tint:#edf3f5;--error:#ad3939}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--canvas);font:16px/1.75 -apple-system,BlinkMacSystemFont,"Microsoft YaHei",sans-serif}a{color:var(--action);text-decoration:none}header,main,footer{width:min(1120px,calc(100% - 48px));margin:auto}header{min-height:88px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:24px}nav{display:flex;align-items:center;gap:26px;font-size:14px}nav a:last-child{color:var(--muted)}main{padding:56px 0 72px}h1{font-size:clamp(30px,3.4vw,44px);font-weight:650;line-height:1.45;margin:14px 0 18px;letter-spacing:0}h2{font-size:22px;line-height:1.5}h3{font-size:16px}p{color:var(--muted)}.eyebrow{font-size:13px;color:var(--action);margin:0}.intro{max-width:950px}.intro p{margin:12px 0}.actions{display:flex;align-items:center;gap:24px;margin:28px 0 44px;flex-wrap:wrap}.button,button{border:0;border-radius:4px;background:var(--action);color:#fff;padding:11px 22px;min-height:44px;display:inline-flex;justify-content:center;align-items:center;font:inherit;font-size:14px;cursor:pointer}.button:hover,button:hover{background:#194650}.secondary{color:var(--action);background:transparent;border:1px solid var(--line)}.secondary:hover{background:var(--tint)}.brief{display:grid;grid-template-columns:220px minmax(0,1fr);border:1px solid var(--line);background:var(--paper);margin:0 0 56px;border-radius:6px;overflow:hidden}.brief-index{background:var(--tint);padding:28px 24px}.brief-index>p{font-size:12px;margin:0 0 30px}.brief-index ol{padding:0;list-style:none;font-size:14px;display:grid;gap:20px;color:var(--muted)}.brief-index li:first-child{color:var(--action);font-weight:600}.brief-paper{padding:30px 40px}.brief-label{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line);padding-bottom:16px}.brief-paper h2{font-size:25px;margin:24px 0 12px}.brief-paper p{font-size:14px;margin:10px 0}.brief-paper strong{color:var(--ink)}.brief-question{border-left:3px solid var(--action);padding:4px 0 4px 18px;margin:24px 0}.brief-foot{font-size:12px!important;border-top:1px solid var(--line);padding-top:16px}.features{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:40px;margin:30px 0 48px}.features section{border-top:1px solid var(--line);padding-top:18px}.features span{font-size:12px;color:var(--action)}.features h2{font-size:19px}.features p{font-size:14px}.start-note{border-top:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;gap:24px;padding-top:30px}.start-note h2{margin:0 0 8px}.start-note p{font-size:14px;margin:0}.form{max-width:480px;padding:36px 40px;margin:12px auto 36px;background:var(--paper);border:1px solid var(--line);border-radius:6px}.form h1{font-size:28px;margin:0 0 12px}.form p{font-size:14px}.form label{display:block;margin-top:20px;font-size:14px}.form input,.form select{width:100%;min-height:46px;margin-top:7px;padding:10px 12px;font:inherit;border:1px solid #b8c5cf;border-radius:4px;background:white;color:var(--ink)}.form button{margin-top:24px;width:100%}.form>p:last-child{margin:24px 0 0}.form details{font-size:13px;color:var(--muted);margin:20px 0}.form summary{color:var(--action);cursor:pointer}.success{color:#245c67;background:#edf3f5;padding:12px;border-radius:4px}.error{color:var(--error)!important}.error:empty{display:none}footer{border-top:1px solid var(--line);padding:22px 0 30px;font-size:12px;color:var(--muted)}:focus-visible{outline:3px solid #578b9a;outline-offset:4px}@media(max-width:700px){header,main,footer{width:calc(100% - 36px)}header{min-height:76px;gap:16px}header>a{font-size:16px}header img{width:30px;height:30px}nav{gap:16px}nav a:last-child{display:none}main{padding:36px 0 48px}h1{font-size:30px}.brief{grid-template-columns:1fr}.brief-index{padding:16px 20px}.brief-index>p{margin:0 0 8px}.brief-index ol{display:flex;flex-wrap:wrap;gap:18px;font-size:12px;margin:0}.brief-paper{padding:22px}.brief-paper h2{font-size:21px}.brief-label{font-size:11px;gap:12px}.features{grid-template-columns:1fr;gap:16px}.start-note{display:block}.start-note .button{margin-top:20px}.form{padding:28px 24px}.form h1{font-size:25px}.actions{gap:18px}}\n'

def page(title, content):
    return HTMLResponse('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" type="image/svg+xml" href="/brand/icon.svg?v=20261103-brand1"><link rel="alternate icon" href="/favicon.ico?v=20261103-brand1"><link rel="apple-touch-icon" href="/brand/icon-180.png"><title>'+html.escape(title)+' · 投研笔记</title><style>'+STYLE+'</style><header><a href="/" aria-label="投研笔记首页" style="display:inline-flex;align-items:center;gap:10px;white-space:nowrap;font-weight:600"><img src="/brand/icon.svg?v=20261103-brand1" width="34" height="34" alt="">投研笔记</a><nav><a href="/login">登录</a><a href="/register">注册</a><a href="https://podnotes.cloud/">个人主页</a></nav></header><main>'+content+'</main><footer>研究有依据，判断有边界。分析结果仅供研究参考，不构成投资建议。</footer></html>',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})

@router.get('/')
def landing():
    return page('A 股研究','<section class="intro"><p class="eyebrow">投研笔记 · A 股信息研究</p><h1>从市场线索，走向有依据的判断。</h1><p>整理财经快讯、行业资金与行情信息，让每次研究都从一个具体问题开始。</p><div class="actions"><a class="button" href="/register">建立研究笔记 →</a><a href="#sample">先读一份示例 ↓</a></div></section>\n<section class="brief" id="sample" aria-label="研究笔记示例"><aside class="brief-index"><p>笔记目录 · 示例</p><ol><li>01\u3000研究问题</li><li>02\u3000信息线索</li><li>03\u3000待核实事项</li></ol></aside><article class="brief-paper"><div class="brief-label"><span>市场观察笔记</span><span>结构示例 · 非实时报告</span></div><h2>一则行业新闻，值得继续研究吗？</h2><p>先梳理事件，再讨论影响，把事实与推测分开记录。</p><div class="brief-question"><p><strong>研究问题</strong><br>这次政策变化，可能通过哪些路径影响行业需求？</p></div><p><strong>信息线索</strong>\u3000梳理政策原文、行业新闻和资金表现。</p><p><strong>待核实事项</strong>\u3000关注实施时间、适用范围与实际落地情况。</p><p class="brief-foot">示例仅展示笔记组织方式，真实分析取决于接口可获取的数据。</p></article></section>\n<h2>让研究过程，有章可循。</h2><div class="features"><section><span>01 · 找线索</span><h2>快速整理财经快讯</h2><p>围绕问题提炼重要事件，减少在零散信息间来回切换。</p></section><section><span>02 · 看变化</span><h2>结合资金与行情观察</h2><p>了解板块资金和部分行情，找到值得进一步核实的方向。</p></section><section><span>03 · 留笔记</span><h2>保留每次研究过程</h2><p>回看任务与分析结果，复制或下载报告，持续补充自己的判断。</p></section></div>\n<section class="start-note"><div><h2>从你关心的问题开始。</h2><p>可免费体验三次 AI 分析，也可在模型设置中填写个人 API Key。</p></div><a class="button" href="/register">开始第一份笔记 →</a></section>\n')


def auth_page(mode, error=''):
    register=mode=='register'
    title='开始你的研究笔记' if register else '欢迎回到投研笔记'
    fields='<label>用户名<input name="name" required minlength="2" maxlength="40" autocomplete="nickname"></label>' if register else ''
    fields+='<label>邮箱<input name="email" type="email" required maxlength="254" autocomplete="email"></label><label>密码<input name="password" type="password" required minlength="10" maxlength="128" autocomplete="'+('new-password' if register else 'current-password')+'"></label>'
    if register:
        fields+='<label>确认密码<input name="confirmation" type="password" required minlength="10" maxlength="128" autocomplete="new-password"></label>'
    return page(title,'<section class="form"><h1>'+title+'</h1><p class="'+('success' if error.startswith('注册成功') else 'error')+'" role="'+('status' if error.startswith('注册成功') else 'alert')+'">'+html.escape(error)+'</p><form method="post" action="/'+mode+'">'+fields+'<button>'+('创建账号' if register else '登录工作台')+' →</button></form><p><a href="/'+('login' if register else 'register')+'">'+('已有账号？立即登录' if register else '还没有账号？免费注册')+'</a></p></section>')

@router.get('/register')
def register_page(): return auth_page('register')

@router.get('/login')
def login_page(): return auth_page('login')

@router.post('/register')
async def register(request:Request):
    values=await form(request);throttle(request)
    email=values.get('email','').strip().lower(); password=values.get('password',''); name=values.get('name','').strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254 or not 2<=len(name)<=40 or not 10<=len(password)<=128 or password!=values.get('confirmation'):
        return auth_page('register','请填写有效邮箱、用户名，以及两次一致的至少10位密码。')
    salt=secrets.token_hex(16)
    try:
        with db() as conn:
            conn.execute('INSERT INTO users(id,email,name,password) VALUES(?,?,?,?)',(secrets.token_hex(16),email,name,salt+':'+digest(password,salt)))
    except sqlite3.IntegrityError:
        return auth_page('register','该邮箱无法注册，请尝试登录或使用其他邮箱。')
    return auth_page('login','注册成功，请使用新账号登录。')

@router.post('/login')
async def login(request:Request):
    values=await form(request);throttle(request)
    with db() as conn:
        row=conn.execute('SELECT * FROM users WHERE email=?',(values.get('email','').strip().lower(),)).fetchone()
        salt,expected=(row['password'].split(':') if row else ('00'*16,'00'*32))
        actual=digest(values.get('password','')[:128],salt)
        if not row or not hmac.compare_digest(actual,expected):
            return auth_page('login','邮箱或密码不正确。')
        token=secrets.token_urlsafe(48)
        conn.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
        conn.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],time.time()+43200))
    response=RedirectResponse('/dashboard',303)
    response.set_cookie(COOKIE,token,max_age=43200,secure=True,httponly=True,samesite='lax',path='/')
    return response

@router.post('/logout')
async def logout(request:Request):
    await form(request)
    with db() as conn:
        conn.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(request.cookies.get(COOKIE,'').encode()).hexdigest(),))
    response=RedirectResponse('/login',303);response.delete_cookie(COOKIE,secure=True,httponly=True,path='/');return response

@router.get('/account')
def account(request:Request):
    try: current=user(request)
    except HTTPException: return RedirectResponse('/login',303)
    status='已配置；留空表示保留原 Key。' if current['key'] else '尚未配置个人 Key，将使用剩余免费体验。'
    from api import LEDGER
    quota=LEDGER.status(current['id'])
    status+=' 免费剩余 '+str(quota['remaining'])+' / 3；处理中 '+str(quota['reserved'])+'。默认百炼 qwen3.7-flash。'
    selected=current['provider'] if current['key'] else 'bailian'
    options=''.join('<option value="'+v+'"'+(' selected' if selected==v else '')+'>'+n+'</option>' for v,n in [('bailian','阿里云百炼（北京）'),('deepseek','DeepSeek'),('openai','OpenAI')])
    return page('模型设置','<section class="form"><h1>模型设置</h1><details><summary>如何配置百炼 API Key</summary><p>前往阿里云百炼控制台，选择北京地域，开通模型按量付费并创建 API Key。确认账户余额及 qwen3.7-flash 权限；将 Key 填入下方密码框。保存时使用个人接口发送极小请求验证，可能产生少量个人接口费用，不扣平台次数。个人 Key 优先，失败不会扣平台免费次数。401 检查 Key，403 检查地域/模型权限，429 检查额度。删除个人 Key 不会恢复已用免费次数。</p></details><p>'+status+'</p><form method="post" action="/account"><label>服务商<select name="provider">'+options+'</select></label><label>API Key<input type="password" name="key" autocomplete="off" maxlength="512" placeholder="输入新 Key，或留空保留"></label><button>保存设置</button></form><form method="post" action="/account/delete-key"><button class="secondary">删除已保存的 Key</button></form><p><a href="/dashboard">返回工作台 →</a></p></section>')

@router.post('/account')
async def save_account(request:Request):
    current=user(request);values=await form(request)
    provider=values.get('provider');key=values.get('key','').strip()
    if provider not in ('bailian','deepseek','openai') or len(key)>512:
        raise HTTPException(400,'模型配置无效')
    if key:
        from llm_policy import validate_personal_key
        from starlette.concurrency import run_in_threadpool
        await run_in_threadpool(validate_personal_key,provider,key)
    with db() as conn:
        if key:
            conn.execute('UPDATE users SET key=?,provider=? WHERE id=?',(BOX.encrypt(key.encode()).decode(),provider,current['id']))
        elif provider!=current['provider']:
            conn.execute('UPDATE users SET key=NULL,provider=? WHERE id=?',(provider,current['id']))
    return RedirectResponse('/account',303)

@router.post('/account/delete-key')
async def delete_key(request:Request):
    current=user(request);await form(request)
    with db() as conn: conn.execute('UPDATE users SET key=NULL WHERE id=?',(current['id'],))
    return RedirectResponse('/account',303)

@router.get('/auth/me')
def me(request:Request):
    current=user(request)
    return {'id':current['id'],'name':current['name'],'configured':bool(current['key'])}

