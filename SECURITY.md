# 安全策略

## 支持的版本

我们目前对以下版本提供安全更新：

| 版本 | 支持状态 |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## 报告漏洞

我们非常重视安全问题。如果您发现了安全漏洞，请通过以下方式私下向我们报告：

### 报告方式

**电子邮件**: develop@getaix.tech

请在邮件主题中包含 "[SECURITY]" 标记。

### 报告内容

请在报告中包含以下信息：

1. **漏洞描述**：详细说明安全问题
2. **影响范围**：哪些版本受影响
3. **重现步骤**：如何重现该漏洞
4. **潜在影响**：可能造成的安全风险
5. **建议修复**：如果有修复建议（可选）

### 响应时间

- **确认回复**：我们将在 48 小时内确认收到您的报告
- **初步评估**：我们将在 5 个工作日内提供初步评估
- **修复发布**：根据漏洞严重程度，我们将尽快发布修复版本

### 披露政策

为了保护用户，我们请求：

1. **延迟公开披露**：在我们发布修复版本之前，请不要公开披露漏洞
2. **负责任的披露**：给我们合理的时间来修复问题
3. **协调披露**：我们会与您协商适当的披露时间

### 安全更新通知

安全更新将通过以下渠道发布：

- GitHub Security Advisories
- Release Notes（标记为 SECURITY）
- 项目邮件列表（如果适用）

## 安全最佳实践

使用本项目时，请遵循以下安全最佳实践：

### 1. 认证和授权

```python
# ❌ 不要在代码中硬编码凭证
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# ✅ 使用环境变量
import os
username = os.getenv('COUCHDB_USER')
password = os.getenv('COUCHDB_PASSWORD')
engine = create_engine(f'couchdb://{username}:{password}@localhost:5984/mydb')
```

### 2. 使用 HTTPS

```python
# ❌ 生产环境不要使用 HTTP
engine = create_engine('couchdb://user:pass@example.com:5984/mydb')

# ✅ 生产环境使用 HTTPS
engine = create_engine('couchdb://user:pass@example.com:6984/mydb?ssl=true')
```

### 3. 输入验证

```python
# ✅ 使用参数化查询，避免注入攻击
from sqlalchemy import text

result = conn.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": user_input}
)
```

### 4. 最小权限原则

- 为应用程序创建专用的 CouchDB 用户
- 只授予必要的数据库权限
- 定期审查和更新权限

### 5. 保持更新

```bash
# 定期更新到最新版本
pip install --upgrade sqlalchemy-couchdb
```

## 已知安全考虑

### CouchDB 特定问题

1. **_rev 冲突**：确保正确处理文档版本冲突
2. **_design 文档**：限制对设计文档的访问
3. **_changes feed**：在公开网络上使用时要小心

### 混合架构模式

1. **数据一致性**：双写模式可能导致短暂的数据不一致
2. **凭证管理**：需要管理多个数据库的凭证

## 安全审计

我们欢迎安全研究人员对本项目进行审计。如果您进行了安全审计，请与我们分享结果。

## 致谢

我们感谢以下安全研究人员的贡献：

（目前还没有报告的安全问题）

---

感谢您帮助保持 SQLAlchemy CouchDB Dialect 的安全！
