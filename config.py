# -*- coding: utf-8 -*-
"""
配置文件
"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 基础配置
class Config:
    # 服务配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # OpenAI配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
    # OpenAI API Base URL，如果不设置则使用默认值
    OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
    # 图片题使用的多模态模型，不设置则沿用 OPENAI_MODEL（此时 OPENAI_MODEL 需支持图片输入）
    VISION_MODEL = os.getenv("VISION_MODEL", "")
    # 单题最多发送给模型的图片数量
    MAX_IMAGES = int(os.getenv("MAX_IMAGES", 10))
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # 安全配置（可选）
    # API_KEYS: 允许访问的 API Key，多个用英文逗号分隔；ACCESS_TOKEN 为旧配置名，仍然兼容
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", None)
    API_KEYS = [
        k.strip()
        for k in (os.getenv("API_KEYS", "") + "," + (ACCESS_TOKEN or "")).split(",")
        if k.strip()
    ]
    
    # 响应配置
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", 500))
    TEMPERATURE = float(os.getenv("TEMPERATURE", 0.7))
    
    # 缓存配置
    ENABLE_CACHE = os.getenv("ENABLE_CACHE", "True").lower() == "true"
    CACHE_EXPIRATION = int(os.getenv("CACHE_EXPIRATION", 86400))  # 默认缓存24小时