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
    "method": "get",
    "type": "GM_xmlhttpRequest",
    "contentType": "json",
    "data": {
      "title": "${title}",
      "type": "${type}",
      "options": "${options}"
    },
    "handler": "return (res)=> res.code === 1 ? [res.question, res.answer] : [res.msg, undefined]"
  }
]
```

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

如果你想增加安全性，可以在`.env`文件中设置访问令牌：

```
ACCESS_TOKEN=your_secret_token_here
```

设置后，所有API请求都需要包含此令牌，可以通过以下两种方式之一传递：

1. HTTP头部: `X-Access-Token: your_secret_token_here`
2. URL参数: `?token=your_secret_token_here`

## 部署建议

### 使用Gunicorn部署

对于生产环境，建议使用Gunicorn作为WSGI服务器：

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 使用Docker部署

可以使用以下Dockerfile创建容器镜像：

```Dockerfile
FROM python:3.9-slim

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

