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
| image   | string | 否   | 题目图片：`data:image/png;base64,...`、`http(s)://` 地址、或裸 base64。别名 `images` / `img` / `image_url` / `image_base64` |
| images  | array  | 否   | 多张图片（可用 `{"handler": "return (env)=> env.images"}` 传数组，也兼容 `"${images}"` 拼成的逗号字符串） |
| suggestion_title | string | 否 | OCS 提供的 OCR 后题干文本，有则优先于 `title` |
| suggestion_options | string | 否 | OCS 提供的 OCR 后选项文本，有则优先于 `options` |

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

题目是截图／图片时，把图片通过 `image` 参数传入，或**让图片地址留在题干里**，服务都会自动处理：

```bash
curl -X POST http://localhost:5000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"title":"根据图片选择正确答案","type":"single","options":"A. 选项1\nB. 选项2","image":"<base64 或图片URL>"}'
```

- 题干与图片至少给一个，**只传 `image` 也能作答**
- **题干里内联的图片地址会自动识别并下载**（OCS 常把 `<img>` 的 src 直接拼进标题），无需额外配置
- 图片在服务端带浏览器 UA 下载后转 base64，单张上限 6MB，单次最多 `MAX_IMAGES` 张（默认 10）
- 缓存键包含图片指纹，同题干不同图片不会串答案
- 依赖模型具备视觉能力，纯文本模型会报错或返回空答案

> 注意：推理模型可能把 `max_tokens` 全部消耗在 reasoning 上导致 `content` 为空。
> 服务在空答案时会自动抬高上限重试一次；建议把 `MAX_TOKENS` 设为 16000 左右。

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
    "data": {
      "title": "${title}",
      "type": "${type}",
      "options": "${options}"
    },
    "handler": "return (res)=> res.code === 1 && res.answer ? [res.question, res.answer] : undefined"
  }
]
```

> ⚠️ `type` 必须是 `GM_xmlhttpRequest`。部分网课站点（如智慧树考试页）的 CSP `connect-src` 不含 `localhost`，页面 `fetch` 会被浏览器直接拦截并报 `TypeError: Failed to fetch`；`GM_xmlhttpRequest` 由脚本管理器发请求，不受页面 CSP 限制。使用前需在脚本 `@connect` 中允许 `localhost`（或安装官方全域名通用版本）。

## 安全设置

如果你想增加安全性，可以在`.env`文件中设置访问令牌：

```
ACCESS_TOKEN=your_secret_token_here
```

设置后，所有API请求都需要包含此令牌，可以通过以下两种方式之一传递：

1. HTTP头部: `X-Access-Token: your_secret_token_here`
2. URL参数: `?token=your_secret_token_here`

## 注意事项

1. **多选题答案格式**: 对于多选题，OCS期望的答案格式是用`#`分隔的选项，例如`A#B#C`。本服务会自动处理这个格式，将OpenAI返回的多选答案转换为此格式。

2. **API请求限制**: 注意OpenAI API有使用限制和费用。确保你的账户有足够的额度来处理预期的请求量。

3. **网络连接**: 确保部署此服务的服务器能够访问OpenAI API（api.openai.com）。某些地区可能需要代理服务。

4. **题库域名**: 根据OCS文档说明，需要将题库配置中`homepage`以及`url`所涉及到的域名，在脚本头部元信息`@connect`中新增，否则无法请求到数据。