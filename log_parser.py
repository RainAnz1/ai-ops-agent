import subprocess

def get_logs(service):
    if service == "nginx":
        cmd = "tail -n 50 /var/log/nginx/error.log"
    elif service == "docker":
        cmd = "docker ps -a"
    elif service == "system":
        cmd = "journalctl -xe --no-pager | tail -n 50"
    else:
        return "未知服务"

    try:
        result = subprocess.check_output(cmd, shell=True, text=True)
        return result
    except Exception as e:
        return str(e)
