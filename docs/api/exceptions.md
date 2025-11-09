# 异常处理 API

## 概述

SQLAlchemy CouchDB 提供完整的 DB-API 2.0 异常处理系统。

## 异常层次结构

```
StandardError (Python)
├── DatabaseError
│   ├── CouchDBError (基础异常)
│   ├── NotFoundError (404)
│   ├── DocumentConflictError (409)
│   └── InvalidRequestError (400)
├── OperationalError
│   ├── ConnectionError
│   └── TimeoutError
├── IntegrityError
│   └── UniqueConstraintError
└── InternalError
```

## 基类异常

### CouchDBError

所有 CouchDB 相关错误的基类。

```python
class CouchDBError(DatabaseError):
    """CouchDB 基础异常"""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[dict] = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)
```

**属性**:
- `error_code`: 错误代码
- `details`: 详细信息字典

**示例**:
```python
from sqlalchemy_couchdb.exceptions import CouchDBError

try:
    # 操作
    pass
except CouchDBError as e:
    print(f"错误: {e}")
    print(f"代码: {e.error_code}")
    print(f"详情: {e.details}")
```

## 连接异常

### ConnectionError

连接相关错误。

```python
class ConnectionError(OperationalError):
    """无法连接到 CouchDB"""

    pass
```

**常见场景**:
- CouchDB 服务未启动
- 主机不可达
- 端口被拒绝
- SSL 错误

**示例**:
```python
from sqlalchemy_couchdb.exceptions import ConnectionError

try:
    engine = create_engine('couchdb://localhost:5984/nonexistent')
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
except ConnectionError as e:
    print(f"连接失败: {e}")
```

### TimeoutError

超时错误。

```python
class TimeoutError(OperationalError):
    """请求超时"""

    pass
```

## 文档异常

### NotFoundError

文档不存在。

```python
class NotFoundError(CouchDBError):
    """文档未找到 (404)"""

    pass
```

**示例**:
```python
from sqlalchemy_couchdb.exceptions import NotFoundError

try:
    doc = client.get("nonexistent:doc")
except NotFoundError:
    print("文档不存在")
```

### DocumentConflictError

文档版本冲突（乐观锁）。

```python
class DocumentConflictError(CouchDBError):
    """文档版本冲突 (409)"""

    pass
```

**示例**:
```python
from sqlalchemy_couchdb.exceptions import DocumentConflictError

try:
    # 尝试更新过期文档
    conn.execute(text("""
        UPDATE users
        SET age = 31
        WHERE _id = 'user:123'
    """))
except DocumentConflictError:
    print("文档已被修改，请重试")
```

**解决方式**:
```python
def update_with_retry(conn, doc_id, new_data, max_retries=3):
    """带重试的更新"""
    for attempt in range(max_retries):
        try:
            result = conn.execute(text("UPDATE ..."), new_data)
            conn.commit()
            return result
        except DocumentConflictError:
            if attempt == max_retries - 1:
                raise
            # 重新获取最新文档
            time.sleep(0.1)
```

## 请求异常

### InvalidRequestError

无效请求。

```python
class InvalidRequestError(CouchDBError):
    """无效请求 (400)"""

    pass
```

**常见原因**:
- SQL 语法错误
- 缺少必需字段
- 无效的 JSON
- 不支持的查询

**示例**:
```python
from sqlalchemy_couchdb.exceptions import InvalidRequestError

try:
    conn.execute(text("INVALID SQL"))
except InvalidRequestError as e:
    print(f"无效请求: {e}")
```

### QueryError

查询错误。

```python
class QueryError(InvalidRequestError):
    """查询错误"""

    pass
```

## 资源异常

### DatabaseNotFoundError

数据库不存在。

```python
class DatabaseNotFoundError(CouchDBError):
    """数据库不存在"""

    pass
```

**示例**:
```python
try:
    engine = create_engine('couchdb://localhost:5984/nonexistent_db')
except DatabaseNotFoundError:
    print("数据库不存在")
```

### DesignDocumentNotFoundError

设计文档不存在。

```python
class DesignDocumentNotFoundError(CouchDBError):
    """设计文档不存在"""

    pass
```

## 完整性异常

### UniqueConstraintError

唯一约束冲突。

```python
class UniqueConstraintError(IntegrityError):
    """唯一约束冲突"""

    pass
```

**场景**:
- 插入重复的 `_id`
- 违反唯一索引

**示例**:
```python
from sqlalchemy_couchdb.exceptions import UniqueConstraintError

try:
    conn.execute(text("""
        INSERT INTO users (_id, name, type)
        VALUES ('user:123', 'Alice', 'user')
    """))
    conn.commit()

    # 再次插入相同 ID
    conn.execute(text("""
        INSERT INTO users (_id, name, type)
        VALUES ('user:123', 'Bob', 'user')
    """))
    conn.commit()
except UniqueConstraintError:
    print("用户 ID 已存在")
```

## 内部异常

### InternalError

内部错误。

```python
class InternalError(CouchDBError):
    """内部错误 (500)"""

    pass
```

**常见原因**:
- CouchDB 内部错误
- 内存不足
- 磁盘空间不足
- 视图构建失败

## 异常转换

### HTTP 错误映射

```python
from httpx import Response

def convert_http_error(response: Response) -> CouchDBError:
    """将 HTTP 响应转换为异常"""
    status_code = response.status_code

    if status_code == 400:
        return InvalidRequestError(response.text)
    elif status_code == 404:
        if 'database' in response.text.lower():
            return DatabaseNotFoundError(response.text)
        else:
            return NotFoundError(response.text)
    elif status_code == 409:
        return DocumentConflictError(response.text)
    elif status_code == 500:
        return InternalError(response.text)
    else:
        return CouchDBError(response.text)
```

## 错误处理最佳实践

### 1. 捕获特定异常

```python
from sqlalchemy_couchdb.exceptions import (
    NotFoundError,
    DocumentConflictError,
    UniqueConstraintError
)

try:
    conn.execute(text("UPDATE users SET age=31 WHERE _id='user:123'"))
    conn.commit()
except NotFoundError:
    # 文档不存在
    print("用户不存在")
except DocumentConflictError:
    # 版本冲突
    print("用户信息已更新，请刷新后重试")
except UniqueConstraintError:
    # 约束冲突
    print("用户 ID 已存在")
except CouchDBError as e:
    # 其他 CouchDB 错误
    print(f"CouchDB 错误: {e}")
except Exception as e:
    # 通用错误
    print(f"未知错误: {e}")
```

### 2. 重试机制

```python
from functools import wraps
import time
from sqlalchemy_couchdb.exceptions import DocumentConflictError

def retry_on_conflict(max_attempts=3, delay=0.1):
    """文档冲突重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except DocumentConflictError:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_conflict(max_attempts=3)
def update_user(conn, user_id, data):
    """更新用户信息"""
    result = conn.execute(text("""
        UPDATE users
        SET name = :name, age = :age
        WHERE _id = :id AND type = 'user'
    """), data)
    conn.commit()
    return result
```

### 3. 错误上下文

```python
from contextlib import contextmanager

@contextmanager
def error_handler(operation):
    """错误处理上下文管理器"""
    try:
        yield
    except NotFoundError:
        print(f"{operation}: 资源不存在")
    except DocumentConflictError:
        print(f"{operation}: 资源已更新，请重试")
    except ConnectionError:
        print(f"{operation}: 连接错误，请检查网络")
    except CouchDBError as e:
        print(f"{operation}: CouchDB 错误 - {e}")
    except Exception as e:
        print(f"{operation}: 未知错误 - {e}")

# 使用
with error_handler("更新用户"):
    conn.execute(text("UPDATE ..."))
    conn.commit()
```

### 4. 记录错误

```python
import logging

logger = logging.getLogger(__name__)

try:
    conn.execute(text("..."))
    conn.commit()
except CouchDBError as e:
    logger.error(f"CouchDB 错误: {e}", extra={
        'error_code': e.error_code,
        'details': e.details
    })
    raise
```

## 调试技巧

### 1. 启用详细日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy_couchdb').setLevel(logging.DEBUG)
```

### 2. 打印完整错误信息

```python
import traceback

try:
    conn.execute(text("..."))
except Exception as e:
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {e}")
    print(f"堆栈跟踪:\n{traceback.format_exc()}")
```

### 3. 检查异常属性

```python
except CouchDBError as e:
    print(f"错误代码: {e.error_code}")
    print(f"详细信息: {e.details}")
    print(f"原始消息: {str(e)}")
```

## 测试异常

### 测试异常抛出

```python
import pytest
from sqlalchemy_couchdb.exceptions import NotFoundError

def test_not_found():
    with pytest.raises(NotFoundError):
        client.get("nonexistent")

def test_document_conflict():
    with pytest.raises(DocumentConflictError):
        # 触发冲突
        conn.execute(text("UPDATE ..."))
```

### 测试异常属性

```python
def test_error_attributes():
    try:
        client.get("nonexistent")
    except NotFoundError as e:
        assert e.error_code is not None
        assert isinstance(e.details, dict)
```

## 相关资源

- [DB-API 2.0 规范](https://www.python.org/dev/peps/pep-0249/)
- [SQLAlchemy 异常](https://docs.sqlalchemy.org/en/14/core/exceptions.html)
- [CouchDB 错误文档](https://docs.couchdb.org/en/stable/api/basics.html)
