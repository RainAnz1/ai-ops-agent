import requests

def analyze_error(logs):
    prompt = f"分析以下服务器日志并给出错误类型：\n{logs}"

    # 这里你可以接 OpenAI / OpenClaw
    # 简化版：
    response = requests.post("你的API地址", json={
        "prompt": prompt
    })

    return response.text
