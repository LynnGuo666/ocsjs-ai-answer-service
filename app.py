# -*- coding: utf-8 -*-
"""
EduBrain AI - 智能题库系统
基于 OpenAI API 的智能题库服务，提供兼容 OCS 接口的智能答题功能
作者：Lynn
版本：1.1.0
"""
from flask import Flask, request, jsonify, make_response, render_template
from flask_cors import CORS
import os
import hmac
import time
import hashlib
import base64
import re
import logging
import httpx
import openai
import json
from datetime import datetime

from config import Config
from utils import SimpleCache, format_answer_for_ocs, parse_question_and_options, extract_answer

# 配置日志
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ai_answer_service')

# 初始化应用
app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 初始化缓存
cache = SimpleCache(Config.CACHE_EXPIRATION) if Config.ENABLE_CACHE else None

# 验证OpenAI API密钥
if not Config.OPENAI_API_KEY:
    logger.critical("未设置OpenAI API密钥，请在.env文件中配置OPENAI_API_KEY")
    raise ValueError("请设置环境变量OPENAI_API_KEY")

# 初始化OpenAI客户端
client = openai.OpenAI(
    api_key=Config.OPENAI_API_KEY,
    base_url=Config.OPENAI_API_BASE
)

# 问答记录存储（实际应用中可以使用数据库）
qa_records = []
MAX_RECORDS = 100  # 最多保存100条记录
start_time = time.time()

# 题目图片字段别名（OCS 侧或自建客户端可任选其一传入）
IMAGE_FIELDS = ('image', 'images', 'img', 'image_url', 'image_base64')
# 图片归一化后的字符上限（base64 约 8MB，原图约 6MB）
MAX_IMAGE_CHARS = 8 * 1024 * 1024


def _first_nonempty(src, fields):
    """从 dict / MultiDict 中按顺序取第一个非空的图片字段。"""
    for field in fields:
        value = src.get(field)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            items = [str(v).strip() for v in value if str(v).strip()]
            if items:
                return items
            continue
        value = str(value).strip()
        if value:
            return value
    return ''


def normalize_image(value):
    """把图片统一成可直接交给 OpenAI 的 url 形式。

    支持三种写法：
      1. data:image/png;base64,xxx  -> 原样使用
      2. http(s)://example.com/a.png -> 原样使用
      3. 裸 base64                   -> 按文件头补 data:image 前缀
    """
    if not value:
        return ''
    v = value.strip()
    if v.startswith('data:image'):
        return v
    if v.startswith(('http://', 'https://')):
        return v
    head = v[:12]
    if head.startswith('/9j/'):
        mime = 'image/jpeg'
    elif head.startswith('R0lGOD'):
        mime = 'image/gif'
    elif head.startswith('UklGR'):
        mime = 'image/webp'
    else:
        mime = 'image/png'
    return 'data:%s;base64,%s' % (mime, v)

# 题干/选项里内联出现的图片地址（OCS 常见做法：把 <img> 的 src 直接拼进标题）
_IMAGE_URL_RE = re.compile(
    r'https?://[^\s"\'<>()\u4e00-\u9fff]+?\.(?:png|jpe?g|gif|webp|bmp)(?:\?[^\s"\'<>]*)?',
    re.I)
MAX_IMAGES = Config.MAX_IMAGES      # 单次请求最多处理张数（.env 的 MAX_IMAGES）
MAX_IMAGE_BYTES = 6 * 1024 * 1024  # 单张原图字节上限
DOWNLOAD_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


def split_image_items(raw):
    """把请求里的图片字段拆成列表。

    兼容三种来源：
      1. 数组（OCS 字段解析器 {"handler": "return (env)=> env.images"}）
      2. JSON 字符串形式的数组
      3. "${images}" 占位符被拼成的字符串 —— 数组用逗号连接，
         而 data URL 内部本身含逗号，因此按 ",data:" 边界切分
    """
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith('['):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except ValueError:
            pass
    parts = re.split(r',(?=data:[A-Za-z]+/)', text)
    return [p.strip() for p in parts if p.strip()]


def extract_image_urls(*texts):
    """从题干/选项文本中抽取内联图片地址，按出现顺序去重。"""
    found = []
    for text in texts:
        if not text:
            continue
        for match in _IMAGE_URL_RE.finditer(str(text)):
            url = match.group(0)
            if url not in found:
                found.append(url)
    return found


def fetch_image_as_data_url(url):
    """服务端下载图片并转成 data URL，失败返回空串。

    部分图床（如超星 p.ananas.chaoxing.com）对不带 UA 的请求直接返回 403，
    必须带浏览器 UA 才能取到图。
    """
    try:
        with httpx.Client(timeout=15, follow_redirects=True,
                          headers={'User-Agent': DOWNLOAD_UA,
                                   'Referer': 'https://mooc1.chaoxing.com/'}) as cli:
            resp = cli.get(url)
        if resp.status_code != 200:
            logger.warning('图片下载失败 %s -> HTTP %s' % (url, resp.status_code))
            return ''
        data = resp.content
        if not data or len(data) > MAX_IMAGE_BYTES:
            logger.warning('图片为空或过大 %s (%d 字节)' % (url, len(data)))
            return ''
        ctype = (resp.headers.get('content-type') or '').split(';')[0].strip().lower()
        if not ctype.startswith('image/'):
            ctype = 'image/png'
        return 'data:%s;base64,%s' % (ctype, base64.b64encode(data).decode())
    except Exception as e:
        logger.warning('图片下载异常 %s: %s' % (url, e))
        return ''


def _extract_api_key(req):
    """从请求中提取 API Key：X-API-Key / Authorization Bearer / ?api_key=。"""
    api_key = (req.headers.get("X-API-Key") or "").strip()
    if not api_key:
        authorization = (req.headers.get("Authorization") or "").strip()
        if authorization.lower().startswith("bearer "):
            api_key = authorization[7:].strip()
    if not api_key:
        api_key = (req.args.get("api_key") or "").strip()
    return api_key


def verify_api_key(req):
    """校验固定 API Key，使用常量时间比较避免时序侧信道。"""
    supplied = _extract_api_key(req)
    return bool(supplied) and hmac.compare_digest(supplied, Config.API_KEY)


@app.before_request
def require_api_key():
    """统一保护 /api/*：仅 /api/health 公开，并放行 CORS 预检。"""
    if request.method == "OPTIONS":
        return None
    protected = request.path.startswith("/api/") and request.path != "/api/health"
    if request.path == "/dashboard":
        protected = True
    if protected and not verify_api_key(request):
        return jsonify({
            "code": 0,
            "msg": "无效的 API Key"
        }), 401
    return None

@app.route('/api/search', methods=['GET', 'POST'])
def search():
    """
    处理OCS发送的搜索请求，使用OpenAI API生成答案
    GET请求: 从URL参数获取问题
    POST请求: 从请求体获取问题
    
    参数:
        title: 问题内容
        type: 问题类型 (single-单选, multiple-多选, judgement-判断, completion-填空)
        options: 选项内容
        
    返回:
        成功: {'code': 1, 'question': '问题', 'answer': 'AI生成的答案'}
        失败: {'code': 0, 'msg': '错误信息'}
    """
    start_time = time.time()
    
    try:
        # 统一取出请求参数（GET / JSON / 表单三种来源）
        if request.method == 'GET':
            src = request.args
        else:
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                src = request.get_json(silent=True) or {}
            else:
                src = request.form

        question = src.get('title', '') or ''
        question_type = src.get('type', '') or ''
        options = src.get('options', '') or ''
        raw_image = _first_nonempty(src, IMAGE_FIELDS)
        # OCS 可选：通过字段解析器提供的 OCR 建议文本，有则优先用于组 prompt
        suggestion_title = str(src.get('suggestion_title') or '').strip()
        suggestion_options = str(src.get('suggestion_options') or '').strip()

        # ===== 收集题目图片 =====
        # 1) 显式图片字段（images / image / img / image_url / image_base64，支持单张或多张）
        explicit = split_image_items(raw_image)
        # 2) OCS 常把图片地址直接拼在题干文本里，必须一并抽出来，
        #    否则模型只能看到一串链接、看不到图，会返回空答案
        inline = extract_image_urls(question, options, suggestion_title, suggestion_options)

        images = []
        for item in list(explicit) + inline:
            if not item or item in images:
                continue
            if len(images) >= MAX_IMAGES:
                break
            norm = normalize_image(item)
            # http(s) 图片统一在服务端下载成 base64，避免网关/模型抓不到
            if norm.startswith(('http://', 'https://')):
                fetched = fetch_image_as_data_url(norm)
                if fetched:
                    logger.info('已下载题目图片: %s (%d 字符)' % (norm[:80], len(fetched)))
                    norm = fetched
                else:
                    logger.warning('图片下载失败，降级为直接传 URL: %s' % norm[:80])
            if len(norm) > MAX_IMAGE_CHARS:
                logger.warning('单张图片过大已跳过 (%d 字符)' % len(norm))
                continue
            images.append(norm)
        
        # 记录接收到的问题
        logger.info(f"接收到问题: '{question[:50]}...' (类型: {question_type}, 图片: {len(images)} 张)")
        
        # 题干（含 OCR 建议文本）和图片都为空才算无效请求
        if not question and not suggestion_title and not images:
            logger.warning("未提供问题内容")
            return jsonify({
                'code': 0,
                'msg': '未提供问题内容'
            })
        
        # 检查缓存中是否有此问题的答案
        if Config.ENABLE_CACHE:
            image_sig = hashlib.md5('|'.join(images).encode('utf-8')).hexdigest()[:16] if images else ''
            key_question = suggestion_title or question
            key_options = suggestion_options or options
            cached_answer = cache.get(key_question, question_type, key_options, image_sig)
            if cached_answer:
                logger.info(f"从缓存获取答案 (耗时: {time.time() - start_time:.2f}秒)")
                return jsonify(format_answer_for_ocs(question, cached_answer))
        
        # 构建发送给OpenAI的提示
        # OCS 若传了 suggestion_title / suggestion_options（OCR 结果），优先使用
        prompt_question = suggestion_title or question
        prompt_options = suggestion_options or options
        prompt = parse_question_and_options(prompt_question, prompt_options, question_type)
        if images:
            prompt += "\n（题目附带 %d 张图片，请结合图片中的公式、数字和文字作答。）" % len(images)
        
        # 有图片时构造多模态消息（text + 若干 image_url），否则保持纯文本
        if images:
            user_content = [{"type": "text", "text": prompt}]
            for img in images:
                user_content.append({"type": "image_url", "image_url": {"url": img}})
        else:
            user_content = prompt

        # 调用OpenAI API
        messages = [
            {"role": "system", "content": "你是一个专业的考试答题助手。请直接回答答案，不要解释。选择题只回答选项的内容(如：地球)；多选题用#号分隔答案,只回答选项的内容(如中国#世界#地球)；判断题只回答: 正确/对/true/√ 或 错误/错/false/×；填空题直接给出答案，若有多个空请按顺序用#分隔。"},
            {"role": "user", "content": user_content}
        ]

        # 推理模型有时会把 token 全花在 reasoning 上、最终 content 为空
        # （finish_reason=length）。空答案时抬高上限重试一次，仍为空才放弃。
        ai_answer = ''
        finish_reason = ''
        token_limits = [Config.MAX_TOKENS]
        if Config.MAX_TOKENS < 32000:
            token_limits.append(min(Config.MAX_TOKENS * 2, 32000))

        for attempt, limit in enumerate(token_limits, 1):
            response = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                temperature=Config.TEMPERATURE,
                max_tokens=limit,
                messages=messages
            )
            choice = response.choices[0]
            finish_reason = getattr(choice, 'finish_reason', '') or ''
            ai_answer = (choice.message.content or '').strip()
            if ai_answer:
                if attempt > 1:
                    logger.info('重试成功（第 %d 次，max_tokens=%d）' % (attempt, limit))
                break
            logger.warning('第 %d/%d 次调用未拿到答案 (finish_reason=%s, max_tokens=%d)'
                           % (attempt, len(token_limits), finish_reason, limit))

        if not ai_answer:
            logger.warning('模型返回空答案（题型: %s, 图片: %d 张, finish_reason=%s）'
                           % (question_type, len(images), finish_reason))
            return jsonify({
                'code': 0,
                'msg': 'AI 未返回有效答案（可能思考超限），已跳过避免填入空值'
            })
        
        # 处理答案格式
        processed_answer = extract_answer(ai_answer, question_type)
        
        # 保存到缓存
        if Config.ENABLE_CACHE:
            cache.set(key_question, processed_answer, question_type, key_options, image_sig)
        
        # 保存问答记录
        current_time = datetime.now()
        qa_records.append({
            'time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': current_time.isoformat(),
            'question': question,
            'type': question_type,
            'options': options,
            'answer': processed_answer,
            'has_image': bool(images),
            'images_count': len(images)
        })
        if len(qa_records) > MAX_RECORDS:
            qa_records.pop(0)
        
        # 记录处理时间
        process_time = time.time() - start_time
        logger.info(f"问题处理完成 (耗时: {process_time:.2f}秒)")
        
        # 返回符合OCS格式的响应
        return jsonify(format_answer_for_ocs(question, processed_answer))
    
    except Exception as e:
        # 记录异常
        logger.error(f"处理问题时发生错误: {str(e)}", exc_info=True)
        
        # 捕获所有异常并返回错误信息
        return jsonify({
            'code': 0,
            'msg': f'发生错误: {str(e)}'
        })

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'message': 'AI题库服务运行正常',
        'version': '1.0.0',
        'cache_enabled': Config.ENABLE_CACHE,
        'model': Config.OPENAI_MODEL
    })

@app.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """清除缓存接口"""
    if not Config.ENABLE_CACHE:
        return jsonify({
            'success': False,
            'message': '缓存未启用'
        })
    
    cache.clear()
    return jsonify({
        'success': True,
        'message': '缓存已清除'
    })

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取服务统计信息"""
    stats = {
        'version': '1.0.0',
        'uptime': time.time() - start_time,
        'model': Config.OPENAI_MODEL,
        'cache_enabled': Config.ENABLE_CACHE,
        'cache_size': len(cache.cache) if Config.ENABLE_CACHE else 0,
        'qa_records_count': len(qa_records)
    }
    
    return jsonify(stats)

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """仪表盘 - 显示问答记录和系统状态"""
    uptime_seconds = time.time() - start_time
    days = int(uptime_seconds // 86400)
    hours = int((uptime_seconds % 86400) // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{days}天{hours}小时{minutes}分钟"
    
    return render_template(
        'dashboard.html',
        version="1.1.0",
        cache_enabled=Config.ENABLE_CACHE,
        cache_size=len(cache.cache) if Config.ENABLE_CACHE else 0,
        model=Config.OPENAI_MODEL,
        uptime=uptime_str,
        records=qa_records
    )

@app.route('/', methods=['GET'])
def index():
    """首页 - 显示Web界面"""
    return render_template('index.html')

@app.route('/docs', methods=['GET'])
def docs():
    """API文档页面"""
    with open('api_docs.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 使用markdown库将文档转换为HTML（需要安装：pip install markdown）
    try:
        import markdown
        html_content = markdown.markdown(content, extensions=['tables'])
        
        return f"""
        <html>
            <head>
                <title>AI题库服务 - API文档</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1, h2, h3 {{ color: #2c3e50; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    code {{ background: #e0e0e0; padding: 2px 4px; border-radius: 3px; }}
                    pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                    table {{ border-collapse: collapse; width: 100%; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; }}
                    th {{ background-color: #f4f4f4; }}
                </style>
            </head>
            <body>
                <div class="container">
                    {html_content}
                </div>
            </body>
        </html>
        """
    except ImportError:
        # 如果没有安装markdown库，则返回纯文本
        return f"""
        <html>
            <head>
                <title>AI题库服务 - API文档</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1 {{ color: #333; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    pre {{ background: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>AI题库服务 - API文档</h1>
                    <pre>{content}</pre>
                </div>
            </body>
        </html>
        """

if __name__ == '__main__':
    # 开启应用
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)