# -*- coding: utf-8 -*-
"""
测试脚本
用于测试AI题库服务是否正常工作
"""
import requests
import json
import sys
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 服务URL
SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:5999")
# 鉴权密钥（与 .env 的 API_KEYS 一致）
API_KEY = os.getenv("API_KEYS", "")
HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

def test_health():
    """测试健康检查接口"""
    print("测试健康检查接口...")
    try:
        response = requests.get(f"{SERVICE_URL}/api/health", headers=HEADERS)
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print("健康检查接口测试成功！\n")
        return True
    except Exception as e:
        print(f"健康检查接口测试失败: {str(e)}")
        return False

def test_search(question, question_type=None, options=None):
    """测试搜索接口"""
    print(f"测试搜索接口: {question}")
    
    params = {
        "title": question
    }
    
    if question_type:
        params["type"] = question_type
        
    if options:
        params["options"] = options
    
    try:
        print("发送请求...")
        print(f"参数: {json.dumps(params, indent=2, ensure_ascii=False)}")
        
        response = requests.get(f"{SERVICE_URL}/api/search", params=params, headers=HEADERS)
        
        print(f"状态码: {response.status_code}")
        result = response.json()
        print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
        
        if result.get("code") == 1:
            print("搜索接口测试成功！\n")
            return True
        else:
            print(f"搜索接口测试失败: {result.get('msg', '未知错误')}\n")
            return False
    except Exception as e:
        print(f"搜索接口测试失败: {str(e)}\n")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("AI题库服务测试脚本")
    print("=" * 50)
    
    # 测试健康检查接口
    if not test_health():
        print("健康检查失败，请确认服务是否正常运行。")
        sys.exit(1)
    
    # 测试单选题
    test_search(
        "中国的首都是哪个城市？", 
        "single",
        "A. 上海\nB. 北京\nC. 广州\nD. 深圳"
    )
    
    # 测试多选题
    test_search(
        "以下哪些是中国的一线城市？", 
        "multiple",
        "A. 北京\nB. 上海\nC. 广州\nD. 深圳\nE. 成都\nF. 杭州"
    )
    
    # 测试判断题
    test_search(
        "地球是太阳系中第三颗行星。", 
        "judgement"
    )
    
    # 测试填空题
    test_search(
        "《红楼梦》的作者是_______。", 
        "completion"
    )
    
    print("=" * 50)
    print("测试完成！")
    print("=" * 50)

if __name__ == "__main__":
    main()