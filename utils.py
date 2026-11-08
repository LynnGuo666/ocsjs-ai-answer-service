# -*- coding: utf-8 -*-
"""
工具函数模块
包含缓存管理、答案处理和OpenAI API调用等辅助功能
"""
import json
import time
import os
import hashlib
import re
from typing import Dict, Any, Optional, Tuple, List

class SimpleCache:
    """简单的内存缓存实现"""
    
    def __init__(self, expiration_seconds: int = 86400):
        """
        初始化缓存
        
        Args:
            expiration_seconds: 缓存过期时间（秒），默认24小时
        """
        self.cache = {}
        self.expiration = expiration_seconds
    
    def _generate_key(self, question: str, question_type: str, options: str, images: Optional[List[str]] = None) -> str:
        """
        根据问题内容生成缓存键
        
        Args:
            question: 问题内容
            question_type: 问题类型
            options: 选项内容
            
        Returns:
            str: 缓存键
        """
        # 使用问题内容、类型和选项的组合生成哈希键
        content = f"{question}|{question_type}|{options}"
        # 图片题：文本相同但图片不同的题目不能共用缓存
        if images:
            content += "|" + "|".join(hashlib.md5(img.encode('utf-8')).hexdigest() for img in images)
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get(self, question: str, question_type: str = "", options: str = "", images: Optional[List[str]] = None) -> Optional[str]:
        """
        从缓存获取答案
        
        Args:
            question: 问题内容
            question_type: 问题类型
            options: 选项内容
            
        Returns:
            Optional[str]: 缓存的答案，如果不存在或已过期则返回None
        """
        key = self._generate_key(question, question_type, options, images)
        if key in self.cache:
            timestamp, value = self.cache[key]
            # 检查缓存是否过期
            if time.time() - timestamp < self.expiration:
                return value
            # 缓存已过期，删除
            del self.cache[key]
        return None
    
    def set(self, question: str, answer: str, question_type: str = "", options: str = "", images: Optional[List[str]] = None) -> None:
        """
        设置缓存
        
        Args:
            question: 问题内容
            answer: 答案内容
            question_type: 问题类型
            options: 选项内容
        """
        key = self._generate_key(question, question_type, options, images)
        self.cache[key] = (time.time(), answer)
    
    def clear(self) -> None:
        """清空所有缓存"""
        self.cache.clear()
    
    def remove_expired(self) -> int:
        """
        删除所有过期的缓存项
        
        Returns:
            int: 删除的缓存项数量
        """
        now = time.time()
        expired_keys = [
            key for key, (timestamp, _) in self.cache.items() 
            if now - timestamp >= self.expiration
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)


def format_answer_for_ocs(question: str, answer: str) -> Dict[str, Any]:
    """
    格式化答案为OCS期望的格式
    
    Args:
        question: 问题内容
        answer: 答案内容
        
    Returns:
        Dict[str, Any]: 格式化后的响应
    """
    return {
        'code': 1,
        'question': question,
        'answer': answer
    }


def normalize_images(raw: Any) -> List[str]:
    """
    规范化 OCS 图片题优化传入的 images 字段

    OCS 推荐用字段解析器 {"handler": "return (env)=> env.images"} 传数组；
    若用 "${images}" 字符串占位符，数组会被 JS 拼成逗号分隔的字符串（data URL 内部也含逗号），
    这里按 "data:" 前缀重新切分以兼容。

    Returns:
        List[str]: data URL 或 http(s) URL 列表
    """
    if not raw:
        return []
    if isinstance(raw, str):
        raw = raw.strip()
        if raw.startswith('['):
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
    if isinstance(raw, str):
        parts = re.split(r',(?=data:)', raw)
    elif isinstance(raw, list):
        parts = raw
    else:
        return []
    result = []
    for item in parts:
        if not isinstance(item, str):
            continue
        item = item.strip()
        if item.startswith('data:image/') or item.startswith('http://') or item.startswith('https://'):
            result.append(item)
    return result


def build_user_content(prompt: str, images: Optional[List[str]] = None):
    """
    构建 user 消息 content：无图片时为纯文本，有图片时为 OpenAI 多模态数组
    """
    if not images:
        return prompt
    content = [{"type": "text", "text": prompt}]
    for i, url in enumerate(images, 1):
        content.append({"type": "text", "text": f"[图片{i}]"})
        content.append({"type": "image_url", "image_url": {"url": url}})
    return content


def parse_question_and_options(question: str, options: str, question_type: str, image_count: int = 0) -> str:
    """
    解析问题和选项，为OpenAI API构建更好的提示
    
    Args:
        question: 问题内容
        options: 选项内容
        question_type: 问题类型（单选、多选、判断、填空）
        
    Returns:
        str: 格式化后的提示
    """
    prompt = f"问题: {question}\n"
    
    # 添加题目类型提示
    type_prompts = {
        "single": "这是一道单选题。",
        "multiple": "这是一道多选题，答案请用#符号分隔。",
        "judgement": "这是一道判断题，需要回答：正确/对/true/√ 或者 错误/错/false/×。",
        "completion": "这是一道填空题。"
    }
    
    if question_type in type_prompts:
        prompt += f"{type_prompts[question_type]}\n"
    
    if options:
        prompt += f"选项:\n{options}\n"
    
    if image_count:
        prompt += f"题目附带 {image_count} 张图片，文中的 [图片N] 对应第N张图片。若答案选项为图片，请回答对应的 [图片N]。\n"
    
    prompt += "请直接给出答案，不要解释。"
    return prompt


def extract_answer(ai_response: str, question_type: str) -> str:
    """
    从AI响应中提取答案
    
    Args:
        ai_response: AI生成的完整响应
        question_type: 问题类型
        
    Returns:
        str: 提取的答案部分
    """
    # 对于多选题，确保答案格式正确（使用#分隔）
    if question_type == "multiple":
        # 尝试从响应中找出选项部分
        lines = ai_response.split('\n')
        for line in lines:
            # 寻找可能的答案行（包含选项标识如A、B、C、D）
            if any(opt in line.upper() for opt in ['A', 'B', 'C', 'D']) and '#' not in line:
                # 提取所有出现的选项
                options = [opt for opt in ['A', 'B', 'C', 'D', 'E', 'F'] if opt in line.upper()]
                # 将它们用#连接
                answer = '#'.join(options)
                return answer
    
    # 默认返回完整响应
    return ai_response