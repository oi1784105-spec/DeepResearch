# Deep Research 部署手册

本文用于在 Windows、Linux 或 Ubuntu 虚拟机中部署 Deep Research。项目由 FastAPI 后端和 Vue 3 前端组成，前端通过 Vite 代理访问后端。

## 1. 检查环境

```bash
python3 --version
node --version
npm --version
```

Python 推荐 3.11，Node.js 推荐 20.19 或更高版本。Ubuntu 服务器还需要安装 build-essential、python3-dev 和 libmagic 等系统依赖，具体以 pip 安装时报错为准。

## 2. 后端部署

```bash
cd deep-research
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

编辑 .env：

```env
APP_ENV=production
HOST=0.0.0.0
PORT=8000
CORS_ALLOW_ORIGINS=http://你的前端地址
SECRET_KEY=随机长字符串
API_KEY_ENCRYPTION_KEY=Fernet密钥
AUTH_DB_PATH=./data/app.db
```

生成加密密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

启动并验证：

```bash
.venv/bin/python app/app_main.py
curl http://127.0.0.1:8000/health
```

Windows 将最后一条启动命令替换为 `.venv\Scripts\python.exe app/app_main.py`。后端启动时会自动创建 SQLite 表，不需要手工执行建表脚本。

## 3. 前端部署

开发或内网测试：

```bash
cd front/agent_front
npm install
npm run dev -- --host 0.0.0.0
```

生产构建：

```bash
npm run build
```

将 dist 交给 Nginx、Caddy 或其他静态 Web 服务器。前端与后端分离时，修改 vite.config.ts 的 proxy.target 仅影响开发服务器；生产环境应在 Nginx 中把 /api 和 /health 反向代理到后端 8000 端口，并把前端域名加入 CORS_ALLOW_ORIGINS。

## 4. 首次配置

访问前端地址，注册账号并登录。进入 API 配置页，选择接口协议，填写 Endpoint、API Key、模型 ID，先测试连接，再获取模型列表，最后保存并启用。用户 API Key 会在后端加密保存，不会由前端列表回显。

## 5. 运行检查

- GET /health 返回 status 为 ok。
- 浏览器能完成注册、登录和 Provider 保存。
- Provider 测试连接成功，模型列表可获取或能手动填写模型。
- 发送普通问题、上传 PDF 或图片、切换对话后均能返回结果。
- 生产环境日志中不应出现 API Key、密码、JWT 或上传文件内容。

## 6. 安全与备份

不要提交 .env、data/app.db、data/uploads、日志、WAL 文件、node_modules 或 dist。定期备份数据库前先停止服务，并对备份文件加密。修改 API_KEY_ENCRYPTION_KEY 前必须重新配置已有 Provider。生产环境只开放 HTTPS 入口，限制管理端口和 SSH 来源。

## 7. 联系方式

微信：Sane_926

