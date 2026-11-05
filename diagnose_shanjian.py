"""Read-only connectivity/authentication probe; never creates paid video tasks."""
import json
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from mac_launcher import read_config, local_environment
from server import safe_platform_detail
import os


def main():
    config = local_environment(read_config(), 8765)
    key = config.get('SHANJIAN_API_KEY', '')
    if not key:
        print('闪剪API Key未配置，请先运行「配置平台.command」。')
        return
    # Let the same sanitizer redact values loaded from the private local file.
    os.environ['SHANJIAN_API_KEY'] = key
    context = ssl.create_default_context(cafile=config.get('SSL_CERT_FILE') or None)
    print('正在检查闪剪只读资源接口，不会创建视频任务。', flush=True)
    req = Request('https://openapi.shanjian.tv/v1/assets/virtualman/common', headers={'Authorization': 'Bearer ' + key})
    try:
        with urlopen(req, context=context, timeout=20) as response:
            result = json.load(response)
            print('HTTP状态：', response.status)
        print(safe_platform_detail(result) or '平台已响应，未返回可显示的业务诊断信息。')
        print('这里只验证只读接口响应，不代表形象/音色ID、生成权限或资源余额均正确。')
    except HTTPError as exc:
        print('HTTP状态：', exc.code)
        try:
            print(safe_platform_detail(json.loads(exc.read(16384))) or '平台未返回可显示的诊断信息。')
        except Exception:
            print('平台响应无法解析，未显示原始内容以保护密钥。')
    except (URLError, OSError, ValueError):
        print('只读检查失败，请检查网络、代理与Python系统证书配置。未创建视频任务。')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError):
        print('本机配置或证书无法读取，请检查「配置平台.command」及系统证书文件。')
    input('检查完成，按回车关闭窗口…')
