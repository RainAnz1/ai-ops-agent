from log_parser import get_logs
from analyzer import analyze_error
from fixer import generate_fix
from executor import execute_command

def main():
    print("=== AI 运维 Agent ===")
    service = input("请输入要排查的服务 (nginx/docker/system): ")

    logs = get_logs(service)
    print("\n[日志提取完成]\n")

    error_type = analyze_error(logs)
    print(f"[识别错误类型]: {error_type}\n")

    fix = generate_fix(error_type)
    print("[修复建议]:")
    print(fix)

    choice = input("\n是否执行修复命令？(y/n): ")
    if choice == 'y':
        execute_command(fix)

if __name__ == "__main__":
    main()
