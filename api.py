"""
DeepInsight FastAPI 服务入口

接口:
    GET  /health            健康检查（无 LLM Key 时也可用）
    POST /analyze           提交分析任务（后台执行，立即返回 task_id）
    GET  /result/{task_id}  查询任务结果

启动:
    uvicorn api:app --host 0.0.0.0 --port 8085
"""

import threading
import uuid
from datetime import datetime
from typing import Dict, Optional

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config

app = FastAPI(
    title="DeepInsight Agent",
    description="实时联网财经情报分析服务",
    version="1.0.0",
)

# ==========================================
# 任务存储（内存版，单实例部署）
# ==========================================
_TASK_STORE: Dict[str, dict] = {}
_TASK_LOCK = threading.Lock()

# 全局引擎（延迟初始化属性保证无 Key 时也可导入）
_engine = None


def get_engine():
    """获取全局引擎单例（首次调用时创建）"""
    global _engine
    if _engine is None:
        from main import DeepInsightEngine

        _engine = DeepInsightEngine()
    return _engine


def _run_task(task_id: str, query: str, user_id: str):
    """后台线程执行分析任务"""
    try:
        engine = get_engine()
        result = engine.chat(query, user_id)
        with _TASK_LOCK:
            _TASK_STORE[task_id].update(
                status="completed",
                result=result,
                finished_at=datetime.now().isoformat(),
            )
    except Exception as exc:  # noqa: BLE001
        with _TASK_LOCK:
            _TASK_STORE[task_id].update(
                status="failed",
                error=str(exc),
                finished_at=datetime.now().isoformat(),
            )


# ==========================================
# 请求/响应模型
# ==========================================
class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="用户分析请求")
    user_id: str = Field(default="api_user", description="用户标识")


class AnalyzeResponse(BaseModel):
    task_id: str
    status: str
    created_at: str


# ==========================================
# 接口
# ==========================================
@app.get("/health")
def health_check():
    """健康检查：无 OPENAI_API_KEY 时仍返回 200，并标注 LLM 不可用"""
    llm_available = bool(config.OPENAI_API_KEY)
    return {
        "status": "ok",
        "service": "deepinsight-agent",
        "llm_available": llm_available,
        "model": config.MODEL_NAME if llm_available else None,
        "langfuse_enabled": bool(
            config.LANGFUSE_ENABLED
            and config.LANGFUSE_SECRET_KEY
            and config.LANGFUSE_PUBLIC_KEY
        ),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    """提交分析任务（后台异步执行）"""
    # 无 Key 时给出明确报错（503），而非硬编码默认值静默降级
    if not config.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="服务未配置 OPENAI_API_KEY，LLM 分析不可用。请在环境变量中设置后重启服务。",
        )

    task_id = uuid.uuid4().hex
    now = datetime.now().isoformat()
    with _TASK_LOCK:
        _TASK_STORE[task_id] = {
            "task_id": task_id,
            "status": "running",
            "query": req.query,
            "user_id": req.user_id,
            "created_at": now,
        }

    threading.Thread(
        target=_run_task,
        args=(task_id, req.query, req.user_id),
        daemon=True,
    ).start()

    return AnalyzeResponse(task_id=task_id, status="running", created_at=now)


@app.get("/result/{task_id}")
def get_result(task_id: str):
    """查询任务结果"""
    with _TASK_LOCK:
        task = _TASK_STORE.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        resp = {
            "task_id": task["task_id"],
            "status": task["status"],
            "created_at": task["created_at"],
        }
        if task["status"] == "completed":
            resp["result"] = task.get("result")
        elif task["status"] == "failed":
            resp["error"] = task.get("error")
        resp["finished_at"] = task.get("finished_at")
        return resp


# ==========================================
# Landing Page（根路径静态页，零依赖零构建）
# 挂载在既有路由之后，不影响 /health /analyze /result /docs
# ==========================================
_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="landing")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8085)