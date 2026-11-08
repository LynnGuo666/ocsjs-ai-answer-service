# EduBrain AI - 智能题库系统

这是一个基于Python和OpenAI API的新一代智能题库服务，专为[OCS (Online Course Script)](https://github.com/ocsjs/ocsjs)设计，可以通过AI自动回答题目。此服务实现了与OCS AnswererWrapper兼容的API接口，方便用户将AI能力整合到OCS题库搜索中。

## ⚠️ 重要提示

> [!IMPORTANT]  
> - 本项目仅供个人学习使用，不保证稳定性，且不提供任何技术支持。
> - 使用者必须在遵循 OpenAI 的[使用条款](https://openai.com/policies/terms-of-use)以及**法律法规**的情况下使用，不得用于非法用途。
> - 根据[《生成式人工智能服务管理暂行办法》](http://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm)的要求，请勿对中国地区公众提供一切未经备案的生成式人工智能服务。
> - 使用者应当遵守相关法律法规，承担相应的法律责任
> - 服务不对AI生成内容的准确性做出保证

## 功能特点

- 💡 **AI驱动**：使用OpenAI API生成智能回答
- 🔄 **OCS兼容**：完全兼容OCS的AnswererWrapper题库接口
- 🚀 **高性能**：内存缓存优化，快速响应请求
- 🔒 **安全可靠**：支持访问令牌验证，保护API调用
- 💬 **多种题型**：支持单选、多选、判断、填空等题型
- 📊 **数据统计**：实时监控服务状态和使用情况
- 🌐 **响应式UI**：支持多设备访问的现代化界面
- 📱 **移动友好**：完美适配手机和平板设备

## 系统要求

- Python 3.7+
- OpenAI API密钥（需要单独申请）

## 快速开始

### 1. 克隆代码库

```bash
git clone https://github.com/LynnGuo666/ocsjs-ai-answer-service.git
cd ocsjs-ai-answer-service
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

将`.env.example`复制为`.env`并填写必要的配置信息：

```bash
cp .env.example .env
```

编辑`.env`文件，至少需要填写OpenAI API密钥：

```
OPENAI_API_KEY=your_api_key_here
```

### 4. 启动服务

```bash
python app.py
```

服务将默认运行在`http://localhost:5000`

### 5. 在OCS中配置使用

在OCS的自定义题库配置中添加如下配置：

```json
[
  {
    "name": "AI智能题库",
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

> [!WARNING]
> `type` 必须是 `GM_xmlhttpRequest`（由油猴发请求），不能用默认的 `fetch`。很多网课站点（如智慧树考试页）的 CSP 里 `connect-src` 只允许自己的域名，页面 `fetch` 到 `localhost` 会在发请求前就被浏览器拒掉，控制台表现为 `TypeError: Failed to fetch`，与本题库服务无关。
> 使用 `GM_xmlhttpRequest` 需要在脚本头部的 `@connect` 中允许 `localhost`；原生脚本没有的话会弹授权框，或改装官方的[全域名通用版本](https://greasyfork.org/zh-CN/scripts/481438)。

> [!NOTE]
> **图片题 / 公式题支持**：OCS 新版开启「图片题优化」后，会把题目和选项里的图片转成 base64，通过 `images`、`suggestion_title`、`suggestion_options` 三个字段发送（只在 POST 且配置里引用了这些字段时才发送）。如果你还在用只有 title/type/options 的旧配置，OCS 会提示「当前题库配置暂不支持图片、公式等题目处理」，换成上面的新配置即可。
> - `images` 要用字段解析器 `{"handler": "return (env)=> env.images || []"}` 才能以数组形式提交；用 `"${images}"` 字符串占位符的话，数组会被拼成逗号分隔的字符串，服务端也做了兼容。
> - 图片题需要支持图片输入的模型。请在 `.env` 中设置 `VISION_MODEL`（例如 `gpt-4o-mini`），不设置时沿用 `OPENAI_MODEL`。
> - 图片由 OCS 在浏览器里转成 base64，服务端不会去下载原图链接，避免超星等站点防盗链导致的 403。
> - 如果正确选项本身是图片，模型会回答 `[图片N]`，OCS 会自动把它还原成对应的图片并匹配选项。

## API接口说明

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

## 部署建议

### 使用Gunicorn部署

对于生产环境，建议使用Gunicorn作为WSGI服务器：

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Docker部署

可以使用以下Dockerfile创建容器镜像：

```Dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

构建并运行Docker容器：

```bash
docker build -t ai-answer-service .
docker run -p 5000:5000 --env-file .env ai-answer-service
```

## 常见问题

### 1. AI答案准确性

AI生成的答案可能存在以下情况：
- 选项内容与原题不完全匹配
- 判断题答案可能不准确
- 填空题可能给出模糊或错误答案
- 多选题可能遗漏或多选

建议：
- 始终与原题选项进行对照
- 保持独立思考和判断
- 有疑问时以人工判断为准
- 将AI答案作为参考，而非唯一依据

### 2. 多选题答案格式

对于多选题，OCS期望的答案格式是用`#`分隔的选项，例如`A#B#C`。本服务已经处理了这个格式，会自动将OpenAI返回的多选答案转换为此格式。

### 2. API请求限制

注意OpenAI API有使用限制和费用。确保你的账户有足够的额度来处理预期的请求量。

### 3. 网络连接问题

确保部署此服务的服务器能够访问OpenAI API（api.openai.com）。某些地区可能需要代理服务。

### 4. 答题时每道题都报 `TypeError: Failed to fetch`

先检查题库配置里的 `type` 是否为 `GM_xmlhttpRequest`（默认的 `fetch` 会出这个问题）。

`fetch` 由页面发起，受网课站点 CSP 约束。智慧树考试页（`stuExamWeb`）的 CSP 中 `connect-src` 只列出自身域名：

```
connect-src 'self' *.zhihuishu.com c.dun.163yun.com ...
```

`localhost` 不在白名单内，浏览器会在请求发出之前就拒绝，控制台表现为：

```
Fetch API cannot load http://localhost:5000/api/search?...
Refused to connect because it violates the document's Content Security Policy.
```

OCS 捕获到的异常就是 `TypeError: Failed to fetch`。此时请求根本没有到达本服务，所以改服务端代码、增加 CORS 响应头都无效。

改用 `GM_xmlhttpRequest` 后请求由脚本管理器发起，不受页面 CSP 限制。该方式需要在脚本头部的 `@connect` 中允许 `localhost`（原生脚本会弹一次授权框），或改用官方的[全域名通用版本](https://greasyfork.org/zh-CN/scripts/481438)。

