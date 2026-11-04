"""Tool routes; availability is explicit, never inferred from a marketing feature."""
TOOLS = [
    dict(id='shanjian', name='闪剪', category='数字人', mode='api', url='https://www.shanjian.tv/', note='官方数字人口播 API（无包装）；需开通资源包、形象与音色，按实际用量计费。', docs='https://openapi-doc.shanjian.tv/342245572e0'),
    dict(id='zenvideo', name='腾讯智影', category='数字人', mode='manual', url='https://zenvideo.qq.com/', note='当前按网页制作接入；导出制作包，在工具中完成后回传成片。未核实与你账号匹配的公开生成接口。'),
    dict(id='xiaoyunque', name='剪映·小云雀', category='数字人 / AI视频', mode='manual', url='https://xyq.jianying.com/', note='当前按网页制作接入；不把视频模型 API 等同于网页数字人能力。', docs='https://xyq.jianying.com/tutorials/web-manual'),
    dict(id='jimeng', name='即梦', category='AI视频 / 数字人', mode='manual', url='https://jimeng.jianying.com/', note='已找到火山引擎即梦视频官方 API；本版本尚未适配其签名和模型。先用制作包回传流程，不宣称数字人接口已接通。', docs='https://docs.volcengine.com/docs/jimeng-ai/jimeng-ai-video-generation-30-pro-interface-documentation?lang=zh'),
    dict(id='kling', name='可灵 Kling', category='AI视频', mode='manual', url='https://klingai.com/', note='当前先走制作包与成片回传；开放平台权限及接口适配待核实。'),
    dict(id='wan', name='通义万相', category='AI视频', mode='api', url='https://tongyi.aliyun.com/wanxiang/', note='当前适配 5 秒竖屏无口播空镜，不是完整数字人视频。'),
    dict(id='qingying', name='智谱清影', category='AI视频', mode='manual', url='https://chatglm.cn/', note='当前按网页制作接入；模型 API 待适配，不承诺永久免费或固定免费额度。'),
    dict(id='jianying', name='剪映专业版', category='剪辑', mode='manual', url='https://www.capcut.cn/', note='导出口播、字幕、分镜工单供客户端剪辑；不声称自动导入工程或自动导出。'),
    dict(id='bijian', name='必剪', category='剪辑', mode='manual', url='https://bcut.bilibili.cn/', note='下载制作包后在客户端剪辑，完成后回传成片。'),
    dict(id='dujia', name='度加剪辑', category='图文转视频', mode='manual', url='https://aigc.baidu.com/', note='当前按网页制作接入，具体账号功能和额度以平台为准。'),
    dict(id='yixiaoer', name='蚁小二', category='批量分发', mode='pending', url='https://www.yixiaoer.cn/', note='官方已提供账号管理与发布开放平台；本版本待取得应用权限和接口文档后适配，当前不是已直连。', docs='https://open.yxiaoer.cn/'),
    dict(id='yimei', name='易媒助手', category='批量分发', mode='pending', url='https://yimeizhushou.com/', note='可导出审核后的分发清单；未核实可用的公开开发者发布接口，不伪造直连接口。', docs='https://yimeizhushou.com/help.html'),
]
MANUAL_IDS = {t['id'] for t in TOOLS if t['mode'] == 'manual'}
