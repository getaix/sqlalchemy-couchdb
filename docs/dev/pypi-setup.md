# PyPI 发布配置指南

## 问题说明

GitHub Actions 自动发布到 PyPI 失败，错误信息：
```
HTTPError: 403 Forbidden from https://upload.pypi.org/legacy/
Invalid or non-existent authentication information.
```

## 解决方案

需要在 GitHub 仓库中配置 PyPI API Token。

### 步骤 1: 生成 PyPI API Token

1. 登录 PyPI 账号：https://pypi.org/
2. 进入账户设置：https://pypi.org/manage/account/
3. 滚动到 "API tokens" 部分
4. 点击 "Add API token"
5. 配置 Token：
   - **Token name**: `github-actions-sqlalchemy-couchdb`
   - **Scope**: 选择 "Project: sqlalchemy-couchdb" (如果项目已存在)
     - 或选择 "Entire account" (首次发布时)
6. 点击 "Add token"
7. **重要**: 复制生成的 token（以 `pypi-` 开头），这个 token 只会显示一次！

### 步骤 2: 添加 GitHub Secret

1. 进入 GitHub 仓库：https://github.com/getaix/sqlalchemy-couchdb
2. 点击 "Settings" (设置)
3. 在左侧菜单中找到 "Secrets and variables" → "Actions"
4. 点击 "New repository secret"
5. 配置 Secret：
   - **Name**: `PYPI_API_TOKEN`
   - **Secret**: 粘贴刚才复制的 PyPI token
6. 点击 "Add secret"

### 步骤 3: 重新触发发布

有两种方式重新触发发布：

#### 方式 1: 重新运行失败的 Action

1. 进入 Actions 页面：https://github.com/getaix/sqlalchemy-couchdb/actions
2. 找到失败的 "Publish to PyPI" workflow
3. 点击 "Re-run failed jobs"

#### 方式 2: 删除并重新推送标签

```bash
# 删除本地标签
git tag -d v0.1.2

# 删除远程标签
git push origin :refs/tags/v0.1.2

# 重新创建标签
git tag -a v0.1.2 -m "Version 0.1.2"

# 推送标签
git push origin v0.1.2
```

### 步骤 4: 验证发布

发布成功后，可以在以下位置查看：

- **PyPI 页面**: https://pypi.org/project/sqlalchemy-couchdb/
- **安装测试**:
  ```bash
  pip install sqlalchemy-couchdb
  ```

## 首次发布注意事项

如果这是项目的首次发布到 PyPI，需要：

1. 确保项目名称 `sqlalchemy-couchdb` 在 PyPI 上可用
2. API Token 的 Scope 需要选择 "Entire account"
3. 首次发布成功后，可以创建项目专用的 API Token

## 手动发布（备选方案）

如果 GitHub Actions 有问题，可以手动发布：

```bash
# 安装依赖
pip install build twine

# 清理旧构建
rm -rf dist/ build/ *.egg-info

# 构建包
python -m build

# 检查包
twine check dist/*

# 上传到 PyPI（会提示输入用户名和密码/token）
twine upload dist/*
# Username: __token__
# Password: <your-pypi-token>
```

## 常见问题

### Q1: Token 权限不足

**问题**: 403 Forbidden

**解决**:
- 确保 token 是为正确的项目创建的
- 首次发布使用 "Entire account" scope
- 检查 token 是否已过期或被撤销

### Q2: 项目名称冲突

**问题**: 409 Conflict - Project name already exists

**解决**:
- 在 `pyproject.toml` 中更改项目名称
- 或联系现有项目所有者转让所有权

### Q3: 版本号已存在

**问题**: 400 Bad Request - File already exists

**解决**:
- 不能重新上传相同版本号
- 需要更新版本号（例如从 0.1.2 到 0.1.3）
- 或使用 TestPyPI 进行测试

## TestPyPI 测试

在正式发布前，建议先在 TestPyPI 上测试：

```bash
# 上传到 TestPyPI
twine upload --repository testpypi dist/*

# 从 TestPyPI 安装测试
pip install --index-url https://test.pypi.org/simple/ sqlalchemy-couchdb
```

## 相关链接

- [PyPI 官方文档](https://pypi.org/help/)
- [Packaging Python Projects](https://packaging.python.org/tutorials/packaging-projects/)
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Twine 文档](https://twine.readthedocs.io/)
