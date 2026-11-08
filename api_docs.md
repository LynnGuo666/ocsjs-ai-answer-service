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
| title   | string | 是   | 题目内容                                                 |
| type    | string | 否   | 题目类型 (single-单选, multiple-多选, judgement-判断, completion-填空) |
| options | string | 否   | 选项内容，通常是A、B、C、D选项的文本                       |
| images  | string[] | 否 | 图片题优化：base64 data URL 数组，顺序对应 `[图片1]`、`[图片2]`…（仅 POST JSON） |
| suggestion_title | string | 否 | 图片题优化：图片 URL 已替换为 `[图片N]` 占位符的题目文本 |
| suggestion_options | string | 否 | 图片题优化：图片 URL 已替换为 `[图片N]` 占位符的选项文本 |

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
  "model": "gpt-3.5-turbo"
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
  "model": "gpt-3.5-turbo",
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
    "homepage": "https://github.com/yourusername/ai-answer-service",
    "url": "http://localhost:5000/api/search",
    "method": "post",
    "type": "GM_xmlhttpRequest",
    "contentType": "json",
    "headers": {
      "X-API-Key": "your-api-key"
    },
    "data": {
      "title": "${title}",
      "type": "${type}",
      "options": "${options}",
      "images": { "handler": "return (env)=> env.images || []" },
      "suggestion_title": "${suggestion_title}",
      "suggestion_options": "${suggestion_options}"
    },
    "handler": "return (res)=> res.code === 1 && res.answer ? [res.question, res.answer] : undefined"
  }
]
```

> ⚠️ `type` 必须是 `GM_xmlhttpRequest`。部分网课站点（如智慧树考试页）的 CSP `connect-src` 不含 `localhost`，页面 `fetch` 会被浏览器直接拦截并报 `TypeError: Failed to fetch`；`GM_xmlhttpRequest` 由脚本管理器发请求，不受页面 CSP 限制。使用前需在脚本 `@connect` 中允许 `localhost`（或安装官方全域名通用版本）。

## 安全设置

**服务对外部署时强烈建议开启 API Key 鉴权**，否则任何人都能调用你的接口、消耗你的 OpenAI 额度。在 `.env` 中设置：

```
# 多个 Key 用英文逗号分隔，方便分给不同的人并单独作废
API_KEYS=sk-ocs-xxxxxxxx,sk-ocs-yyyyyyyy
```

可以用 `python -c "import secrets;print('sk-ocs-'+secrets.token_urlsafe(24))"` 生成随机 Key。旧配置 `ACCESS_TOKEN` 仍然有效，会和 `API_KEYS` 合并使用。

开启后，`/api/search`、`/api/stats`、`/api/cache/clear`、`/dashboard` 都需要带 Key，`/`、`/docs`、`/api/health` 不需要。Key 可以用下面任一方式传递：

1. `X-API-Key: <key>`（推荐，OCS 配置里写在 `headers`）
2. `Authorization: Bearer <key>`
3. `X-Access-Token: <key>`（旧版兼容）
4. URL 参数 `?key=<key>` 或 `?token=<key>`（仪表盘用：`/dashboard?key=<key>`）

Key 错误或缺失时返回 HTTP 401，响应体为 `{"code": 0, "msg": "无效或缺失的 API Key"}`。

OCS 配置中加上 `headers` 即可：

```json
"headers": {
  "X-API-Key": "sk-ocs-xxxxxxxx"
},
```

> URL 参数里的 Key 可能出现在浏览器历史和代理日志中，OCS 请优先用请求头传递；公网部署请配合 HTTPS。

## 注意事项

1. **多选题答案格式**: 对于多选题，OCS期望的答案格式是用`#`分隔的选项，例如`A#B#C`。本服务会自动处理这个格式，将OpenAI返回的多选答案转换为此格式。

2. **API请求限制**: 注意OpenAI API有使用限制和费用。确保你的账户有足够的额度来处理预期的请求量。

3. **网络连接**: 确保部署此服务的服务器能够访问OpenAI API（api.openai.com）。某些地区可能需要代理服务。

4. **题库域名**: 根据OCS文档说明，需要将题库配置中`homepage`以及`url`所涉及到的域名，在脚本头部元信息`@connect`中新增，否则无法请求到数据。