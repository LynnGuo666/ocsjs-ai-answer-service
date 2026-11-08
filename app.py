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
import time
import logging
import openai
import json
from datetime import datetime

from config import Config
from utils import (SimpleCache, format_answer_for_ocs, parse_question_and_options, extract_answer,
                   normalize_images, build_user_content)

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

SYSTEM_PROMPT = (
    "你是一个专业的考试答题助手。请直接回答答案，不要解释。"
    "选择题只回答选项的内容(如：地球)；多选题用#号分隔答案,只回答选项的内容(如中国#世界#地球)；"
    "判断题只回答: 正确/对/true/√ 或 错误/错/false/×；填空题直接给出答案。"
    "题目或选项中的 [图片N] 表示随消息附带的第N张图片（按顺序编号），请结合图片内容作答；"
    "若正确选项本身是图片，直接回答该占位符（如 [图片2]）。"
)

def verify_access_token(request):
    """验证访问令牌（如果配置了的话）"""
    if Config.ACCESS_TOKEN:
        token = request.headers.get('X-Access-Token') or request.args.get('token')
        if not token or token != Config.ACCESS_TOKEN:
            return False
    return True

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
    
    # 验证访问令牌（如果配置了的话）
    if not verify_access_token(request):
        return jsonify({
            'code': 0,
            'msg': '无效的访问令牌'
        }), 403
    
    try:
        # 根据请求方法获取问题内容
        images = []
        suggestion_title = ''
        suggestion_options = ''
        if request.method == 'GET':
            question = request.args.get('title', '')
            question_type = request.args.get('type', '')
            options = request.args.get('options', '')
        else:  # POST
            content_type = request.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                data = request.get_json(silent=True) or {}
                question = data.get('title', '') or ''
                question_type = data.get('type', '') or ''
                options = data.get('options', '') or ''
                # OCS 图片题优化（v2 题库配置）新增字段
                images = normalize_images(data.get('images'))
                suggestion_title = data.get('suggestion_title', '') or ''
                suggestion_options = data.get('suggestion_options', '') or ''
            else:
                # 处理表单数据
                question = request.form.get('title', '')
                question_type = request.form.get('type', '')
                options = request.form.get('options', '')
        
        if len(images) > Config.MAX_IMAGES:
            logger.warning(f"图片数量 {len(images)} 超过上限 {Config.MAX_IMAGES}，仅保留前 {Config.MAX_IMAGES} 张")
            images = images[:Config.MAX_IMAGES]
        
        # 记录接收到的问题
        logger.info(f"接收到问题: '{question[:50]}...' (类型: {question_type}, 图片: {len(images)}张)")
        
        # 如果没有提供问题，返回错误
        if not question:
            logger.warning("未提供问题内容")
            return jsonify({
                'code': 0,
                'msg': '未提供问题内容'
            })
        
        # 检查缓存中是否有此问题的答案
        if Config.ENABLE_CACHE:
            cached_answer = cache.get(question, question_type, options, images)
            if cached_answer:
                logger.info(f"从缓存获取答案 (耗时: {time.time() - start_time:.2f}秒)")
                return jsonify(format_answer_for_ocs(question, cached_answer))
        
        # 构建发送给OpenAI的提示
        # 有图片时使用 [图片N] 占位符版本的题目/选项（不含长 URL），并以多模态消息发送
        if images:
            prompt = parse_question_and_options(
                suggestion_title or question,
                suggestion_options or options,
                question_type,
                image_count=len(images)
            )
            model = Config.VISION_MODEL or Config.OPENAI_MODEL
        else:
            prompt = parse_question_and_options(question, options, question_type)
            model = Config.OPENAI_MODEL
        
        # 调用OpenAI API
        response = client.chat.completions.create(
            model=model,
            temperature=Config.TEMPERATURE,
            max_tokens=Config.MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_content(prompt, images)}
            ]
        )
        
        # 获取AI生成的答案
        ai_answer = response.choices[0].message.content.strip()
        
        # 处理答案格式
        processed_answer = extract_answer(ai_answer, question_type)
        
        # 保存到缓存
        if Config.ENABLE_CACHE:
            cache.set(question, processed_answer, question_type, options, images)
        
        # 保存问答记录
        current_time = datetime.now()
        qa_records.append({
            'time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'timestamp': current_time.isoformat(),
            'question': question,
            'type': question_type,
            'options': options,
            'images': len(images),
            'answer': processed_answer
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
    # 验证访问令牌
    if not verify_access_token(request):
        return jsonify({
            'success': False,
            'message': '无效的访问令牌'
        }), 403
    
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
    # 验证访问令牌
    if not verify_access_token(request):
        return jsonify({
            'success': False,
            'message': '无效的访问令牌'
        }), 403
    
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