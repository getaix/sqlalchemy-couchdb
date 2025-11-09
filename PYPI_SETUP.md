# PyPI 发布配置指南（无需 Token）

## ✨ 使用 Trusted Publishers

PyPI Trusted Publishers 是官方推荐的发布方式，**无需手动管理 API Token**。

## 🚀 快速配置（仅需一次，3分钟）

### 步骤 1: 在 PyPI 配置 Trusted Publisher

访问：https://pypi.org/manage/account/publishing/

点击 "Add a new pending publisher"，填写：

```
PyPI Project Name:  sqlalchemy-couchdb
Owner:              getaix
Repository name:    sqlalchemy-couchdb
Workflow name:      publish.yml
Environment name:   (留空)
```

点击 "Add" 即可。

### 步骤 2: 重新运行发布

访问：https://github.com/getaix/sqlalchemy-couchdb/actions

找到失败的 workflow，点击 "Re-run failed jobs"。

## ✅ 完成！

配置完成后，以后发布新版本只需：

```bash
# 1. 更新版本号并提交
git commit -am "release: v0.1.3"

# 2. 创建并推送标签（自动触发发布）
git tag v0.1.3
git push origin main --tags
```

GitHub Actions 会自动构建并发布到 PyPI！

## 📚 详细文档

查看完整配置指南：[docs/dev/trusted-publishers.md](./docs/dev/trusted-publishers.md)

## 🔗 相关链接

- **PyPI 配置页面**: https://pypi.org/manage/account/publishing/
- **GitHub Actions**: https://github.com/getaix/sqlalchemy-couchdb/actions
- **官方文档**: https://docs.pypi.org/trusted-publishers/

## 📦 手动发布（备选）

如果需要手动发布：

```bash
pip install build twine
python -m build
twine upload dist/*  # 需要 PyPI 用户名和密码/token
```
