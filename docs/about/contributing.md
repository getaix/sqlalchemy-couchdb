# 贡献指南

## 欢迎贡献

感谢您对 SQLAlchemy CouchDB 方言项目的兴趣！我们欢迎所有形式的贡献，包括但不限于：

- 🐛 报告 Bug
- 💡 提出新功能建议
- 📝 完善文档
- 💻 提交代码修复
- 🧪 添加测试用例
- 🎨 改进代码规范
- 📊 性能优化

## 开发环境设置

### 1. 克隆仓库

```bash
git clone https://github.com/getaix/sqlalchemy-couchdb.git
cd sqlalchemy-couchdb
```

### 2. 创建虚拟环境

```bash
# 使用 venv
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 或使用 pyenv-virtualenv
pyenv virtualenv 3.11.0 sqlalchemy-couchdb-dev
pyenv local sqlalchemy-couchdb-dev
```

### 3. 安装开发依赖

```bash
# 安装项目（可编辑模式）
pip install -e ".[dev]"

# 安装可选依赖（Phase 2 开发需要）
pip install -e ".[all]"

# 验证安装
python -c "import sqlalchemy_couchdb; print(sqlalchemy_couchdb.__version__)"
```

### 4. 启动 CouchDB

```bash
# 使用 Docker（推荐）
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  --name couchdb-dev couchdb:3

# 等待服务启动
sleep 5

# 创建测试数据库
curl -X PUT http://admin:password@localhost:5984/testdb
```

### 5. 验证开发环境

```bash
# 运行简单测试
python -m pytest tests/test_compiler.py::TestSelectCompilation::test_simple_select -v
```

## 工作流程

### Fork 项目

1. 在 GitHub 上 Fork [sqlalchemy-couchdb](https://github.com/getaix/sqlalchemy-couchdb)
2. 克隆您的 Fork 到本地

```bash
git clone https://github.com/YOUR_USERNAME/sqlalchemy-couchdb.git
cd sqlalchemy-couchdb
```

3. 添加上游仓库

```bash
git remote add upstream https://github.com/getaix/sqlalchemy-couchdb.git
```

### 创建分支

```bash
# 从 main 分支创建新分支
git checkout -b feature/your-feature-name

# 或修复 bug
git checkout -b fix/bug-description

# 或文档改进
git checkout -b docs/improve-documentation
```

### 分支命名规范

```
feature/new-feature-name    # 新功能
fix/bug-description         # Bug 修复
docs/some-docs              # 文档改进
refactor/refactor-something # 代码重构
test/add-new-tests          # 测试用例
perf/optimize-something     # 性能优化
```

### 开发流程

```bash
# 1. 更新代码
git checkout main
git pull upstream main

# 2. 创建分支
git checkout -b feature/your-feature

# 3. 开发代码
# ... 编写代码 ...

# 4. 运行测试
pytest

# 5. 提交代码
git add .
git commit -m "feat: 添加新功能描述"

# 6. 推送到您的 Fork
git push origin feature/your-feature

# 7. 在 GitHub 上创建 Pull Request
```

## 代码规范

### 遵循规范

- 遵循 [PEP 8](https://pep8.org/) Python 编码规范
- 使用 Black 格式化代码
- 使用 isort 排序导入
- 添加完整的类型提示
- 编写清晰的文档字符串

### 格式化代码

```bash
# 格式化所有 Python 文件
black sqlalchemy_couchdb tests

# 排序导入
isort sqlalchemy_couchdb tests

# 检查代码风格
ruff check sqlalchemy_couchdb tests

# 自动修复风格问题
ruff check --fix sqlalchemy_couchdb tests
```

### 类型检查

```bash
# 运行 mypy
mypy sqlalchemy_couchdb

# 忽略某些导入的类型错误
mypy sqlalchemy_couchdb --ignore-missing-imports
```

## 提交规范

### 提交信息格式

```
type(scope): subject

body

footer
```

**类型 (type)**:
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式（不影响功能）
- `refactor`: 重构（既不修复 Bug 也不添加功能）
- `test`: 测试相关
- `chore`: 构建工具或辅助工具
- `perf`: 性能优化
- `ci`: 持续集成相关

**作用域 (scope)** (可选):
- `compiler`: 编译器相关
- `client`: 客户端相关
- `dialect`: 方言相关
- `types`: 类型系统相关
- `tests`: 测试相关
- `docs`: 文档相关

**示例**:

```
feat(compiler): 添加 ORDER BY ASC/DESC 支持

- 实现 _compile_order_by 方法
- 支持 ASC 和 DESC 排序
- 自动创建所需索引
- 添加单元测试

Closes #123
```

```
fix(client): 修复批量插入时的超时问题

- 增加 httpx 超时时间
- 添加重试机制
- 更新测试用例

Fixes #456
```

```
docs: 更新安装指南

- 添加 Docker 启动步骤
- 完善故障排除部分
- 添加常见问题

Refs #789
```

## 测试指南

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_compiler.py -v

# 运行测试并生成覆盖率报告
pytest --cov=sqlalchemy_couchdb --cov-report=html --cov-report=term-missing

# 运行慢速测试
pytest -m slow

# 运行单元测试
pytest -m unit
```

### 编写测试

#### 测试文件命名

```
test_*.py              # 测试文件
test_*_unit.py         # 单元测试
test_*_integration.py  # 集成测试
```

#### 测试类和方法

```python
import pytest
from sqlalchemy import text

class TestYourFeature:
    """您的功能测试"""

    @pytest.fixture
    def setup_data(self, engine):
        """设置测试数据"""
        # 插入测试数据
        pass

    def test_something(self, engine, setup_data):
        """测试用例"""
        # Arrange - 准备
        query = text("SELECT * FROM users WHERE type = 'user'")

        # Act - 执行
        result = engine.execute(query)

        # Assert - 断言
        assert result.rowcount > 0
        assert result.fetchone().name is not None
```

#### 测试最佳实践

1. **独立测试**: 每个测试都应独立运行
2. **描述性名称**: 测试方法名应清楚描述测试内容
3. **清理数据**: 测试后清理测试数据
4. **使用 Fixtures**: 复用测试设置
5. **测试覆盖**: 新代码必须有测试覆盖

### 测试标记

```python
import pytest

class TestAsyncFeatures:
    @pytest.mark.asyncio
    async def test_async_operation(self, async_engine):
        """异步操作测试"""
        ...

    @pytest.mark.slow
    def test_performance(self, engine):
        """性能测试"""
        ...

    @pytest.mark.integration
    def test_real_database(self, couchdb_url):
        """集成测试"""
        ...
```

## Pull Request 指南

### PR 前检查清单

- [ ] 代码已格式化（Black, isort）
- [ ] 所有测试通过
- [ ] 添加了新测试
- [ ] 更新了相关文档
- [ ] 提交信息符合规范
- [ ] 没有合并冲突
- [ ] 运行了 linter

### PR 描述模板

```markdown
## 更改说明

简要描述此 PR 的更改内容。

## 更改类型

- [ ] Bug 修复
- [ ] 新功能
- [ ] 破坏性变更
- [ ] 文档更新
- [ ] 性能改进
- [ ] 重构

## 测试

- [ ] 添加了单元测试
- [ ] 所有测试通过
- [ ] 手动测试完成

## 截图/示例（如果适用）

## 注意事项

需要审查者特别关注的内容。

## 相关 Issue

Closes #123
```

### PR 审查流程

1. **自动检查**: CI 会运行测试、代码风格检查等
2. **代码审查**: 维护者会审查代码质量和设计
3. **测试验证**: 确保所有测试通过
4. **合并**: 审查通过后合并到主分支

## Bug 报告

### 使用 GitHub Issues

### Bug 报告模板

```markdown
## Bug 描述
简要描述 Bug。

## 重现步骤
1. 打开 '...'
2. 执行 '...'
3. 滚动到 '...'
4. 看到错误

## 预期行为
描述预期会发生什么。

## 实际行为
描述实际发生了什么。

## 环境信息
- OS: [e.g., macOS 14.0]
- Python: [e.g., 3.11.5]
- SQLAlchemy: [e.g., 2.0.23]
- sqlalchemy-couchdb: [e.g., 0.1.0]
- CouchDB: [e.g., 3.3.3]

## 复现代码
```python
# 提供最小可复现代码
```

## 错误信息
```
完整的错误堆栈跟踪
```

## 其他信息
任何其他有帮助的信息。
```

## 功能请求

### 功能请求模板

```markdown
## 功能描述
简要描述您想要的功能。

## 问题背景
此功能解决什么问题？

## 预期解决方案
您希望此功能如何工作？

## 替代方案
您考虑过其他解决方案吗？

## 其他信息
任何其他相关的信息或截图。
```

## 文档贡献

### 文档类型

- API 参考
- 用户指南
- 教程
- 示例代码
- 最佳实践

### 文档规范

- 使用 Markdown 格式
- 添加代码示例
- 使用中文编写
- 保持简洁清晰
- 添加适当的标题层级

### 文档文件结构

```
docs/
├── getting-started/    # 入门指南
├── guide/             # 用户指南
├── api/               # API 参考
├── dev/               # 开发指南
└── about/             # 项目信息
```

## 性能基准测试

### 运行性能测试

```bash
# 运行基准测试
python -m pytest tests/performance/ -v

# 运行特定基准测试
python -m pytest tests/performance/test_bulk_insert.py -v
```

### 编写性能测试

```python
def test_bulk_insert_performance():
    """批量插入性能测试"""
    import time

    start = time.time()
    # 执行操作
    ...
    elapsed = time.time() - start

    # 断言性能要求
    assert elapsed < 2.0, f"操作耗时 {elapsed:.2f}s，超过阈值"
```

## 发布流程

### 版本号规范

遵循 [语义化版本](https://semver.org/lang/zh-CN/)：

- **主版本号 (x.0.0)**: 不兼容的 API 修改
- **次版本号 (x.y.0)**: 向下兼容的功能性新增
- **修订号 (x.y.z)**: 向下兼容的问题修正

### 发布步骤

1. 更新 `CHANGELOG.md`
2. 更新 `__init__.py` 中的版本号
3. 创建发布 PR
4. 合并到 main 分支
5. 创建 GitHub Release
6. 推送到 PyPI

## 行为准则

### 我们的承诺

为了营造开放和欢迎的环境，我们作为贡献者和维护者承诺，无论年龄、体型、残疾、民族、性别认同与表达、经验水平、教育程度、社会经济地位、国籍、个人外表、种族、宗教信仰或性认同与取向，都让每个人在我们的项目和社区中参与无骚扰。

### 我们的标准

积极向上的例子包括：
- 使用欢迎和包容的语言
- 尊重不同的观点和经历
- 优雅地接受建设性批评
- 专注于对社区最有利的事情
- 对其他社区成员表现出同理心

不可接受的例子包括：
- 使用性化的语言或图像，以及不受欢迎的性关注或搭讪
- 恶意评论、侮辱/贬损评论，以及个人或政治攻击
- 公开或私下骚扰
- 未经明确许可，发布他人的私人信息，如物理或电子地址
- 在专业环境中可能被合理认为不当的其他行为

### 执行

可以通过 [email@example.com] 报告违规行为。审查后，所有投诉都将得到审查和调查，并将产生被认为是必要且适合具体情况的回应。

## 获取帮助

### 沟通渠道

- **GitHub Issues**: Bug 报告和功能请求
- **GitHub Discussions**: 一般性讨论
- **邮件**: 您的.email@example.com

### 常见问题

**Q: 我可以在不了解 CouchDB 的情况下贡献吗？**
A: 可以！我们欢迎各种背景的贡献者。您可以从阅读文档开始，然后从简单的任务（如文档改进）开始。

**Q: 如何选择第一个 issue？**
A: 建议从标记为 `good first issue` 的问题开始。

**Q: 我的 PR 很长时间没有审查怎么办？**
A: 请在 PR 中留言或给维护者发邮件。我们会尽快处理。

## 致谢

感谢所有为本项目做出贡献的开发者和用户！

- 感谢所有代码贡献者
- 感谢所有报告 Bug 的用户
- 感谢所有完善文档的贡献者
- 感谢所有提供反馈和建议的用户

## 许可证

通过贡献，您同意您的贡献将在 MIT 许可证下许可。

## 联系方式

- 维护者: [Your Name] <your.email@example.com>
- 项目主页: https://github.com/getaix/sqlalchemy-couchdb
- 文档: https://getaix.github.io/sqlalchemy-couchdb

---

再次感谢您的贡献！我们期待与您一起使这个项目变得更好。🎉
