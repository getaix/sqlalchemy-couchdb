# 测试指南

## 概述

SQLAlchemy CouchDB 方言使用 pytest 进行测试，测试覆盖编译器、同步和异步操作。

## 测试环境设置

### 1. 安装开发依赖

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
```

### 2. 启动 CouchDB

```bash
# 使用 Docker
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  --name couchdb-test couchdb:3

# 等待服务启动
sleep 5

# 创建测试数据库
curl -X PUT http://admin:password@localhost:5984/testdb
```

### 3. 验证安装

```bash
# 检查 Python 包
python -c "import sqlalchemy_couchdb; print(sqlalchemy_couchdb.__version__)"

# 检查测试
pytest --version
```

## 运行测试

### 所有测试

```bash
# 运行所有测试
pytest tests/

# 带详细输出
pytest tests/ -v

# 带覆盖率报告
pytest tests/ --cov=sqlalchemy_couchdb --cov-report=html --cov-report=term-missing
```

### 特定测试类别

```bash
# 编译器测试
pytest tests/test_compiler.py -v

# 同步测试
pytest tests/test_sync.py -v

# 异步测试
pytest tests/test_async.py -v

# 集成测试
pytest tests/test_couchdb_integration.py -v
```

### 单个测试

```bash
# 运行特定测试方法
pytest tests/test_compiler.py::TestSelectCompilation::test_simple_select -v

# 运行测试类
pytest tests/test_compiler.py::TestSelectCompilation -v
```

### 测试标记

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 只运行同步测试
pytest -m sync

# 只运行异步测试
pytest -m async_

# 跳过慢速测试
pytest -m "not slow"
```

## 测试结构

### 测试目录结构

```
tests/
├── conftest.py                 # pytest 配置和 fixtures
├── test_compiler.py           # 编译器测试
├── test_sync.py               # 同步操作测试
├── test_async.py              # 异步操作测试
├── test_couchdb_integration.py # 集成测试
├── test_types.py              # 类型系统测试
├── test_exceptions.py         # 异常测试
└── unit/                      # 单元测试
    ├── test_compiler_unit.py
    ├── test_client_unit.py
    └── test_dialect_unit.py
```

### 核心测试文件

#### test_compiler.py

测试 SQL → Mango Query 转换。

```python
class TestSelectCompilation:
    """SELECT 编译测试"""

    def test_simple_select(self, dialect):
        """简单 SELECT 编译"""
        sql = text("SELECT * FROM users WHERE type = 'user'")
        compiler = CouchDBCompiler(dialect, sql)
        mango = compiler.visit_select(sql)

        assert mango['selector'] == {"type": {"$eq": "user"}}
        assert "fields" in mango
        assert "limit" in mango

    def test_where_conditions(self, dialect):
        """WHERE 条件编译"""
        sql = text("""
            SELECT * FROM users
            WHERE type = 'user' AND age > 25
        """)
        compiler = CouchDBCompiler(dialect, sql)
        mango = compiler.visit_select(sql)

        assert mango['selector']['type'] == {"$eq": "user"}
        assert mango['selector']['age'] == {"$gt": 25}

    def test_order_by(self, dialect):
        """ORDER BY 编译"""
        sql = text("""
            SELECT * FROM users
            ORDER BY age DESC, name ASC
        """)
        compiler = CouchDBCompiler(dialect, sql)
        mango = compiler.visit_select(sql)

        assert mango['sort'] == [
            {"age": "desc"},
            {"name": "asc"}
        ]
```

#### test_sync.py

测试同步操作。

```python
class TestSyncCRUD:
    """同步 CRUD 测试"""

    @pytest.fixture
    def engine(self):
        """创建测试引擎"""
        engine = create_engine('couchdb://admin:password@localhost:5984/testdb')
        yield engine
        engine.dispose()

    def test_insert(self, engine):
        """插入测试"""
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id, :name, :age, 'user')
            """), {
                'id': 'test:user:1',
                'name': 'Test User',
                'age': 30
            })
            conn.commit()

        # 验证插入
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM users WHERE _id = 'test:user:1'
            """))
            row = result.fetchone()
            assert row.name == 'Test User'
            assert row.age == 30

    def test_select(self, engine):
        """查询测试"""
        # 先插入数据
        self.test_insert(engine)

        # 查询
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM users WHERE type = 'user'
            """))

            rows = result.fetchall()
            assert len(rows) > 0
            assert rows[0].name == 'Test User'

    def test_update(self, engine):
        """更新测试"""
        # 先插入数据
        self.test_insert(engine)

        # 更新
        with engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE users
                SET age = :age
                WHERE _id = :id AND type = 'user'
                RETURNING *
            """), {
                'id': 'test:user:1',
                'age': 31
            })

            updated_row = result.fetchone()
            assert updated_row.age == 31
            conn.commit()

    def test_delete(self, engine):
        """删除测试"""
        # 先插入数据
        self.test_insert(engine)

        # 删除
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM users
                WHERE _id = :id AND type = 'user'
            """), {
                'id': 'test:user:1'
            })
            conn.commit()

        # 验证删除
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM users WHERE _id = 'test:user:1'
            """))
            assert result.rowcount == 0
```

#### test_async.py

测试异步操作。

```python
class TestAsyncCRUD:
    """异步 CRUD 测试"""

    @pytest.fixture
    async def engine(self):
        """创建异步测试引擎"""
        engine = create_async_engine('couchdb+async://admin:password@localhost:5984/testdb')
        yield engine
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_async_insert(self, engine):
        """异步插入测试"""
        async with engine.connect() as conn:
            await conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id, :name, :age, 'user')
            """), {
                'id': 'async:user:1',
                'name': 'Async User',
                'age': 25
            })
            await conn.commit()

    @pytest.mark.asyncio
    async def test_async_select(self, engine):
        """异步查询测试"""
        # 先插入
        await self.test_async_insert(engine)

        # 查询
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT * FROM users WHERE type = 'user'
            """))

            # 注意：使用同步迭代
            rows = result.fetchall()
            assert len(rows) > 0
            assert rows[0].name == 'Async User'

    @pytest.mark.asyncio
    async def test_concurrent_queries(self, engine):
        """并发查询测试"""
        async with engine.connect() as conn:
            # 并发执行多个查询
            tasks = [
                conn.execute(text("SELECT * FROM users WHERE type = 'user' AND age > :age"), {'age': 20}),
                conn.execute(text("SELECT * FROM users WHERE type = 'user' AND age < :age"), {'age': 30}),
            ]

            results = await asyncio.gather(*tasks)

            assert len(results) == 2
            assert results[0].rowcount >= 0
            assert results[1].rowcount >= 0
```

### conftest.py

全局测试配置。

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

@pytest.fixture(scope='session')
def couchdb_url():
    """CouchDB 连接 URL"""
    return 'couchdb://admin:password@localhost:5984/testdb'

@pytest.fixture
def engine(couchdb_url):
    """同步引擎"""
    engine = create_engine(couchdb_url)
    yield engine
    engine.dispose()

@pytest.fixture
async def async_engine(couchdb_url):
    """异步引擎"""
    engine = create_async_engine(couchdb_url.replace('couchdb://', 'couchdb+async://'))
    yield engine
    await engine.dispose()

@pytest.fixture
def dialect(engine):
    """方言实例"""
    return engine.dialect

@pytest.fixture(scope='session', autouse=True)
def setup_database():
    """设置测试数据库"""
    import httpx

    # 清理现有数据
    try:
        with httpx.Client() as client:
            # 删除测试数据库（如果存在）
            client.delete('http://admin:password@localhost:5984/testdb')
    except:
        pass

    # 创建测试数据库
    with httpx.Client() as client:
        client.put('http://admin:password@localhost:5984/testdb')

    yield

    # 清理
    try:
        with httpx.Client() as client:
            client.delete('http://admin:password@localhost:5984/testdb')
    except:
        pass
```

## 编写测试

### 编写新测试

1. **选择合适的测试文件**:
   - 编译器测试 → `test_compiler.py`
   - 同步操作 → `test_sync.py`
   - 异步操作 → `test_async.py`

2. **使用测试类组织**:
```python
class TestYourFeature:
    """你的功能测试"""

    def test_something(self):
        """测试方法"""
        # Arrange
        ...

        # Act
        ...

        # Assert
        assert ...
```

3. **使用 pytest fixtures**:
```python
class TestYourFeature:
    def test_with_fixture(self, engine, dialect):
        """使用 fixtures"""
        ...
```

### 测试最佳实践

#### 1. 独立测试

```python
# ✅ 好：每个测试独立
def test_insert(self, engine):
    with engine.connect() as conn:
        conn.execute(text("..."), data)
        conn.commit()

    # 验证在同一个测试中
    with engine.connect() as conn:
        result = conn.execute(text("..."))
        assert result.rowcount > 0

# ❌ 差：依赖其他测试
def test_insert(self, engine):
    # 假设测试已经运行
    result = conn.execute(text("..."))
```

#### 2. 清理数据

```python
class TestCleanup:
    def test_with_cleanup(self, engine):
        user_id = 'test:cleanup:1'
        try:
            # 测试操作
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO ..."), {'id': user_id})
                conn.commit()
        finally:
            # 清理
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM users WHERE _id = :id"), {'id': user_id})
                conn.commit()
```

#### 3. 参数化测试

```python
@pytest.mark.parametrize("age,expected_count", [
    (25, 1),
    (30, 2),
    (35, 0),
])
def test_age_filter(self, engine, age, expected_count):
    # 先插入测试数据
    ...

    # 查询
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM users WHERE age > :age
        """), {'age': age})
        assert result.rowcount == expected_count
```

#### 4. 使用标记

```python
import pytest

class TestYourFeature:
    @pytest.mark.unit
    def test_compiler(self, dialect):
        """单元测试：编译器"""
        ...

    @pytest.mark.integration
    def test_real_operation(self, engine):
        """集成测试：真实操作"""
        ...

    @pytest.mark.slow
    def test_performance(self, engine):
        """慢速测试：性能"""
        ...
```

## 代码覆盖率

### 生成覆盖率报告

```bash
# HTML 报告
pytest --cov=sqlalchemy_couchdb --cov-report=html

# 终端报告
pytest --cov=sqlalchemy_couchdb --cov-report=term-missing

# 带详细输出
pytest --cov=sqlalchemy_couchdb --cov-report=term-missing --cov-report=html --cov-append
```

### 查看覆盖率

```bash
# 打开 HTML 报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### 覆盖率目标

- **当前覆盖率**: 64%
- **目标覆盖率**: 80%+
- **新代码**: 必须达到 90%+

## 性能测试

### 基准测试

```python
import time
from contextlib import contextmanager

@contextmanager
def timer():
    """计时器"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"耗时: {elapsed:.3f}s")

class TestPerformance:
    def test_bulk_insert_performance(self, engine):
        """批量插入性能测试"""
        data = [{'id': f'perf:{i}', 'name': f'User{i}', 'type': 'user'}
                for i in range(1000)]

        with timer():
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO users (_id, name, type)
                    VALUES (:id, :name, 'user')
                """), data)
                conn.commit()

        # 验证性能：1000 条记录 < 2 秒
        # assert elapsed < 2.0
```

### 内存测试

```python
import psutil
import os

class TestMemory:
    def test_memory_usage(self, engine):
        """内存使用测试"""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # 执行大量操作
        for i in range(10000):
            with engine.connect() as conn:
                conn.execute(text("INSERT INTO ..."), data)
                conn.commit()

        final_memory = process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB

        # 内存增长 < 100MB
        assert memory_increase < 100
```

## 持续集成

### GitHub Actions 配置

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']

    services:
      couchdb:
        image: couchdb:3
        ports:
          - 5984:5984
        env:
          COUCHDB_USER: admin
          COUCHDB_PASSWORD: password

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Create test database
        run: |
          sleep 5
          curl -X PUT http://admin:password@localhost:5984/testdb

      - name: Run tests
        run: |
          pytest tests/ --cov=sqlalchemy_couchdb --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

## 故障排除

### 常见测试失败

#### 1. 连接失败

```bash
# 错误: 无法连接到 CouchDB
# 解决: 确保 CouchDB 正在运行
docker ps
curl http://localhost:5984/
```

#### 2. 数据库不存在

```bash
# 错误: 数据库不存在
# 解决: 创建测试数据库
curl -X PUT http://admin:password@localhost:5984/testdb
```

#### 3. 测试数据残留

```bash
# 错误: 测试数据冲突
# 解决: 清理测试数据库
curl -X DELETE http://admin:password@localhost:5984/testdb
curl -X PUT http://admin:password@localhost:5984/testdb
```

#### 4. 端口占用

```bash
# 错误: 端口 5984 已被占用
# 解决: 停止现有服务或使用其他端口
lsof -i :5984
docker stop couchdb
```

## 下一步

- [代码规范](coding-standards.md)
- [性能优化](performance.md)
- [贡献指南](../about/contributing.md)
