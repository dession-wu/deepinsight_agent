// Only digests and opaque operation IDs remain in memory; never persist manuscripts.
function createOperationFetch(fetcher = (...args) => globalThis.fetch(...args), cryptoApi = globalThis.crypto) {
  const pending = new Map();
  return async function operationFetch(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'POST' || !/\/(novels(?:\/|$)|analyze(?:\?|$))/.test(String(url))) return fetcher(url, options);
    const headers = new Headers(options.headers || {});
    const bytes = new TextEncoder().encode(method+'\n'+url+'\n'+(headers.get('Authorization') || '')+'\n'+(options.body || ''));
    const hash = [...new Uint8Array(await cryptoApi.subtle.digest('SHA-256', bytes))].map(n=>n.toString(16).padStart(2,'0')).join('');
    let id = pending.get(hash);
    if (!id) { id = cryptoApi.randomUUID(); pending.set(hash, id); }
    headers.set('Idempotency-Key', id);
    const response = await fetcher(url, {...options, headers});
    if (!response.ok || !response.body) return response;
    // Keep the ID until the body finishes: headers alone do not prove stream success.
    const reader = response.body.getReader();
    const decoder = new TextDecoder(); let tail = ''; let failed = false;
    const body = new ReadableStream({
      async pull(controller) {
        try {
          const chunk = await reader.read();
          if (chunk.done) { if (!failed && pending.get(hash) === id) pending.delete(hash); controller.close(); return; }
          tail = (tail + decoder.decode(chunk.value, {stream:true})).slice(-8192);
          if (/"error"\s*:/.test(tail)) failed = true;
          controller.enqueue(chunk.value);
        } catch (error) { controller.error(error); }
      },
      cancel(reason) { return reader.cancel(reason); }
    });
    return new Response(body, {status:response.status,statusText:response.statusText,headers:response.headers});
  };
}
const aiFetch = createOperationFetch();

/* Dependency-free UI for the existing asynchronous analysis API. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const STORAGE_KEY = 'deepinsight.history.v2.' + document.querySelector('meta[name=account-id]').content;
  const topics = {
    news: ['整理财联社最新财经新闻，概括重点事件与值得关注的影响。', '财联社最新快讯有哪些重点？', '整理最新财经新闻中的政策变化'],
    capital: ['分析东方财富行业资金流向，列出值得进一步关注的板块与不确定性。', '哪些行业主力资金净流入较多？请分析行业资金流向', '结合行情与资金流向，整理板块观察线索'],
    market: ['整理 A股行情 快照，概括接口返回的个股表现，并说明数据覆盖范围与局限。', '整理当前 A股行情 快照的主要表现', '结合财经新闻与行情，概括市场关注点']
  };
  const labels = { workspace: '新建分析', history: '我的历史', guide: '使用指南' };
  const sourceInstructions = {
    news: '请结合财联社最新财经快讯回答。',
    capital: '请结合东方财富行业资金流向和行情回答。',
    market: '请结合东方财富 A股行情 快照回答，并说明仅覆盖接口返回的部分个股。'
  };
  let history = [];
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
    if (Array.isArray(saved)) history = saved.filter((x) => x && typeof x.id === 'string' && typeof x.query === 'string' && typeof x.created === 'string' && ['running', 'completed', 'failed'].includes(x.status) && (x.result == null || typeof x.result === 'string')).slice(0, 15);
  } catch (_) { /* Local storage is optional. */ }
  let selectedTopic = 'news';
  let activeTask = null;
  let busy = false;
  let timer;
  let pollVersion = 0;
  let healthState = 'unknown';
  let healthChecking = false;

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(history)); }
    catch (_) { $('action-message').textContent = '浏览器未能保存记录，请下载分析以保留。'; }
    $('history-count').textContent = history.length;
    if (!$('history-view').hidden) renderHistory();
  }
  function showView(name) {
    for (const key of Object.keys(labels)) $(key + '-view').hidden = key !== name;
    document.querySelectorAll('.nav-item').forEach((el) => {
      const active = el.dataset.view === name;
      el.classList.toggle('active', active);
      if (active) el.setAttribute('aria-current', 'page'); else el.removeAttribute('aria-current');
    });
    $('page-name').textContent = labels[name];
    if (name === 'history') renderHistory();
    window.scrollTo({ top: 0, behavior: 'instant' });
  }
  document.querySelectorAll('[data-view]').forEach((el) => el.addEventListener('click', () => {
    if (el.dataset.view === 'workspace' && !busy) {
      stopPolling(); activeTask = null; $('task-panel').hidden = true; $('query').value = ''; updateCount();
    }
    showView(el.dataset.view);
  }));
  function updateCount() { $('char-count').textContent = $('query').value.length; }
  function setTopic(name) {
    selectedTopic = name;
    document.querySelectorAll('.topic').forEach((el) => {
      const selected = el.dataset.topic === name;
      el.classList.toggle('active', selected);
      el.setAttribute('aria-pressed', String(selected));
    });
    $('query').placeholder = '例如：' + topics[name][0];
    $('example-list').replaceChildren();
    topics[name].slice(1).forEach((query) => {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'example'; button.textContent = query;
      button.addEventListener('click', () => { if (busy) return; $('query').value = query; updateCount(); $('query').focus(); });
      $('example-list').append(button);
    });
  }
  document.querySelectorAll('.topic').forEach((el) => el.addEventListener('click', () => setTopic(el.dataset.topic)));
  $('query').addEventListener('input', updateCount);
  async function request(url, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await aiFetch(url, { ...options, signal: controller.signal });
      let data;
      try { data = await response.json(); } catch (_) { throw new Error('服务返回了无法识别的内容，请稍后重试。'); }
      if (response.status === 401) { window.location.assign("/login"); throw new Error("登录已过期，请重新登录。"); }
      if (!response.ok) {
        const message = response.status === 404 ? '该任务已不存在，可能由于服务重启。请重新提交问题。' : response.status === 503 ? '分析服务暂不可用，请联系管理员检查模型配置。' : '请求失败，请稍后重试。';
        const error = new Error(message); error.status = response.status; throw error;
      }
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('连接超时，请检查网络后重试。');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  async function checkHealth() {
    if (healthChecking) return;
    healthChecking = true;
    try {
      const health = await request('/health');
      healthState = health.status === 'ok' && health.llm_available ? 'ready' : 'unavailable';
      $('health-text').textContent = healthState === 'ready' ? '服务已连接' : '分析服务未就绪';
      $('service-message').textContent = '请检查模型设置中的免费剩余额度与服务配置；免费用尽后填写自己的百炼 API Key。';
      $('service-message').hidden = healthState === 'ready';
    } catch (_) {
      healthState = 'unknown';
      $('health-text').textContent = '服务连接待确认';
      $('service-message').textContent = '暂时无法确认服务状态。你仍可尝试提交问题，或点击右上角重新检查。';
      $('service-message').hidden = false;
    } finally {
      $('health-check').dataset.state = healthState;
      healthChecking = false;
    }
  }
  // Render basic Markdown through DOM nodes, never model-generated HTML.
  function inline(node, text) {
    text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).forEach((part) => {
      if (part.startsWith('**') && part.endsWith('**')) { const strong = document.createElement('strong'); strong.textContent = part.slice(2, -2); node.append(strong); }
      else if (part.startsWith('`') && part.endsWith('`')) { const code = document.createElement('code'); code.textContent = part.slice(1, -1); node.append(code); }
      else node.append(document.createTextNode(part));
    });
  }
  function renderReport(text) {
    $('report').replaceChildren();
    let paragraph = [], list = null, code = null;
    function flush() {
      if (paragraph.length) { const p = document.createElement('p'); inline(p, paragraph.join('\n')); $('report').append(p); paragraph = []; }
    }
    String(text).split('\n').forEach((line) => {
      if (/^\s*```/.test(line)) { flush(); list = null; if (code) code = null; else { code = document.createElement('pre'); $('report').append(code); } return; }
      if (code) { code.textContent += line + '\n'; return; }
      const heading = line.match(/^\s*(#{1,6})\s+(.+)/);
      const bullet = line.match(/^\s*(?:[-*•]|\d+[.)、])\s+(.+)/);
      if (heading) { flush(); list = null; const h = document.createElement(heading[1].length < 3 ? 'h3' : 'h4'); inline(h, heading[2]); $('report').append(h); }
      else if (bullet) {
        flush(); const kind = /^\s*\d/.test(line) ? 'ol' : 'ul';
        if (!list || list.tagName.toLowerCase() !== kind) { list = document.createElement(kind); $('report').append(list); }
        const li = document.createElement('li'); inline(li, bullet[1]); list.append(li);
      } else if (!line.trim()) { flush(); list = null; }
      else { list = null; paragraph.push(line); }
    });
    flush();
  }
  function formatDate(date) { const d = new Date(date); return Number.isNaN(d.getTime()) ? '时间未知' : d.toLocaleString('zh-CN', { hour12: false }); }
  function setBusy(value) {
    busy = value; $('submit-button').disabled = value;
    $('submit-button').textContent = value ? '正在分析…' : '开始分析 →';
    $('query').readOnly = value;
    document.querySelectorAll('.topic, .example').forEach((el) => { el.disabled = value; });
  }
  function renderTask(task) {
    $('task-panel').hidden = false;
    $('task-title').textContent = task.query;
    $('task-label').textContent = '提交于 ' + formatDate(task.created);
    $('task-state').textContent = { running: '处理中', completed: '已完成', failed: '未完成' }[task.status];
    $('task-feedback').dataset.state = task.status;
    $('task-feedback').hidden = task.status === 'completed';
    $('task-feedback').textContent = task.status === 'running' ? '请求已提交，正在等待分析结果。当前服务仅返回整体状态，页面会自动查询，请稍候。' : task.error || '分析未完成，请稍后重新提交。';
    const complete = task.status === 'completed';
    $('report').hidden = !complete; $('report-caveat').hidden = !complete;
    $('copy-result').hidden = !complete; $('download-result').hidden = !complete;
    $('check-result').hidden = true; $('action-message').textContent = '';
    if (complete) renderReport(task.result || '服务未返回分析内容。');
  }
  function stopPolling() { clearTimeout(timer); pollVersion++; }
  async function poll(task, version, started = Date.now()) {
    try {
      const data = await request('/result/' + encodeURIComponent(task.id));
      if (version !== pollVersion) return;
      if (data.status === 'running') {
        if (Date.now() - started > 300000) {
          $('task-feedback').textContent = '任务等待时间较长，已暂停自动查询。可以稍后继续查询，无需重复提交。';
          $('check-result').hidden = false; setBusy(false); return;
        }
        timer = setTimeout(() => poll(task, version, started), 2500); return;
      }
      if (!['completed', 'failed'].includes(data.status)) throw new Error('无法识别任务状态，请稍后继续查询。');
      const result = typeof data.result === 'string' ? data.result : '';
      // The current engine can return an error string in a completed task.
      const engineError = /^\s*❌/.test(result);
      task.status = engineError || data.status === 'failed' || !result.trim() ? 'failed' : 'completed';
      task.result = task.status === 'completed' ? result : '';
      task.error = engineError ? '分析引擎未能完成请求，请联系管理员检查模型或网络配置。' : data.status === 'failed' ? '分析执行失败，请稍后重试，或联系管理员检查服务。' : !result.trim() ? '服务没有返回分析内容，请稍后重试。' : '';
      renderTask(task); save(); setBusy(false);
    } catch (error) {
      if (version !== pollVersion) return;
      if (error.status === 404) { task.status = 'failed'; task.error = error.message; renderTask(task); save(); }
      else { $('task-feedback').textContent = '查询暂时中断。' + error.message + ' 可继续查询已提交的任务。'; $('check-result').hidden = false; }
      setBusy(false);
    }
  }
  $('analysis-form').addEventListener('submit', async (event) => {
    event.preventDefault(); if (busy) return;
    const query = $('query').value.trim();
    if (!query) { $('query').setCustomValidity('请先描述你的分析问题，或选择下方示例。'); $('query').reportValidity(); return; }
    $('query').setCustomValidity('');
    if (healthState === 'unavailable') { $('service-message').hidden = false; return; }
    stopPolling(); setBusy(true);
    const version = pollVersion;
    const task = { id: '', query, created: new Date().toISOString(), status: 'running', topic: selectedTopic };
    activeTask = task;
    renderTask(task); $('task-feedback').textContent = '正在提交你的问题…';
    $('task-panel').scrollIntoView({ block: 'nearest' });
    try {
      const apiQuery = query + '\n\n' + sourceInstructions[task.topic] + '请按重点摘要、信息解读、风险与待核实问题组织回答。没有数据支持时请明确说明，不要虚构数据来源或验证结果。';
      const data = await request('/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: apiQuery, user_id: 'web_user' }) });
      if (typeof data.task_id !== 'string' || !data.task_id) throw new Error('服务未返回有效任务编号，请稍后重试。');
      task.id = data.task_id; task.created = data.created_at || task.created;
      history.unshift(task); history = history.slice(0, 15); save();
      if (version !== pollVersion) return;
      renderTask(task); poll(task, version);
    } catch (error) {
      if (version !== pollVersion) return;
      task.status = 'failed'; task.error = error.message + ' 若提交期间连接中断，服务器可能仍在处理；当前无法恢复未返回编号的任务。';
      renderTask(task); setBusy(false);
    }
  });
  $('query').addEventListener('input', () => $('query').setCustomValidity(''));
  $('check-result').addEventListener('click', () => {
    if (!activeTask || !activeTask.id) return;
    stopPolling(); setBusy(true); renderTask(activeTask); poll(activeTask, pollVersion);
  });
  function openTask(task) {
    stopPolling(); activeTask = task; showView('workspace'); renderTask(task);
    if (Object.hasOwn(topics, task.topic)) setTopic(task.topic);
    $('query').value = task.query; updateCount();
    setBusy(task.status === 'running');
    if (task.status === 'running') poll(task, pollVersion);
    $('task-panel').scrollIntoView({ block: 'start' });
  }
  function renderHistory() {
    $('history-list').replaceChildren();
    if (!history.length) {
      const empty = document.createElement('div'); empty.className = 'empty-state';
      const heading = document.createElement('h2'); heading.textContent = '从第一个问题开始';
      const p = document.createElement('p'); p.textContent = '提交一次分析后，你的记录会出现在这里。';
      const button = document.createElement('button'); button.className = 'primary-button'; button.textContent = '新建分析'; button.addEventListener('click', () => { showView('workspace'); $('query').focus(); });
      empty.append(heading, p, button); $('history-list').append(empty); return;
    }
    history.forEach((task) => {
      const button = document.createElement('button'); button.className = 'history-row';
      const info = document.createElement('div'); const title = document.createElement('strong'); title.textContent = task.query;
      const time = document.createElement('small'); time.textContent = formatDate(task.created);
      const status = document.createElement('span'); status.className = 'state-badge'; status.textContent = { running: '待查询', completed: '已完成', failed: '未完成' }[task.status];
      info.append(title, time); button.append(info, status); button.addEventListener('click', () => openTask(task)); $('history-list').append(button);
    });
  }
  $('copy-result').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(activeTask.query + '\n\n' + activeTask.result); $('action-message').textContent = '已复制全文'; }
    catch (_) { $('action-message').textContent = '无法访问剪贴板，请选择文字复制或下载分析。'; }
  });
  $('download-result').addEventListener('click', () => {
    const blob = new Blob([activeTask.query + '\n' + formatDate(activeTask.created) + '\n\n' + activeTask.result + '\n\n' + $('report-caveat').textContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'DeepInsight-' + activeTask.id.slice(0, 8) + '.txt'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('action-message').textContent = '已生成下载文件';
  });
  $('health-check').addEventListener('click', checkHealth);
  $('history-count').textContent = history.length;
  setTopic('news'); checkHealth();
})();
