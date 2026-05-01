# AI Ops Agent 🚀

一个基于 AI 的服务器日志分析与自动排障工具。

## 功能
- 自动读取 Nginx / Docker / 系统日志
- 自动识别错误类型
- 提供修复建议
- 支持命令执行

## 使用方法
```bash
python main.py


## 示例

输入日志：
nginx: [emerg] bind() to 0.0.0.0:80 failed (98: Address already in use)

输出：
错误类型：端口占用  
解决方案：
lsof -i :80
kill -9 <PID>
