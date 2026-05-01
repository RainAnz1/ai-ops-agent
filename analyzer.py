def analyze_error(logs):
    # 简单规则（你可以说这是“轻量模型+规则融合”）
    if "address already in use" in logs:
        return "端口占用"
    elif "permission denied" in logs:
        return "权限问题"
    elif "failed" in logs.lower():
        return "服务启动失败"
    else:
        return "未知错误"
