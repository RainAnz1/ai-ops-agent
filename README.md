# AI Ops Agent

一个轻量级服务器日志分析与安全巡检助手，用于快速查看 Nginx、Docker、systemd 或自定义日志，识别常见故障类型，并生成可执行前可审查的排障建议。

## 特性

- 支持 `nginx`、`docker`、`system`、`file`、`stdin` 五种日志来源
- 内置常见运维故障规则：端口占用、权限问题、磁盘空间不足、OOM、配置语法错误、网络异常、服务启动失败
- 可选接入外部 AI 分析接口，未配置时自动回退到本地规则
- 默认只预览巡检命令，避免误执行 `kill`、`restart`、`rm` 等高风险操作
- 使用结构化分析结果和修复计划，便于后续扩展规则或接入平台

## 环境要求

- Python 3.10+
- 可选：`requests`，仅在启用外部 AI 接口时需要
- 按需安装本机巡检工具：`journalctl`、`docker`、`nginx`、`lsof`、`ss` 等

## 快速开始

```bash
git clone https://github.com/RainAnz1/ai-ops-agent.git
cd ai-ops-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --service system
```

默认情况下，程序只会输出日志片段、分析结果、修复建议和巡检命令预览，不会真的执行命令。

## 使用示例

分析 systemd 最近日志：

```bash
python main.py --service system --lines 120
```

分析 Nginx 错误日志：

```bash
python main.py --service nginx
```

指定日志文件：

```bash
python main.py --service file --log-file /var/log/nginx/error.log --lines 200
```

查看 Docker 容器日志：

```bash
python main.py --service docker --container my-container --lines 100
```

从管道读取日志：

```bash
tail -n 200 /var/log/nginx/error.log | python main.py --service stdin
```

确认后执行安全巡检命令：

```bash
python main.py --service system --execute
```

## 可选 AI 接口

如果你有自己的 AI 网关，可以通过环境变量启用：

```bash
export AI_OPS_API_URL="https://your-ai-gateway.example.com/analyze"
export AI_OPS_API_TIMEOUT=15
python main.py --service file --log-file ./error.log --ai
```

接口会收到如下 JSON：

```json
{
  "prompt": "请分析以下服务器日志...",
  "logs": "日志内容"
}
```

推荐接口返回 JSON：

```json
{
  "issue_type": "端口占用",
  "severity": "high",
  "summary": "服务监听 80 端口失败，因为端口已被占用。",
  "evidence": ["bind() to 0.0.0.0:80 failed (98: Address already in use)"],
  "confidence": 0.92
}
```

如果 AI 接口不可用，程序会自动使用本地规则继续分析。

## 安全策略

项目不会把修复建议直接当 shell 脚本运行。即使传入 `--execute`，执行器也会：

- 阻止包含 shell 操作符的命令，例如 `;`、`&&`、`|`、反引号和命令替换
- 阻止包含 `<PID>`、`{service}` 等占位符的命令
- 阻止 `systemctl restart/stop/start`、`docker rm/kill/restart` 等修改类操作
- 只允许白名单内的巡检命令，例如 `journalctl`、`systemctl status`、`docker ps`、`df`、`ss`、`lsof`

真正会改变系统状态的操作，应在确认根因后由运维人员手动执行。

## 开发

运行语法检查：

```bash
python3 -m py_compile main.py analyzer.py log_parser.py fixer.py executor.py
```

运行测试：

```bash
python3 -m unittest discover -s tests
```

## 项目结构

```text
.
├── analyzer.py      # 日志分析：可选 AI + 本地规则兜底
├── executor.py      # 安全巡检命令执行器
├── fixer.py         # 修复计划生成
├── log_parser.py    # 日志采集
├── main.py          # CLI 入口
├── requirements.txt
└── tests/
```

## 后续可扩展方向

- 增加更多服务规则，例如 MySQL、Redis、Kubernetes、Caddy
- 将分析结果输出为 JSON，方便接入告警平台或工单系统
- 给规则增加权重、标签和更细的服务识别
- 支持远程主机采集，但需要先设计 SSH 凭据和命令审计策略
