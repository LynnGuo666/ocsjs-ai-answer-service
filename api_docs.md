# AI题库服务API文档

## 概述

AI题库服务是一个基于OpenAI API的问题解答服务，专为[OCS (Online Course Script)](https://github.com/ocsjs/ocsjs)设计，可以通过AI自动回答题目。此服务实现了与OCS AnswererWrapper兼容的API接口，方便用户将AI能力整合到OCS题库搜索中。

## 接口详情

### 搜索接口

**URL**: `/api/search`

**方法**: `GET` 或 `POST`

**参数**:

| 参数名   | 类型   | 必填 | 说明                                                     |
|---------|--------|------|----------------------------------------------------------|
| title   | string | 否   | 题目文字内容（与 `image` 至少提供一个）                    |
| type    | string | 否   | 题目类型 (single-单选, multiple-多选, judgement-判断, completion-填空) |
| options | string | 否   | 选项内容，通常是A、B、C、D选项的文本                       |
| image   | string | 否   | 题目图片：`data:image/png;base64,...`、`http(s)://` 地址、或裸 base64 均可。别名 `img` / `image_url` / `image_base64` 等价 |

**成功响应**:

```json
{
  "code": 1,
  "question": "问题内容",
  "answer": "AI生成的答案"
}
```

**失败响应**:

```json
{
  "code": 0,
  "msg": "错误信息"
}
```

### 图片题（多模态）

题目是截图／图片时，通过 `image` 参数把图片一起传过来，服务会走多模态请求让模型直接读图作答：

```bash
curl -X POST http://<YOUR_HOST>:5999/api/search \
  -H 'X-API-Key: <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"title":"根据图片选择正确答案","type":"single","options":"A. 选项1\nB. 选项2","image":"<base64 或图片URL>"}'
```

- 题干与图片至少给一个，**只传 `image` 也能作答**
- 图片过大（归一化后超过 8MB）返回 `code:0` 并提示压缩
- 缓存键包含图片指纹，同题干不同图片不会串答案
- 依赖模型具备视觉能力，纯文本模型会报错或返回空答案

### 健康检查接口

**URL**: `/api/health`

**方法**: `GET`

**响应**:

```json
{
  "status": "ok",
  "message": "AI题库服务运行正常",
  "version": "1.0.0",
  "cache_enabled": true,
  "model": "<模型名>"
}
```

### 缓存清理接口

**URL**: `/api/cache/clear`

**方法**: `POST`

**响应**:

```json
{
  "success": true,
  "message": "缓存已清除"
}
```

### 统计信息接口

**URL**: `/api/stats`

**方法**: `GET`

**响应**:

```json
{
  "version": "1.0.0",
  "uptime": 1621234567.89,
  "model": "<模型名>",
  "cache_enabled": true,
  "cache_size": 123
}
```

## OCS配置示例

在OCS的自定义题库配置中添加如下配置：

```json
[
  {
    "name": "AI智能题库",
    "homepage": "http://<YOUR_HOST>:5999/",
    "url": "http://<YOUR_HOST>:5999/api/search?api_key=<YOUR_API_KEY>",
    "method": "post",
    "type": "GM_xmlhttpRequest",
    "contentType": "json",
    "data": {
      "title": "${title}",
      "type": "${type}",
      "options": "${options}"
    },
    "handler": "return (res)=> res.code === 1 && res.answer ? [res.question, res.answer] : undefined"
  }
]
```

> ⚠️ `type` 必须是 `GM_xmlhttpRequest`。部分网课站点（如智慧树考试页）的 CSP `connect-src` 不含你的题库域名，页面 `fetch` 会被浏览器直接拦截并报 `TypeError: Failed to fetch`；`GM_xmlhttpRequest` 由脚本管理器发请求，不受页面 CSP 限制。使用前需在脚本 `@connect` 中允许题库域名（或安装官方全域名通用版本）。
>
> ⚠️ 上面的 `api_key` 是**必填**的，否则一律 401。`<YOUR_HOST>` / `<YOUR_API_KEY>` 换成你自己的部署地址和 `.env` 里的 `API_KEYS`。
>
> 若你的 OCS 版本提供题目图片变量（如 `${img}`），可在 `data` 中加 `"image": "${img}"` 以支持图片题；**不确定支持就不要加**，否则会把字面量字符串 `${img}` 当图片传过来导致失败。

## 安全设置

服务启用固定 API Key 鉴权，密钥配置在 `.env` 中：

```
API_KEYS=your_secret_key_here
```

除 `/api/health` 外的所有 `/api/*` 请求、以及 `/dashboard` 页面，都必须携带密钥，任选一种方式：

1. HTTP 头部：`X-API-Key: your_secret_key_here`
2. HTTP 头部：`Authorization: Bearer your_secret_key_here`
3. URL 参数：`?api_key=your_secret_key_here`（适合无法自定义请求头的 OCS 客户端）

未携带或错误时返回 HTTP 401：

```json
{"code":0,"msg":"无效的 API Key"}
```

> `.env` 是本服务的**唯一配置源**（端口、模型、密钥都在里面），修改后需 `systemctl restart ocs` 生效。
> 页面访问可直接带上密钥：`http://<YOUR_HOST>:5999/?api_key=<YOUR_API_KEY>`，页面内的接口调用与站内链接会自动携带。

## 注意事项

1. **多选题答案格式**: 对于多选题，OCS期望的答案格式是用`#`分隔的选项，例如`A#B#C`。本服务会自动处理这个格式，将OpenAI返回的多选答案转换为此格式。

2. **API请求限制**: 注意OpenAI API有使用限制和费用。确保你的账户有足够的额度来处理预期的请求量。

3. **网络连接**: 确保部署此服务的服务器能够访问 `.env` 中 `OPENAI_API_BASE` 指向的 API 地址，且该模型支持视觉（图片题需要）。

4. **题库域名**: 根据OCS文档说明，需要将题库配置中`homepage`以及`url`所涉及到的域名，在脚本头部元信息`@connect`中新增，否则无法请求到数据。