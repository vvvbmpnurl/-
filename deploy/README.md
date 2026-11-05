# 内容工厂服务器试用部署

本方案把已有单人工作台放到 HTTPS 和账号密码入口之后，适合小范围内部试用。当前使用一个管理员账号，进入后的所有操作均为管理员权限，不提供成员角色、审核人身份审计或租户隔离。原有选题/成稿仍属于各浏览器 localStorage，不是团队共享数据库；视频任务与分发记录在服务端共享。正式多人协作需继续实现账户体系、权限、共享选题与任务队列。

## 前置条件

- 有 Docker Engine 和 Compose v2 的 Linux 服务器，推荐先使用 2核4GB 起步进行小规模测试；视频计算在外部平台完成。
- 域名 DNS 已指向服务器，80/443 可访问且没有其他服务占用；SSH 管理端口仅向管理来源开放。
- 服务器能访问闪剪等所选平台的 HTTPS API。国内服务器的域名及访问条件需由服务器服务商确认。
- 取得本 PR 分支代码，服务器私有保存。原 index.html 中的门店信息和原有内置浏览器 Key 不会因容器部署自动清除；全部页面必须位于认证入口之后，原有 Key 建议迁移或轮换。不要将镜像推送公共镜像仓库。

## 初次配置

在项目根目录：

```sh
cp deploy/server.env.example deploy/server.env
chmod 600 deploy/server.env
```

编辑文件，填写域名和登录用户名。交互生成登录密码哈希：

```sh
docker run --rm -it caddy:2.10-alpine caddy hash-password
```

将输出的哈希填入 `FACTORY_ADMIN_PASSWORD_HASH`，保留单引号。不要把明文密码写入文件或命令行参数。生成一个独立代理令牌：

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

将结果填入 `FACTORY_PROXY_TOKEN`。供应商密钥仅在服务器配置，不发送到聊天或提交 GitHub。

## 启动与检查

```sh
docker compose --env-file deploy/server.env -f compose.server.yml config --quiet
docker compose --env-file deploy/server.env -f compose.server.yml up -d --build
docker compose --env-file deploy/server.env -f compose.server.yml ps
docker compose --env-file deploy/server.env -f compose.server.yml logs --tail=100
```

容器构建自动运行页面安装脚本，无需修改仓库里的原 index.html。Caddy 自动申请/续期证书，HTTP 转 HTTPS；服务端无宿主机公开端口，只有 Caddy 暴露80/443。不要手动把8765映射到公网。服务端还验证域名、代理令牌、HTTPS Origin及CSRF。

通过 `https://你的域名` 登录。先确认未登录返回401，再验证登录后页面和 API 正常。提交一条手动制作任务测试持久化：重启服务后任务应保留。供应商 API 付费制作及真实账号发布需配置后用一条测试内容联调。

上游 API 等待期间当前使用单进程锁，其他请求可能排队；这是试用方案，不适合高并发。配置变更后重新执行 up -d 会重建相关容器；变更密码哈希后新请求需使用新密码。

## 数据备份

数据库在 `factory_data` 命名卷；Caddy证书保存在独立命名卷。不要执行 `down -v`，它会删除命名卷。

在项目根目录创建一致性数据库快照（运行中可执行，依赖SQLite备份API）：

```sh
mkdir -p backups
docker compose --env-file deploy/server.env -f compose.server.yml exec -T factory python3 -c 'import sqlite3; s=sqlite3.connect("/data/factory.db"); d=sqlite3.connect("/data/factory.backup.db"); s.backup(d); d.close(); s.close()'
docker compose --env-file deploy/server.env -f compose.server.yml cp factory:/data/factory.backup.db backups/factory.backup.db
```

每次备份请在安全位置另外归档，避免覆盖唯一副本。备份和 server.env 含业务数据/密钥，应保存在受限位置，不上传公共仓库。视频链接不是永久素材备份，仍需另外保存成片。

## 当前验证范围

Python后端/HTTP和浏览器流程可本地验证；服务器上线仍需实际域名、DNS、80/443及服务器访问。当前环境的 Docker 构建和 Caddy HTTPS 验收如未执行，不能视为部署成功。没有服务器访问信息时，本项目只交付部署配置，不会宣称已上线。
