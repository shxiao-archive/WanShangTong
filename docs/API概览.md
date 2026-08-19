# API 概览

## 基本约定

- 基础前缀：`/api/v1`
- 数据格式：JSON，文件上传使用 `multipart/form-data`
- 默认响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

业务错误使用对应 HTTP 状态码，并保持相同的 `code` / `message` / `data` 结构。参数校验错误默认返回 `422`。

## 认证与会话

浏览器客户端在请求中携带 `X-WST2-Browser-Session: 1`，登录后由服务端设置 HttpOnly 会话 Cookie。Axios 客户端已配置 `withCredentials: true`。

后端也能从 `Authorization: Bearer <token>` 读取令牌，但浏览器端不应把令牌保存在可由 JavaScript 读取的本地存储中。

生产环境的 Nginx 根据子域名写入 `X-WST2-Portal: merchant|operator`。后端用该值校验入口与账号角色是否一致。

## 接口分类

### 认证 `/auth`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `POST` | `/auth/login` | 登录并创建会话 |
| `POST` | `/auth/register` | 注册商户或运营账号 |
| `POST` | `/auth/operator-invites` | 运营人员生成 24 小时邀请码 |
| `GET` | `/auth/me` | 获取当前用户 |
| `POST` | `/auth/logout` | 删除浏览器会话 |
| `POST` | `/auth/change-password` | 修改密码并使旧令牌失效 |

### 账号 `/users`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/users` | 运营人员查看账号列表 |
| `POST` | `/users/{user_id}/reset-password` | 重置账号密码 |
| `PATCH` | `/users/{user_id}/status` | 启用或停用账号 |

### 商户入驻 `/merchant-onboarding`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/merchant-onboarding/me` | 获取当前商户的入驻草稿/申请 |
| `PUT` | `/merchant-onboarding/me/draft` | 保存分步入驻草稿 |
| `POST` | `/merchant-onboarding/me/documents` | 上传资质文件 |
| `POST` | `/merchant-onboarding/me/submit` | 提交入驻审核 |
| `GET` | `/merchant-onboarding` | 运营人员查询入驻申请 |
| `GET` | `/merchant-onboarding/summary` | 入驻申请汇总 |
| `GET` | `/merchant-onboarding/{application_id}` | 查看入驻详情 |
| `PATCH` | `/merchant-onboarding/{application_id}/review` | 通过或要求补充资料 |

`POST /merchant-onboarding/me` 为兼容旧客户端保留的废弃接口，新代码应使用草稿和提交接口。

### 资质与媒体

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/credential-documents/{document_id}/content` | 权限检查后预览资质文件 |
| `DELETE` | `/credential-documents/{document_id}` | 删除可删除的资质文件 |
| `GET` | `/media/{media_id}/content` | 权限检查后返回商品图片 |
| `DELETE` | `/media/{media_id}` | 删除媒体文件 |

### 商户 `/merchants`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/merchants` | 商户列表/当前商户可见范围 |
| `GET` | `/merchants/{merchant_id}` | 商户档案 |
| `PUT` | `/merchants/{merchant_id}` | 更新商户档案 |
| `POST` | `/merchants/{merchant_id}/product-images` | 上传商品图片 |
| `GET` | `/merchants/{merchant_id}/business-summary` | 经营汇总与图表数据 |
| `GET` | `/merchants/{merchant_id}/profile` | 可解释商户画像 |
| `GET` | `/merchants/{merchant_id}/recommendations` | 数字化资源推荐 |

### 经营数据 `/merchants/{merchant_id}/business-data`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/merchants/{merchant_id}/business-data` | 查询经营数据 |
| `POST` | `/merchants/{merchant_id}/business-data` | 新增单日数据 |
| `PUT` | `/merchants/{merchant_id}/business-data/{data_id}` | 修改单日数据 |
| `DELETE` | `/merchants/{merchant_id}/business-data/{data_id}` | 删除单日数据 |
| `GET` | `/merchants/{merchant_id}/business-data/template` | 下载 Excel 导入模板 |
| `POST` | `/merchants/{merchant_id}/business-data/import` | 预览或确认 Excel 导入 |
| `GET` | `/merchants/{merchant_id}/business-data/export` | 导出 Excel |

### 数字化资源 `/resources`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/resources` | 查询可见资源 |
| `POST` | `/resources` | 新增资源 |
| `PUT` | `/resources/{resource_id}` | 编辑资源 |
| `PATCH` | `/resources/{resource_id}/status` | 启用或停用资源 |

### 服务申请 `/service-applications`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `POST` | `/service-applications` | 商户创建服务申请 |
| `GET` | `/service-applications` | 按权限查询申请 |
| `GET` | `/service-applications/summary` | 申请状态汇总 |
| `GET` | `/service-applications/{application_id}` | 申请详情与时间线 |
| `PATCH` | `/service-applications/{application_id}/status` | 推进或取消申请 |
| `POST` | `/service-applications/{application_id}/notes` | 添加跟进备注/商户留言 |

### 通知与待办 `/inbox`

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/inbox/summary` | 未读、待办和申请数量汇总 |
| `GET` | `/inbox/notifications` | 查询通知 |
| `PATCH` | `/inbox/notifications/{notification_id}/read` | 标记单条已读 |
| `POST` | `/inbox/notifications/read-all` | 标记筛选范围内全部已读 |
| `GET` | `/inbox/work-items` | 运营人员查询待办 |

### 看板、协议与系统

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| `GET` | `/dashboard/overview` | 按角色返回首页概览 |
| `GET` | `/legal/agreements/current` | 当前服务规则和隐私政策版本 |
| `GET` | `/system/status` | 运营人员查看系统与备份状态 |
| `GET` | `/health` | 基础存活检查 |
| `GET` | `/health/live` | 存活检查 |
| `GET` | `/health/ready` | 数据库与上传目录就绪检查 |

## 权限原则

- 运营专属：账号管理、入驻审核、资源写入、运营待办和系统状态。
- 商户专属：入驻申请、自有商户档案与经营数据写入、提交服务申请。
- 运营人员可查看商户档案和经营数据，但不代替商户修改其业务数据。
- 商户不能访问其他商户的档案、文件、经营数据或申请。

## 交互式文档

`ENVIRONMENT` 不是 `production` 时，FastAPI 提供：

- Swagger UI：`/api/docs`
- OpenAPI JSON：`/api/openapi.json`

生产环境默认关闭这两个入口。

[返回文档中心](./README.md)
