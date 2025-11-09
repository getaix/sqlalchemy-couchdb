# PyPI Trusted Publishers 配置指南

## 什么是 Trusted Publishers？

Trusted Publishers（可信发布者）是 PyPI 推荐的发布方式，使用 OpenID Connect (OIDC) 进行身份验证，**无需手动管理 API Token**。

## 优势

- ✅ **无需 Token**: 不需要创建和管理 PyPI API Token
- ✅ **更安全**: 使用 OIDC 临时凭证，无需在 GitHub Secrets 中存储长期凭证
- ✅ **自动化**: GitHub Actions 自动处理认证
- ✅ **推荐方式**: PyPI 官方推荐的发布方式

## 配置步骤

### 步骤 1: 在 PyPI 配置 Trusted Publisher

#### 首次发布（项目还不存在）

1. 访问 PyPI 的待发布管理页面：https://pypi.org/manage/account/publishing/
2. 点击 "Add a new pending publisher"
3. 填写信息：
   ```
   PyPI Project Name: sqlalchemy-couchdb
   Owner: getaix
   Repository name: sqlalchemy-couchdb
   Workflow name: publish.yml
   Environment name: (留空)
   ```
4. 点击 "Add"

#### 已存在的项目

1. 访问项目页面：https://pypi.org/manage/project/sqlalchemy-couchdb/settings/publishing/
2. 点击 "Add a new publisher"
3. 填写相同的信息（如上）
4. 点击 "Add"

### 步骤 2: 推送代码（已完成）

GitHub Actions 工作流已更新为使用 Trusted Publishers，配置文件：
```yaml
# .github/workflows/publish.yml
permissions:
  id-token: write  # 用于 PyPI Trusted Publishers
  contents: read

steps:
  - name: Publish to PyPI
    uses: pypa/gh-action-pypi-publish@release/v1
```

### 步骤 3: 测试发布

有两种方式测试：

#### 方式 1: 重新运行失败的 Action

1. 配置好 Trusted Publisher 后
2. 访问：https://github.com/getaix/sqlalchemy-couchdb/actions
3. 找到失败的 workflow
4. 点击 "Re-run failed jobs"

#### 方式 2: 推送新标签

```bash
# 删除旧标签
git tag -d v0.1.2
git push origin :refs/tags/v0.1.2

# 重新创建并推送
git tag -a v0.1.2 -m "Version 0.1.2"
git push origin v0.1.2
```

## 验证配置

### 在 PyPI 上验证

1. 访问：https://pypi.org/manage/account/publishing/
2. 应该看到 `sqlalchemy-couchdb` 的 pending publisher 或已配置的 publisher

### 检查 GitHub Actions

1. 确保工作流有正确的权限：
   ```yaml
   permissions:
     id-token: write
     contents: read
   ```

2. 使用官方发布 Action：
   ```yaml
   uses: pypa/gh-action-pypi-publish@release/v1
   ```

## 故障排除

### 问题 1: "Trusted publishing is not configured"

**原因**: PyPI 上未配置 Trusted Publisher

**解决**: 按照步骤 1 在 PyPI 上配置

### 问题 2: "Could not obtain OIDC token"

**原因**: GitHub Actions 缺少 `id-token: write` 权限

**解决**: 检查工作流文件是否有正确的 `permissions` 配置

### 问题 3: "Repository name mismatch"

**原因**: PyPI 配置的仓库信息与实际仓库不匹配

**解决**:
- Owner: `getaix`
- Repository: `sqlalchemy-couchdb`
- Workflow: `publish.yml`

## 配置示例

### PyPI Trusted Publisher 配置

```
PyPI Project Name:  sqlalchemy-couchdb
Owner:              getaix
Repository name:    sqlalchemy-couchdb
Workflow name:      publish.yml
Environment name:   (optional, leave empty)
```

### GitHub Actions 完整配置

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

jobs:
  build-and-publish:
    runs-on: ubuntu-latest

    permissions:
      id-token: write
      contents: read

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build

    - name: Build package
      run: python -m build

    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
```

## 首次发布流程

对于全新项目：

1. ✅ 在 PyPI 上配置 **Pending Publisher**
2. ✅ 推送版本标签触发 GitHub Actions
3. ✅ Actions 自动发布到 PyPI
4. ✅ Pending Publisher 自动转换为正式 Publisher

## 后续发布

配置完成后，以后的发布流程极其简单：

```bash
# 1. 更新版本号
# 编辑 pyproject.toml 和 __init__.py

# 2. 提交并创建标签
git add .
git commit -m "release: v0.1.3"
git tag -a v0.1.3 -m "Version 0.1.3"

# 3. 推送（自动触发发布）
git push origin main
git push origin v0.1.3
```

GitHub Actions 会自动：
- 构建包
- 通过 OIDC 认证
- 发布到 PyPI

## 相关链接

- [PyPI Trusted Publishers 官方文档](https://docs.pypi.org/trusted-publishers/)
- [PyPI 待发布管理](https://pypi.org/manage/account/publishing/)
- [GitHub Actions OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [PyPI Publish Action](https://github.com/pypa/gh-action-pypi-publish)

## 总结

使用 Trusted Publishers 后：

- ❌ **不需要**: 创建 PyPI API Token
- ❌ **不需要**: 在 GitHub Secrets 中存储 Token
- ❌ **不需要**: 担心 Token 泄露或过期
- ✅ **只需要**: 在 PyPI 上一次性配置 Trusted Publisher
- ✅ **自动化**: 推送标签即可自动发布
