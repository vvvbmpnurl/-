# 闪速记单词 · 内容工厂

在现有单文件工作台上增加服务端视频任务、人工成片审核与多账号分发流程。保留原有选题、成稿、导出和排期。

## 服务器部署

尚未购买服务器时，可先审阅 [服务器部署说明](deploy/README.md)。本次提供 Docker Compose、Caddy HTTPS、单管理员密码入口和持久化数据卷；不是已上线，也不是完整团队协作版。实际部署需要Linux服务器、域名和DNS配置。

## 本机运行

Python 3.10+，无需安装第三方依赖：

```sh
python3 install.py
python3 server.py
```

打开 http://127.0.0.1:8765 ，进入「新媒体端口 → B7 内容工厂」。先在原有选题区生成成稿，再在新增的视频生产区选择成稿、修改口播或镜头提示词，选择工具。闪剪/万相走服务端 API；其他已列出的制作工具创建手动任务，导出制作包、口播和字幕，在工具中完成制作后回传可播放的 HTTPS 成片直链。当前不支持本地视频文件上传。完成后查询进度、预览视频、人工审核，再选择账号分发。刷新页面会保留服务端任务和发布记录；原有成稿仍保存在原浏览器本地。

通过进程环境配置密钥（参见 `.env.example`，程序不会自动加载 `.env`）。密钥不返回浏览器，不提交到 GitHub。数据库默认位于 `data/factory.db`，也可用 `FACTORY_DB` 修改。该服务是**单人本机版**，只监听 127.0.0.1，校验 Host、Origin 和会话 CSRF；不要直接暴露公网。团队部署需另补登录、审核角色、租户隔离和持久任务队列。

## 接入范围与现状

- **闪剪官方直连接口已实现、待真实联调**：`POST https://openapi.shanjian.tv/v1/virtualman/video`，`GET /v1/task/info?taskId=...`。配置 `SHANJIAN_API_KEY`、`SHANJIAN_AVATAR_ID`、`SHANJIAN_SPEAKER_ID`、`AIGC_CONTENT_PRODUCER`。口播 3–3600 字符，输出无包装数字人口播；字幕、剪辑及画面 AI 标识仍需检查。形象与声音需为有权使用的资产，服务端发送 AIGC 隐式标识。
- **腾讯智影、小云雀、即梦、可灵、智谱清影、剪映专业版、必剪、度加剪辑**：当前都可通过手动制作包与成片回传进入统一流程；未宣称这些工具已自动生成。即梦已有火山引擎视频官方接口，但本版尚未适配，不等于网页数字人已能 API 调用。
- **蚁小二 / 易媒助手**：提供入口和人工审核后的分发清单导出，清单不是它们保证可导入的专用格式。蚁小二已确认有开放平台，真实直连待取得应用权限及具体接口文档；易媒助手未确认可用公开开发者发布接口。当前通用发布网关不是两家的官方适配器。
- **阿里万相**：直接调用北京地域 DashScope 异步接口，模型 `wan2.1-t2v-turbo`，720×1280、5秒，生成无口播的 AI 镜头素材。不能将其视为完整长视频或数字人视频。
- **HeyGen（可选）**：实现 `v2/video/generate` 与 `v1/video_status.get` 适配，需 API 套餐、有效形象 ID 与音色 ID。国内数字人需求不依赖此适配器。
- **分发**：抖音、小红书、视频号的多账号服务适配接口。必须由你拥有正式授权和发布能力的网关提供下述接口；本仓库没有伪造各平台开放发布权限，也不自动登录或绕过权限。公众号图文保留原有导出流程，不纳入此视频分发接口。
- 未配置的平台会显示“未配置”并禁用按钮。已有密钥仅显示“已配置”，不等于连通性验证通过。
- 当前没有供应商密钥或已授权账号，**未进行真实视频生成、真实账号发布测试**，也未触发付费调用。自动测试使用模拟上游响应。

## 其他数字人网关兼容契约

设置 `AVATAR_GATEWAY_URL` 为 HTTPS 基地址，`AVATAR_GATEWAY_TOKEN` 为服务端令牌，按需配置 `AVATAR_ID`、`AVATAR_VOICE_ID`。该兼容接口保留在服务端，当前 UI 优先显示用户指定的工具；可在 `server.py` 中增加其他官方适配器，或者由自有网关转换官方接口。单纯填写平台官网地址不能接通。

创建：`POST {base}/videos`，请求头 `Authorization: Bearer ...`、`Idempotency-Key: <本地任务ID>`。

```json
{"script":"选题生成的完整口播稿","title":"标题","aspect_ratio":"9:16","ai_generated":true,"avatar_id":"形象ID","voice_id":"音色ID","idempotency_key":"本地任务ID"}
```

返回 `{"task_id":"平台任务ID"}`。网关须将完整稿件用于语音及口型生成，并实现幂等。

查询：`GET {base}/videos/{task_id}`，同样使用 Bearer 认证。返回：

```json
{"status":"completed","video_url":"https://.../video.mp4"}
```

状态支持 `processing` / `completed` / `failed`。完成时必须返回 HTTPS 成片地址；失败可在平台控制台查看详情。

## 多账号发布网关契约

设置 `PUBLISH_GATEWAY_URL`、`PUBLISH_GATEWAY_TOKEN`，并通过 `PUBLISH_ACCOUNTS` 配置已经在该服务授权的账号：

```json
[{"id":"授权服务中的账号ID","name":"西安门店·抖音","platform":"dy"},{"id":"另一个账号ID","name":"总部门店·视频号","platform":"sph"}]
```

平台支持 `dy` / `xhs` / `sph`。配置账号不等于完成平台 OAuth，授权必须在发布服务中完成。

创建：`POST {base}/publications`，Bearer 认证，`Idempotency-Key` 请求头。请求体：

```json
{"account_id":"账号ID","platform":"dy","video_url":"https://.../video.mp4","title":"视频标题","description":"口播稿","ai_generated":true,"idempotency_key":"本地分发记录ID"}
```

返回 `{"publication_id":"唯一发布ID","status":"submitted"}`；仅平台明确发布成功时返回 `published`，可附 `url`；确定失败返回 `failed`。网关必须映射各平台要求的 AI 标识字段、下载/上传视频并使用正式授权发布，不得忽略 AI 标识。平台不支持时必须报错。网关需提供幂等保证。

查询：`GET {base}/publications/{publication_id}`，返回同样结构及最新状态。前端“查询发布结果”更新记录。未明确成功不会显示“已发布”。

## 审核、幂等与恢复

制作稿在任务提交时形成不可变快照；改稿需创建新任务，不能继承旧成片审核。文案关键词扫描不等于人工成片审核。人工通过需勾选已观看并检查成片；退回必须给修改意见。开始分发后冻结审核记录。

发布前服务端重新验证成片、审核与账号清单。SQLite 唯一约束防止同一成片同一账号重复提交；批量请求按账号保存结果，部分失败不会抹去成功记录。进程重启会把中断的提交标记为“结果待核实”；网络超时也标记待核实且不自动重发。已有发布ID可查询，缺少ID需去平台核对。本版本没有自动重试和定时分发，避免不确定结果下重复发布；确定失败后核实原因，修正并创建新制作任务。

平台视频链接可能有有效期；请及时下载成片。本版本未做长期素材对象存储。提交后请用“查询制作进度”获取成片，发布后用“查询发布结果”获取最终回执。

## 验证

```sh
python3 -m unittest discover -s tests -v
node --check factory.js
```

测试验证人工审核门禁、不可变稿件快照、平台适配映射、失败与超时状态、多账号去重、部分成功、重启恢复和本机 HTTP 防护。正式上线前仍需使用你指定的国内数字人供应商及授权分发服务进行联调。

浏览器验证脚本：环境安装 Playwright 后执行 `node tests/browser-check.cjs`，默认使用 `/usr/bin/chromium`，可用 `CHROMIUM_PATH` 指定。脚本在本机临时端口运行服务，使用模拟视频/发布响应验证原有成稿导入、审核门禁、发布回执和窄屏布局。

## 本次工具核实依据（2026-11-04）

- 闪剪快速接入及实名认证、资源包要求：https://openapi-doc.shanjian.tv/7289369m0
- 闪剪数字人口播字段：https://openapi-doc.shanjian.tv/342245572e0
- 闪剪查询任务详情：https://openapi-doc.shanjian.tv/342296170e0
- 闪剪结果状态结构：https://openapi-doc.shanjian.tv/7694236m0
- 闪剪视频链接通常仅保留24小时，需及时转存：https://openapi-doc.shanjian.tv/7331505m0
- 蚁小二开放平台能力：https://open.yxiaoer.cn/
- 小云雀官方产品手册：https://xyq.jianying.com/tutorials/web-manual
- 即梦火山引擎视频 API：https://docs.volcengine.com/docs/jimeng-ai/jimeng-ai-video-generation-30-pro-interface-documentation?lang=zh
- 易媒助手帮助中心：https://yimeizhushou.com/help.html

不沿用截图中的“永久免费”“仅企业可调用”等未验证承诺。费用、模型、时长、账号权限以官方最新控制台为准。目录中的“手动制作”描述当前系统实现，并不推断厂商不存在任何 API。

新增验证涵盖闪剪官方字段/状态映射、全部手动工具的回传与审核门禁、不可更换已审核成片、防止误把分发工具当视频生成接口。共12项后端测试及浏览器流程验证通过；没有真实平台凭证，仍未触发付费调用或发布。
