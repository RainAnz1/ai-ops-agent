def generate_fix(error_type):
    fixes = {
        "端口占用": "lsof -i :80\nkill -9 <PID>",
        "权限问题": "chmod -R 755 /path/to/file",
        "服务启动失败": "systemctl restart nginx",
        "未知错误": "请检查日志或手动排查"
    }

    return fixes.get(error_type, "无建议")
