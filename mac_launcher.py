"""macOS local launcher/configuration. No shell evaluation of configuration."""
import getpass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'data/local-config.json'
FIELDS = [
    ('SHANJIAN_API_KEY', '闪剪 API Key', True),
    ('SHANJIAN_AVATAR_ID', '闪剪数字人形象 ID', False),
    ('SHANJIAN_SPEAKER_ID', '闪剪音色 ID', False),
    ('AIGC_CONTENT_PRODUCER', '内容服务提供者名称', False),
    ('DASHSCOPE_API_KEY', '通义万相 API Key（选填）', True),
    ('PUBLISH_GATEWAY_URL', '授权发布网关 HTTPS 地址（未接入可留空）', False),
    ('PUBLISH_GATEWAY_TOKEN', '授权发布网关令牌（选填）', True),
]

def read_config(path=CONFIG):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        allowed = {x[0] for x in FIELDS}
        if not isinstance(data, dict) or any(k not in allowed or not isinstance(v, str) for k, v in data.items()):
            raise ValueError()
        return data
    except (ValueError, OSError):
        raise RuntimeError('本机配置无法读取，请重新运行「配置平台.command」；不要把配置内容发送到聊天。') from None

def configure():
    data = read_config()
    print('配置仅保存在本机 data/local-config.json。密钥输入时不显示字符，这是正常的。')
    print('直接回车保留原值；输入单个 - 清空。没有接口可全部留空，先体验手动制作流程。')
    for key, label, secret in FIELDS:
        prompt = f'{label}（{"已设置" if data.get(key) else "未设置"}）：'
        value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
        if value == '-':
            data.pop(key, None)
        elif value:
            data[key] = value
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    import tempfile
    fd, name = tempfile.mkstemp(dir=CONFIG.parent, prefix='.config-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.chmod(name, 0o600)
        os.replace(name, CONFIG)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print('配置已保存。重启内容工厂后生效。发布账号清单目前仍按 README 配置 PUBLISH_ACCOUNTS。')

def local_environment(config, port):
    env = os.environ.copy()
    env.update(config)
    if sys.platform == 'darwin' and not env.get('SSL_CERT_FILE') and Path('/etc/ssl/cert.pem').is_file():
        env['SSL_CERT_FILE'] = '/etc/ssl/cert.pem'
    # Always launch local mode even if a previous server deployment exported these.
    env.update(FACTORY_BIND='127.0.0.1', FACTORY_PORT=str(port), FACTORY_DB=str(ROOT / 'data/factory.db'))
    env.pop('FACTORY_PUBLIC_ORIGIN', None)
    env.pop('FACTORY_PROXY_TOKEN', None)
    return env

def launch():
    import fcntl
    (ROOT / 'data').mkdir(mode=0o700, exist_ok=True)
    with (ROOT / 'data/mac-launcher.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('内容工厂已由另一个启动窗口运行，请回到那个窗口或先将它停止。') from None
        subprocess.run([sys.executable, str(ROOT / 'install.py')], cwd=ROOT, check=True)
        port = None
        for candidate in range(8765, 8776):
            with socket.socket() as probe:
                try:
                    probe.bind(('127.0.0.1', candidate))
                    port = candidate
                    break
                except OSError:
                    continue
        if port is None:
            raise RuntimeError('8765–8775 端口均被占用，请关闭旧的内容工厂后再启动。')
        url = f'http://127.0.0.1:{port}'
        process = subprocess.Popen([sys.executable, str(ROOT / 'server.py')], cwd=ROOT, env=local_environment(read_config(), port))
        try:
            for _ in range(40):
                if process.poll() is not None:
                    raise RuntimeError('服务启动失败，请查看此窗口上方信息。')
                try:
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with opener.open(url + '/api/factory/state', timeout=0.4) as response:
                        state = json.load(response)
                        if not isinstance(state.get('jobs'), list) or not state.get('csrf'):
                            raise ValueError()
                    break
                except (OSError, ValueError):
                    time.sleep(0.2)
            else:
                raise RuntimeError('等待服务启动超时，请查看此窗口信息。')
            print(f'工作台地址：{url}\n进入「新媒体端口 → B7 内容工厂」。\n请保持此终端窗口打开，按 Control+C 停止服务。', flush=True)
            webbrowser.open(url)
            process.wait()
        except KeyboardInterrupt:
            print('\n正在停止内容工厂…')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()

if __name__ == '__main__':
    try:
        if sys.version_info < (3, 10):
            raise RuntimeError('请先安装 Python 3.10 或更高版本。')
        configure() if '--configure' in sys.argv else launch()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        input('按回车关闭窗口…')
        sys.exit(1)
