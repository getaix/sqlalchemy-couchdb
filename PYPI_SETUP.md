# PyPI 发布快速指南

## 🚨 当前问题

GitHub Actions 发布失败：**403 Forbidden - Invalid authentication**

## ✅ 快速修复步骤

### 1. 获取 PyPI Token (5分钟)

访问：https://pypi.org/manage/account/token/

- Token name: `github-actions-sqlalchemy-couchdb`
- Scope: **Entire account** (首次发布)
- 复制生成的 token (以 `pypi-` 开头)

### 2. 添加到 GitHub (2分钟)

访问：https://github.com/getaix/sqlalchemy-couchdb/settings/secrets/actions

- 点击 "New repository secret"
- Name: `PYPI_API_TOKEN`
- Secret: 粘贴 PyPI token
- 点击 "Add secret"

### 3. 重新运行发布 (1分钟)

访问：https://github.com/getaix/sqlalchemy-couchdb/actions

- 找到失败的 workflow
- 点击 "Re-run failed jobs"

## 📦 手动发布（备选）

```bash
# 1. 安装工具
pip install build twine

# 2. 构建包
python -m build

# 3. 上传（会提示输入 token）
twine upload dist/*
```

使用 `__token__` 作为用户名，PyPI token 作为密码。

## 📚 详细文档

查看完整配置指南：[docs/dev/pypi-setup.md](./pypi-setup.md)

## 🔗 相关链接

- PyPI 账户：https://pypi.org/manage/account/
- GitHub Secrets：https://github.com/getaix/sqlalchemy-couchdb/settings/secrets/actions
- GitHub Actions：https://github.com/getaix/sqlalchemy-couchdb/actions
