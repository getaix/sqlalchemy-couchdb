# 代码规范

## 概述

SQLAlchemy CouchDB 方言遵循严格的代码规范，确保代码质量、可读性和可维护性。

## Python 代码规范

### PEP 8 合规

遵循 [PEP 8](https://pep8.org/) Python 编码规范：

```python
# ✅ 正确：使用 4 个空格缩进
def example_function():
    if True:
        print("正确缩进")

# ❌ 错误：使用 Tab
def example_function():
	if True:
		print("错误缩进")
```

### 行长度

- **最大行长度**: 88 字符（Black 默认）
- **长行处理**: 使用括号或反斜杠

```python
# ✅ 正确：使用括号
result = some_function(
    arg1='value1',
    arg2='value2',
    arg3='value3'
)

# ✅ 正确：字符串拼接
long_string = (
    "这是一个很长的字符串 "
    "需要跨多行显示"
)
```

### 导入规范

```python
# ✅ 标准库
import os
import sys
from datetime import datetime

# ✅ 第三方库
import httpx
import pytest
from sqlalchemy import text

# ✅ 本地模块
from sqlalchemy_couchdb.client import SyncCouchDBClient
from sqlalchemy_couchdb.compiler import CouchDBCompiler

# ❌ 避免：混乱的导入
from sqlalchemy import *
import os, sys
```

### 函数和类命名

```python
# ✅ 函数：小写下划线
def get_user_info():
    pass

def fetch_document():
    pass

# ✅ 类：PascalCase
class CouchDBDialect:
    pass

class AsyncCouchDBClient:
    pass

# ✅ 常量：大写下划线
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3

# ✅ 私有方法：前导下划线
class Example:
    def _private_method(self):
        pass

# ✅ 私有属性：前导下划线
class Example:
    def __init__(self):
        self._private_attr = None
```

### 变量命名

```python
# ✅ 描述性名称
user_id = 'user:123'
document_count = 0
is_active = True

# ❌ 模糊名称
x = 'user:123'
c = 0
flag = True
```

## 文档字符串

### 使用 Google 风格

```python
def compile_select(
    self,
    select: Select,
    **kwargs: Any
) -> dict:
    """
    编译 SELECT 语句为 Mango Query。

    此方法将 SQLAlchemy Select 对象转换为 CouchDB Mango Query，
    支持 WHERE、ORDER BY、LIMIT 等子句。

    参数:
        select: SQLAlchemy Select 对象
        **kwargs: 其他编译参数

    返回:
        包含 selector、fields、sort 等的字典

    异常:
        CompileError: 编译失败时抛出

    示例:
        >>> compiler = CouchDBCompiler(dialect, None)
        >>> sql = text("SELECT * FROM users WHERE age > 25")
        >>> mango = compiler.compile_select(sql)
        >>> print(mango)
        {
            'selector': {'age': {'$gt': 25}},
            'fields': ['_id', 'name', 'age']
        }

    注意:
        此方法会自动创建所需的索引
    """
    pass
```

### 类文档

```python
class CouchDBCompiler:
    """
    SQL → Mango Query 编译器。

    负责将 SQLAlchemy SQL 语句转换为 CouchDB Mango Query，
    支持 SELECT、INSERT、UPDATE、DELETE 等操作。

    属性:
        dialect: 关联的方言实例
        client: CouchDB 客户端
    """

    def __init__(self, dialect, statement, **kwargs):
        """初始化编译器。"""
        self.dialect = dialect
        self.statement = statement
```

## 类型提示

### 必需的类型提示

```python
from typing import Dict, List, Optional, Union, Any

def process_value(
    value: Union[str, int],
    default: Optional[str] = None
) -> Dict[str, Any]:
    """
    处理输入值。

    参数:
        value: 要处理的值，可以是字符串或整数
        default: 默认值，如果输入为空则使用

    返回:
        包含处理结果的字典
    """
    pass
```

### 复杂类型

```python
from typing import Protocol, TypeVar

T = TypeVar('T')

# Protocol 用于定义接口
class ClientProtocol(Protocol):
    def find(self, selector: dict) -> List[dict]:
        """执行查询。"""
        ...

# 泛型
def process_list(items: List[T]) -> List[T]:
    """处理列表。"""
    return items

# 可调用类型
from typing import Callable

Callback = Callable[[dict], None]

def process_with_callback(data: dict, callback: Callback) -> None:
    """使用回调处理数据。"""
    callback(data)
```

## 代码结构

### 类结构

```python
class ExampleClass:
    """示例类。"""

    # 类变量
    default_value = 100

    def __init__(self, value: int):
        """初始化。"""
        self.value = value
        self._private = None

    # 公共方法
    def public_method(self) -> str:
        """公共方法。"""
        return f"Value: {self.value}"

    # 私有方法
    def _private_method(self) -> None:
        """私有方法。"""
        pass

    # 静态方法
    @staticmethod
    def static_method() -> str:
        """静态方法。"""
        return "Static"

    # 类方法
    @classmethod
    def from_string(cls, s: str) -> 'ExampleClass':
        """从字符串创建实例。"""
        return cls(int(s))

    # 属性
    @property
    def doubled(self) -> int:
        """只读属性。"""
        return self.value * 2
```

### 模块结构

```python
"""
模块说明。

此模块提供 ... 功能。
"""

from __future__ import annotations

from typing import List, Optional
import logging

# 日志配置
logger = logging.getLogger(__name__)

# 常量
DEFAULT_TIMEOUT = 30

# 异常
class CustomError(Exception):
    """自定义异常。"""
    pass

# 辅助函数
def helper_function(arg: str) -> bool:
    """辅助函数。"""
    return True

# 主要类
class MainClass:
    """主要类。"""
    pass

# 公开 API
__all__ = [
    'MainClass',
    'helper_function',
    'CustomError',
]
```

## 错误处理

### 异常使用

```python
# ✅ 特定异常
from sqlalchemy_couchdb.exceptions import CouchDBError

try:
    result = client.get(doc_id)
except NotFoundError:
    logger.warning("文档不存在: %s", doc_id)
    return None
except DocumentConflictError:
    logger.error("文档版本冲突: %s", doc_id)
    raise
except CouchDBError as e:
    logger.error("CouchDB 错误: %s", e)
    raise
except Exception as e:
    logger.exception("未预期错误")
    raise

# ❌ 通用异常捕获
try:
    result = client.get(doc_id)
except Exception:
    # 太宽泛
    pass
```

### 清理资源

```python
# ✅ 使用上下文管理器
def process_data(data: list) -> list:
    """处理数据。"""
    with open('output.txt', 'w') as f:
        for item in data:
            f.write(f"{item}\n")

# ✅ 显式清理
client = None
try:
    client = SyncCouchDBClient(...)
    # 使用 client
finally:
    if client:
        client.close()

# ❌ 资源泄露
client = SyncCouchDBClient(...)
# 没有关闭客户端
```

## 测试规范

### 测试文件命名

```
test_compiler.py           # 测试文件
test_compiler_unit.py      # 单元测试
test_compiler_integration.py  # 集成测试
```

### 测试类和方法

```python
import pytest
from sqlalchemy import text

class TestCouchDBCompiler:
    """编译器测试。"""

    @pytest.fixture
    def compiler(self, dialect):
        """创建编译器实例。"""
        return CouchDBCompiler(dialect, None)

    def test_simple_select(self, compiler):
        """简单 SELECT 测试。"""
        # Arrange
        sql = text("SELECT * FROM users WHERE type = 'user'")

        # Act
        mango = compiler.visit_select(sql)

        # Assert
        assert mango['selector'] == {"type": {"$eq": "user"}}
        assert 'fields' in mango
        assert 'limit' in mango
```

### 测试注释

```python
def test_update_with_conflict(engine):
    """测试更新时的乐观锁冲突。"""
    # 此测试验证：当文档被外部修改后，
    # UPDATE 操作正确抛出 DocumentConflictError
    pass

def test_concurrent_queries(async_engine):
    """测试并发查询。"""
    # 注意：此测试需要真实的异步环境
    pass
```

## 性能优化

### 避免性能陷阱

```python
# ✅ 使用局部变量
def process_data(data):
    result = []
    append = result.append  # 局部变量，加速
    for item in data:
        append(item)
    return result

# ❌ 频繁属性访问
def process_data_slow(data):
    result = []
    for item in data:
        result.append(item)  # 每次都访问 result
    return result

# ✅ 预计算值
def calculate_values(items):
    # 预计算常用值
    count = len(items)
    sum_value = sum(item.value for item in items)
    avg_value = sum_value / count if count > 0 else 0
    return {'count': count, 'avg': avg_value}
```

### 内存优化

```python
# ✅ 生成器（惰性求值）
def process_large_dataset(data):
    for item in data:
        yield process_item(item)

# ❌ 列表（立即求值）
def process_large_dataset_slow(data):
    return [process_item(item) for item in data]

# ✅ 分块处理
def process_in_chunks(data, chunk_size=1000):
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        yield process_chunk(chunk)
```

## 安全规范

### 输入验证

```python
def validate_doc_id(doc_id: str) -> str:
    """验证文档 ID。"""
    if not doc_id:
        raise ValueError("文档 ID 不能为空")

    if ':' not in doc_id:
        raise ValueError("文档 ID 必须包含 ':'")

    # 长度限制
    if len(doc_id) > 256:
        raise ValueError("文档 ID 过长")

    return doc_id
```

### 参数化查询

```python
# ✅ 始终使用参数化
conn.execute(
    text("SELECT * FROM users WHERE age > :age"),
    {"age": 25}
)

# ❌ 字符串拼接（SQL 注入风险）
age = 25
conn.execute(
    text(f"SELECT * FROM users WHERE age > {age}")
)
```

### 敏感信息

```python
import os

# ✅ 使用环境变量
PASSWORD = os.getenv('COUCHDB_PASSWORD')

# ❌ 硬编码密码
PASSWORD = 'password123'
```

## Git 提交规范

### 提交信息格式

```
type(scope): subject

body

footer
```

**类型**:
- `feat`: 新功能
- `fix`: 修复
- `docs`: 文档更新
- `style`: 代码格式
- `refactor`: 重构
- `test`: 测试
- `chore`: 构建/工具

**示例**:

```
feat(compiler): 添加 ORDER BY 支持

- 实现 _compile_order_by 方法
- 自动创建索引
- 添加测试用例

Closes #123
```

## 代码审查检查表

### 功能正确性

- [ ] 代码完成所需功能
- [ ] 包含单元测试
- [ ] 通过所有测试
- [ ] 异常处理完整

### 代码质量

- [ ] 遵循 PEP 8
- [ ] 类型提示完整
- [ ] 文档字符串清晰
- [ ] 无死代码

### 性能

- [ ] 无明显性能问题
- [ ] 资源正确释放
- [ ] 避免不必要的计算

### 安全

- [ ] 无安全漏洞
- [ ] 参数化查询
- [ ] 输入验证
- [ ] 无硬编码敏感信息

## 工具配置

### Black (代码格式化)

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
```

### isort (导入排序)

```toml
# pyproject.toml
[tool.isort]
profile = "black"
multi_line_output = 3
line_length = 88
```

### mypy (类型检查)

```ini
# mypy.ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

[mypy-sqlalchemy_couchdb.*]
ignore_missing_imports = True
```

### pytest (测试)

```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --strict-markers
markers =
    unit: 单元测试
    integration: 集成测试
    slow: 慢速测试
```

## 下一步

- [测试指南](testing.md)
- [性能优化](performance.md)
- [贡献指南](../about/contributing.md)
