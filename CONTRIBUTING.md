# Contributing to SQLAlchemy CouchDB

感谢你对 SQLAlchemy CouchDB 的关注！

## 开发环境设置

```bash
# 克隆仓库
git clone https://github.com/getaix/sqlalchemy-couchdb.git
cd sqlalchemy-couchdb

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 启动 CouchDB (Docker)
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  --name couchdb couchdb:3
```

## 代码质量

运行以下命令确保代码质量：

```bash
# 格式化代码
black sqlalchemy_couchdb tests examples

# Linting
ruff check sqlalchemy_couchdb tests examples --fix

# 类型检查
mypy sqlalchemy_couchdb --ignore-missing-imports

# 运行测试
pytest tests/ -v --cov=sqlalchemy_couchdb
```

## 提交规范

我们使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

- `feat:` 新功能
- `fix:` 错误修复
- `docs:` 文档更新
- `style:` 代码格式（不影响功能）
- `refactor:` 重构
- `test:` 测试相关
- `chore:` 构建/工具链更新

示例：
```
feat: 添加批量删除功能
fix: 修复异步查询超时问题
docs: 更新快速入门指南
```

## 发布流程

1. 更新版本号（使用 bumpversion）：
   ```bash
   bumpversion patch  # 0.1.0 -> 0.1.1
   bumpversion minor  # 0.1.0 -> 0.2.0
   bumpversion major  # 0.1.0 -> 1.0.0
   ```

2. 更新 CHANGELOG.md

3. 推送标签：
   ```bash
   git push origin master --tags
   ```

4. GitHub Actions 自动发布到 PyPI

## 问题反馈

请在 [GitHub Issues](https://github.com/getaix/sqlalchemy-couchdb/issues) 提交问题。
