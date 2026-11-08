"""Project-local atomic operations. No credential values are persisted here."""
import os, sqlite3, hashlib, json
from pathlib import Path
from contextvars import ContextVar
from contextlib import contextmanager
from fastapi import HTTPException
SCOPE=ContextVar('llm_operation',default=None)
ENDPOINTS={'bailian':('https://dashscope.aliyuncs.com/compatible-mode/v1','qwen3.7-flash'),'deepseek':('https://api.deepseek.com','deepseek-chat'),'openai':('https://api.openai.com/v1','gpt-4o-mini')}

def operator_key():
    key=os.environ.get('BAILIAN_API_KEY','').strip()
    if key:return key
    name=os.environ.get('BAILIAN_API_KEY_FILE')
    if not name and os.name=='nt':
        default=Path(r'E:\podnotes\podnotes-server\config\ops-secrets\bailian-secret.bin')
        if default.is_file():name=str(default)
    if not name:return None
    if os.name!='nt':
        try:return Path(name).read_text().strip()
        except (OSError,UnicodeError):raise HTTPException(503,'运营模型密钥暂不可用，请稍后重试或使用个人 Key。') from None
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    try:raw=Path(name).read_bytes()
    except OSError:raise HTTPException(503,'运营模型密钥暂不可用，请稍后重试或使用个人 Key。') from None
    buf=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw);src=Blob(len(raw),buf);out=Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(src),None,None,None,None,0,ctypes.byref(out)):
        raise HTTPException(503,'运营模型密钥无法解密')
    try:return ctypes.string_at(out.pbData,out.cbData).decode().strip()
    finally:ctypes.windll.kernel32.LocalFree(out.pbData)

def process_alive(pid):
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return ctypes.get_last_error()!=87  # Access denied means unknown/live.
        try:
            code=wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0);return True
    except ProcessLookupError:return False
    except (PermissionError,OSError):return True

class Ledger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:c.execute('CREATE TABLE IF NOT EXISTS operations(owner TEXT,id TEXT,fingerprint TEXT,state TEXT,pid INTEGER,response TEXT, PRIMARY KEY(owner,id))')
    @contextmanager
    def connect(self):
        conn=sqlite3.connect(self.path,timeout=30)
        try:
            with conn:yield conn
        finally:conn.close()
    def recover(self):
        # Never release live workers simply because a second worker starts.
        with self.connect() as c:
            for pid, in c.execute("SELECT DISTINCT pid FROM operations WHERE state='reserved'"):
                if not process_alive(pid):c.execute("UPDATE operations SET state='failed' WHERE state='reserved' AND pid=?",(pid,))
    def status(self,owner):
        with self.connect() as c:
            used=c.execute("SELECT count(*) FROM operations WHERE owner=? AND state='succeeded'",(str(owner),)).fetchone()[0]
            pending=c.execute("SELECT count(*) FROM operations WHERE owner=? AND state='reserved'",(str(owner),)).fetchone()[0]
        return {'used':used,'reserved':pending,'remaining':max(0,3-used-pending),'model':'qwen3.7-flash'}
    def reserve(self,owner,operation,fingerprint):
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT fingerprint,state,response FROM operations WHERE owner=? AND id=?',(str(owner),operation)).fetchone()
            if old:
                if old[0]!=fingerprint:raise HTTPException(409,'操作编号与请求不匹配')
                if old[1]=='succeeded':return old[2]
                if old[1]=='reserved':raise HTTPException(409,'操作正在处理中')
            count=c.execute("SELECT count(*) FROM operations WHERE owner=? AND state IN ('reserved','succeeded')",(str(owner),)).fetchone()[0]
            if count>=3:raise HTTPException(409,{'code':'quota_exhausted','message':'三次免费体验已用尽，请配置自己的百炼 API Key。'})
            c.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?,?,NULL)',(str(owner),operation,fingerprint,'reserved',os.getpid()))
        return None
    def finish(self,owner,operation,success,response=None):
        with self.connect() as c:c.execute("UPDATE operations SET state=?,response=? WHERE owner=? AND id=? AND state='reserved'",('succeeded' if success else 'failed',response,str(owner),operation))

def scoped_credentials(personal,ledger):
    scope=SCOPE.get()
    if not scope or not scope.get('owner'):raise HTTPException(401,'请登录后使用 AI')
    if personal:return personal
    if scope.get('credentials'):return scope['credentials']
    key=operator_key()
    if not key:raise HTTPException(503,'运营模型尚未配置；可在设置中配置个人百炼 Key。')
    replay=ledger.reserve(scope['owner'],scope['id'],scope['fingerprint'])
    if replay is not None:raise HTTPException(409,'此操作已完成，请查看已保存结果。')
    scope['reserved']=True
    scope['credentials']=('bailian',key)
    return scope['credentials']


def validate_personal_key(provider,key):
    """A tiny personal-key request: no operator fallback or platform reservation."""
    if provider not in ENDPOINTS:raise HTTPException(422,'服务商不受支持')
    try:
        from openai import OpenAI
        endpoint,model=ENDPOINTS[provider]
        with OpenAI(api_key=key,base_url=endpoint,timeout=20,max_retries=0) as client:
            result=client.chat.completions.create(model=model,messages=[{'role':'user','content':'Reply OK'}],max_tokens=8,extra_body={'enable_thinking':False} if provider=='bailian' else {})
            if not result.choices or not result.choices[0].message.content:raise ValueError('empty')
    except Exception:
        raise HTTPException(422,'个人 Key 验证失败，请检查地域、模型权限、余额与网络。此验证仅使用个人接口额度，不扣平台免费次数。') from None
