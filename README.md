# 万州商户通

面向万州中小商户的数字化经营助手 MVP。平台包含商户端和运营后台，提供商户档案、经营分析、透明规则画像、通信与数字服务推荐，以及运营侧商户/数据/资源管理。

生产部署可为两类用户配置独立入口，例如 `merchant.example.com`（商户端）和 `admin.example.com`（管理端）。前后端会根据入口限制账号角色，实际域名及基础设施配置由部署环境提供。

## 技术栈

- 前端：Vue 3、TypeScript、Element Plus、ECharts、Vite
- 后端：FastAPI、SQLAlchemy、JWT、PBKDF2 密码摘要
- 数据库：开发默认 SQLite，生产 MySQL 8.4
- 部署：Docker Compose、Nginx、Let's Encrypt

## 项目文档

详细文档见 [docs 文档中心](./docs/README.md)：

- [功能介绍](./docs/功能介绍.md)
- [开发指南](./docs/开发指南.md)
- [架构说明](./docs/架构说明.md)
- [API 概览](./docs/API概览.md)
- [部署指南](./docs/部署指南.md)

## 本地开发

后端推荐 Python 3.12：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# 将 .env 中的占位值替换为仅供本地开发使用的值
uvicorn app.main:app --reload
```

前端另开终端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:5173`，API 文档位于 `http://localhost:8000/api/docs`。首次启动会自动建表并写入完全虚构的样例数据。初始化凭据通过环境变量配置，请勿将真实凭据提交到版本库。

## 测试

```bash
cd backend
DATABASE_URL=sqlite:////tmp/wst-test.db JWT_SECRET=test-only pytest -q

# 或对运行中的 API 做真实 HTTP 冒烟验证
python tests/smoke_live.py http://127.0.0.1:8000

cd ../frontend
npm run build
```

## Docker 部署

```bash
cp .env.example .env
# 修改所有密码、JWT_SECRET、域名和 CORS_ORIGINS
docker compose build
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose up -d
docker compose ps
curl http://127.0.0.1:8080/api/v1/health
```

容器中的 MySQL 只连接内部网络，Web 服务仅绑定服务器回环地址 `127.0.0.1:8080`。生产环境应另行配置 HTTPS 反向代理、备份、监控和访问控制；服务器地址、备案信息、云存储配置及真实凭据不应提交到本仓库。

## API

所有业务接口使用 `/api/v1` 前缀和 `{ code, message, data }` 响应结构。主要接口包括：

- `POST /auth/login`、`GET /auth/me`
- `GET/POST /merchants`、`GET/PUT /merchants/{id}`
- `GET/POST/PUT /merchants/{id}/business-data`
- `GET /merchants/{id}/business-summary`
- `GET /merchants/{id}/profile`
- `GET /merchants/{id}/recommendations`
- `GET/POST/PUT /resources`、`PATCH /resources/{id}/status`
- `GET /dashboard/overview`

## MVP 边界

这是公开演示型 MVP，不包含支付、短信、外卖/短视频平台或运营商生产系统接入，不使用机器学习或大模型。画像与推荐完全由可解释规则生成。仓库中的名称、地址、电话和经营数据均为虚构样例，不得用于指代真实主体。
