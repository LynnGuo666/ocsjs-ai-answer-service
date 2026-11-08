# -*- coding: utf-8 -*-
"""
配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 基础配置
class Config:
    # 服务配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 6000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # OpenAI配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
    # OpenAI API Base URL，如果不设置则使用默认值
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', '')
    
    # 图片配置：单次请求最多处理张数
    MAX_IMAGES = int(os.getenv("MAX_IMAGES", "10"))

    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # API 鉴权（按需求固定写死，不读取环境变量）
    API_KEY  = os.getenv("API_KEYS","")

    # 旧版可选访问令牌（保留配置项，实际鉴权统一使用 API_KEY）
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", None)
    
    # 响应配置
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1000))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    
    # 缓存配置
    ENABLE_CACHE = os.getenv("ENABLE_CACHE", "True").lower() == "true"
    CACHE_EXPIRATION = int(os.getenv("CACHE_EXPIRATION", 86400))  # 默认缓存24小时