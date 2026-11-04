"""Local content-factory service. Python 3.10+, standard library only."""
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse, quote
from tools_catalog import TOOLS, MANUAL_IDS

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('FACTORY_DB', str(ROOT / 'data/factory.db')))
LOCK = threading.RLock()
TOKEN = secrets.token_urlsafe(32)

class Problem(Exception):
    pass

def remote(method, url, key, body=None, header='Authorization', extra=None):
    headers = {header: ('Bearer ' + key if header == 'Authorization' else key), 'Content-Type': 'application/json'}
    headers.update(extra or {})
    req = Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers, method=method)
    try:
        with urlopen(req, timeout=45) as response:
            return json.load(response)
    except HTTPError as exc:
        # Never expose upstream response bodies: they may contain credentials.
        raise Problem(f'平台接口返回 HTTP {exc.code}，请检查服务端配置或平台控制台') from None
    except Exception:
        raise Problem('平台请求超时或连接失败；请查询平台任务记录后再操作') from None

def init_db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY, job TEXT NOT NULL, account TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(job, account))')
        # In-flight requests cannot safely be replayed after a process crash.
        for table in ('jobs', 'deliveries'):
            for ident, raw in db.execute(f'SELECT id,data FROM {table}').fetchall():
                obj = json.loads(raw)
                if obj['status'] in ('creating', 'sending'):
                    obj.update(status='unknown', error='服务在请求期间中断，请到平台核对；系统不会自动重发')
                    db.execute(f'UPDATE {table} SET data=? WHERE id=?', (json.dumps(obj, ensure_ascii=False), ident))

def rows(table):
    with sqlite3.connect(DB) as db:
        return [json.loads(x[0]) for x in db.execute(f'SELECT data FROM {table} ORDER BY rowid DESC')]

def persist(table, obj):
    with sqlite3.connect(DB) as db:
        raw = json.dumps(obj, ensure_ascii=False)
        if table == 'jobs':
            db.execute('INSERT INTO jobs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (obj['id'], raw))
        else:
            db.execute('INSERT INTO deliveries VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data', (obj['id'], obj['job'], obj['account'], raw))

def get_job(ident):
    item = next((j for j in rows('jobs') if j['id'] == ident), None)
    if not item:
        raise Problem('任务不存在')
    return item

def https_url(value):
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password:
        raise Problem('视频地址必须为 HTTPS 地址')
    return value

def accounts():
    raw = os.environ.get('PUBLISH_ACCOUNTS', '[]')
    try:
        items = json.loads(raw)
        assert isinstance(items, list)
        assert len({x['id'] for x in items}) == len(items)
        assert all(isinstance(x['id'], str) and x['id'] and x['platform'] in ('dy', 'xhs', 'sph') and x['name'] for x in items)
        return items
    except Exception:
        raise Problem('服务端 PUBLISH_ACCOUNTS 配置无效') from None

def provider_ready(provider):
    if provider in MANUAL_IDS:
        return True
    if provider == 'shanjian':
        return all(os.environ.get(k) for k in ('SHANJIAN_API_KEY', 'SHANJIAN_AVATAR_ID', 'SHANJIAN_SPEAKER_ID', 'AIGC_CONTENT_PRODUCER'))
    if provider == 'domestic':
        return bool(os.environ.get('AVATAR_GATEWAY_URL') and os.environ.get('AVATAR_GATEWAY_TOKEN'))
    if provider == 'heygen':
        return bool(os.environ.get('HEYGEN_API_KEY') and os.environ.get('HEYGEN_AVATAR_ID') and os.environ.get('HEYGEN_VOICE_ID'))
    if provider == 'wan':
        return bool(os.environ.get('DASHSCOPE_API_KEY'))
    return False

def create_job(data):
    provider = data.get('provider')
    if not provider_ready(provider):
        raise Problem('制作平台尚未配置，请先配置服务端 API 密钥及形象/音色')
    title = str(data.get('title', '')).strip()
    script = str(data.get('script', '')).strip()
    if not title or not script or len(title) > 200 or len(script) > 5000:
        raise Problem('请填写标题和制作稿（标题 ≤200 字，制作稿 ≤5000 字）')
    if provider == 'shanjian' and not 3 <= len(script) <= 3600:
        raise Problem('闪剪数字人口播稿需为 3–3600 字符')
    job = dict(id=uuid.uuid4().hex, title=title, script=script, provider=provider,
               source=str(data.get('source', ''))[:200], status='creating', created=time.time(), video_url='', review=None)
    if provider in MANUAL_IDS:
        job['status'] = 'awaiting_upload'
        job['production_mode'] = 'manual'
        job['srt'] = str(data.get('srt', ''))[:20000]
        persist('jobs', job)
        return job
    persist('jobs', job)
    try:
        if provider == 'shanjian':
            result = remote('POST', 'https://openapi.shanjian.tv/v1/virtualman/video', os.environ['SHANJIAN_API_KEY'], {
                'virtualmanId': os.environ['SHANJIAN_AVATAR_ID'], 'speakerId': os.environ['SHANJIAN_SPEAKER_ID'],
                'text': script, 'speakerExtra': {'speedRatio': 1, 'language': 'zh-CN'},
                'metadata': {'AIGC': json.dumps({'Label': '1', 'ContentProducer': os.environ['AIGC_CONTENT_PRODUCER'], 'ProduceID': job['id']}, ensure_ascii=False)}})
            ident = (result.get('data') or {}).get('taskId')
        elif provider == 'domestic':
            base = https_url(os.environ['AVATAR_GATEWAY_URL'].rstrip('/'))
            result = remote('POST', base + '/videos', os.environ['AVATAR_GATEWAY_TOKEN'], {
                'script': script, 'title': title, 'aspect_ratio': '9:16', 'ai_generated': True,
                'avatar_id': os.environ.get('AVATAR_ID', ''), 'voice_id': os.environ.get('AVATAR_VOICE_ID', ''),
                'idempotency_key': job['id']}, extra={'Idempotency-Key': job['id']})
            ident = result.get('task_id')
        elif provider == 'heygen':
            result = remote('POST', 'https://api.heygen.com/v2/video/generate', os.environ['HEYGEN_API_KEY'], {
                'video_inputs': [{'character': {'type': 'avatar', 'avatar_id': os.environ['HEYGEN_AVATAR_ID'], 'avatar_style': 'normal'},
                                  'voice': {'type': 'text', 'input_text': script, 'voice_id': os.environ['HEYGEN_VOICE_ID']}}],
                'dimension': {'width': 720, 'height': 1280}}, 'X-Api-Key')
            ident = (result.get('data') or {}).get('video_id')
        else:
            result = remote('POST', 'https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis', os.environ['DASHSCOPE_API_KEY'], {
                'model': 'wan2.1-t2v-turbo', 'input': {'prompt': script},
                'parameters': {'size': '720*1280', 'duration': 5}}, extra={'X-DashScope-Async': 'enable'})
            ident = (result.get('output') or {}).get('task_id')
        if not ident:
            job.update(status='unknown', error='平台未返回任务编号，请到平台核对后处理')
        else:
            job.update(status='processing', remote_id=ident)
    except Problem as exc:
        job.update(status='unknown', error=str(exc))
    persist('jobs', job)
    return job

def refresh_job(ident):
    job = get_job(ident)
    if job['status'] != 'processing':
        return job
    if job['provider'] == 'shanjian':
        result = remote('GET', 'https://openapi.shanjian.tv/v1/task/info?taskId=' + quote(job['remote_id'], safe=''), os.environ['SHANJIAN_API_KEY'])
        out = result.get('data') or {}
        status, url = out.get('status'), (out.get('result') or {}).get('videoUrl')
        done, failed = status == 'succeed', status == 'failed'
    elif job['provider'] == 'domestic':
        base = https_url(os.environ['AVATAR_GATEWAY_URL'].rstrip('/'))
        out = remote('GET', base + '/videos/' + quote(job['remote_id'], safe=''), os.environ['AVATAR_GATEWAY_TOKEN'])
        status, url = out.get('status'), out.get('video_url')
        done, failed = status == 'completed', status == 'failed'
    elif job['provider'] == 'heygen':
        result = remote('GET', 'https://api.heygen.com/v1/video_status.get?video_id=' + quote(job['remote_id'], safe=''), os.environ['HEYGEN_API_KEY'], header='X-Api-Key')
        out = result.get('data') or {}
        status = out.get('status')
        url = out.get('video_url')
        done, failed = status == 'completed', status == 'failed'
    else:
        result = remote('GET', 'https://dashscope.aliyuncs.com/api/v1/tasks/' + quote(job['remote_id'], safe=''), os.environ['DASHSCOPE_API_KEY'])
        out = result.get('output') or {}
        status = out.get('task_status')
        url = out.get('video_url')
        done, failed = status == 'SUCCEEDED', status in ('FAILED', 'CANCELED')
    if done and url:
        job.update(status='ready', video_url=https_url(url))
    elif failed:
        job.update(status='failed', error='平台制作失败，请到平台控制台查看详情')
    persist('jobs', job)
    return job

def import_video(ident, data):
    job = get_job(ident)
    if job['status'] != 'awaiting_upload' or job['provider'] not in MANUAL_IDS:
        raise Problem('仅等待手动制作的任务可回传成片；更换视频请新建版本并重新审核')
    url = https_url(str(data.get('video_url', '')).strip())
    if len(url) > 4000:
        raise Problem('视频链接过长')
    job.update(status='ready', video_url=url, review=None)
    persist('jobs', job)
    return job


def review_job(ident, data):
    job = get_job(ident)
    if job['status'] != 'ready':
        raise Problem('仅已完成的成片可审核')
    if any(x['job'] == ident for x in rows('deliveries')):
        raise Problem('该版本已进入分发流程，不能修改审核记录，请新建版本')
    decision = data.get('decision')
    if decision not in ('approved', 'rejected'):
        raise Problem('审核结论无效')
    note = str(data.get('note', '')).strip()[:2000]
    if decision == 'rejected' and not note:
        raise Problem('退回时请填写修改意见')
    if decision == 'approved' and data.get('watched') is not True:
        raise Problem('请先确认已观看成片并检查画面、字幕、声音和 AI 标识')
    job['review'] = dict(decision=decision, note=note, at=time.time())
    persist('jobs', job)
    return job

def gateway():
    base = os.environ.get('PUBLISH_GATEWAY_URL', '').rstrip('/')
    if not base or not os.environ.get('PUBLISH_GATEWAY_TOKEN'):
        raise Problem('未接入发布服务；请配置已获平台授权的发布网关')
    https_url(base)
    return base

def publish(ident, data):
    job = get_job(ident)
    if job['status'] != 'ready' or (job.get('review') or {}).get('decision') != 'approved':
        raise Problem('只有成片人工审核通过后才能分发')
    chosen = data.get('accounts')
    allowed = {a['id']: a for a in accounts()}
    if not isinstance(chosen, list) or not chosen or any(not isinstance(a, str) or a not in allowed for a in chosen):
        raise Problem('请选择有效的已授权账号')
    base = gateway()
    # Persist all targets before the first request, so partial results survive restart.
    existing = {(x['job'], x['account']): x for x in rows('deliveries')}
    targets = []
    for account in dict.fromkeys(chosen):
        if (ident, account) in existing:
            targets.append(existing[(ident, account)])
            continue
        delivery = dict(id=uuid.uuid4().hex, job=ident, account=account, account_name=allowed[account]['name'],
                        platform=allowed[account]['platform'], status='queued', created=time.time())
        persist('deliveries', delivery)
        targets.append(delivery)
    for delivery in targets:
        if delivery['status'] != 'queued':
            continue
        delivery['status'] = 'sending'
        persist('deliveries', delivery)
        try:
            result = remote('POST', base + '/publications', os.environ['PUBLISH_GATEWAY_TOKEN'], {
                'account_id': delivery['account'], 'platform': delivery['platform'], 'video_url': job['video_url'],
                'title': job['title'], 'description': job['script'], 'ai_generated': True,
                'idempotency_key': delivery['id']}, extra={'Idempotency-Key': delivery['id']})
            apply_publication(delivery, result)
        except Problem as exc:
            delivery.update(status='unknown', error=str(exc))
        persist('deliveries', delivery)
    return targets

def apply_publication(delivery, result):
    state = result.get('status')
    ident = result.get('publication_id') or delivery.get('remote_id')
    if state not in ('submitted', 'published', 'failed') or not ident:
        delivery.update(status='unknown', error='发布接口返回不完整，请在发布服务中核实')
        return
    delivery.update(status=state, remote_id=str(ident), error='')
    if result.get('url'):
        delivery['url'] = https_url(result['url'])

def refresh_delivery(ident):
    item = next((x for x in rows('deliveries') if x['id'] == ident), None)
    if not item:
        raise Problem('发布记录不存在')
    if item['status'] not in ('submitted', 'unknown') or not item.get('remote_id'):
        return item
    result = remote('GET', gateway() + '/publications/' + quote(item['remote_id'], safe=''), os.environ['PUBLISH_GATEWAY_TOKEN'])
    apply_publication(item, result)
    persist('deliveries', item)
    return item

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, status, payload, kind='application/json; charset=utf-8'):
        body = json.dumps(payload, ensure_ascii=False).encode() if kind.startswith('application/json') else payload
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
        self.wfile.write(body)

    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')

    def do_GET(self):
        if not self.valid_host():
            return self.respond(403, {'error': '仅支持本机访问'})
        path = urlparse(self.path).path
        if path in ('/', '/index.html', '/factory.js', '/factory.css'):
            name = 'index.html' if path == '/' else path[1:]
            kind = {'html': 'text/html; charset=utf-8', 'js': 'text/javascript; charset=utf-8', 'css': 'text/css; charset=utf-8'}[name.rsplit('.', 1)[1]]
            return self.respond(200, (ROOT / name).read_bytes(), kind)
        if path == '/api/factory/state':
            try:
                with LOCK:
                    return self.respond(200, dict(csrf=TOKEN, jobs=rows('jobs'), deliveries=rows('deliveries'), accounts=accounts(),
                        tools=TOOLS,
                        providers=[dict(id=t['id'], name=t['name'], mode=t['mode'], note=t['note'], ready=provider_ready(t['id'])) for t in TOOLS if t['category'] != '批量分发'],
                        publish_ready=bool(os.environ.get('PUBLISH_GATEWAY_URL') and os.environ.get('PUBLISH_GATEWAY_TOKEN'))))
            except Problem as exc:
                return self.respond(400, {'error': str(exc)})
        self.respond(404, {'error': '接口不存在'})

    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Factory-CSRF') != TOKEN or self.headers.get('Origin') != 'http://' + self.headers.get('Host', ''):
            return self.respond(403, {'error': '请求来源校验失败，请从本机工作台操作'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 65536:
                raise Problem('请求过大')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise Problem('请求格式无效')
            parts = urlparse(self.path).path.strip('/').split('/')
            with LOCK:
                if parts == ['api', 'factory', 'jobs']:
                    result = create_job(data)
                elif len(parts) == 5 and parts[:3] == ['api', 'factory', 'jobs']:
                    ident, action = parts[3:]
                    if action == 'refresh': result = refresh_job(ident)
                    elif action == 'import': result = import_video(ident, data)
                    elif action == 'review': result = review_job(ident, data)
                    elif action == 'publish': result = publish(ident, data)
                    else: raise Problem('接口不存在')
                elif len(parts) == 5 and parts[:3] == ['api', 'factory', 'deliveries'] and parts[4] == 'refresh':
                    result = refresh_delivery(parts[3])
                else:
                    return self.respond(404, {'error': '接口不存在'})
            self.respond(200, result)
        except (Problem, ValueError, KeyError) as exc:
            self.respond(400, {'error': str(exc) if isinstance(exc, Problem) else '请求或服务配置无效'})
        except Exception:
            self.respond(500, {'error': '服务处理失败，请检查本机服务日志和配置'})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('FACTORY_PORT', '8765'))
    print(f'内容工厂已启动：http://127.0.0.1:{port} （仅限本机）', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()
