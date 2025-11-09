---
name: Bug 报告
about: 创建一个 Bug 报告来帮助我们改进
title: '[BUG] '
labels: 'bug'
assignees: ''

---

## Bug 描述
简洁清晰地描述这个 Bug。

## 复现步骤
重现该问题的步骤：
1. 执行 '...'
2. 调用 '...'
3. 观察到 '...'
4. 出现错误

## 期望行为
清晰简洁地描述你期望发生的行为。

## 实际行为
清晰简洁地描述实际发生的行为。

## 最小可复现代码
```python
# 请提供能够复现问题的最小代码示例
from sqlalchemy import create_engine

engine = create_engine('couchdb://admin:password@localhost:5984/testdb')
# ... 你的代码
```

## 错误信息
```
请粘贴完整的错误堆栈信息
```

## 环境信息
- **操作系统**: [例如 macOS 14.0, Ubuntu 22.04, Windows 11]
- **Python 版本**: [例如 3.11.5]
- **sqlalchemy-couchdb 版本**: [例如 0.1.0]
- **SQLAlchemy 版本**: [例如 2.0.23]
- **CouchDB 版本**: [例如 3.3.3]
- **安装方式**: [pip, conda, 源码安装]

## 附加信息
添加任何关于该问题的其他上下文信息。

### 日志输出
如果相关，请包含日志输出：
```
启用日志：
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 数据库配置
- 是否使用 CouchDB 集群？
- 是否启用了认证？
- 是否使用了代理或负载均衡？

### 已尝试的解决方案
描述你已经尝试过的解决方案（如果有）。
