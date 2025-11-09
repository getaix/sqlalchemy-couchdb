# 性能基准测试示例

## 概述

本示例展示如何使用 SQLAlchemy CouchDB 方言进行性能基准测试。

## 基准测试套件

### 1. CRUD 性能测试

```python
import time
from contextlib import contextmanager
from sqlalchemy import create_engine, text

@contextmanager
def timer(name):
    """计时器"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{name}: {elapsed:.3f}s")

def benchmark_crud(engine, num_ops=1000):
    """CRUD 操作基准测试"""
    print(f"\n{'='*60}")
    print(f"CRUD 性能基准测试 - {num_ops} 操作")
    print(f"{'='*60}")

    # INSERT 测试
    print("\n1. INSERT 测试")
    with timer(f"插入 {num_ops} 条记录"):
        with engine.connect() as conn:
            data = [
                {'id': f'bench:insert:{i}', 'name': f'User{i}', 'age': i % 100, 'type': 'user'}
                for i in range(num_ops)
            ]
            conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id, :name, :age, 'user')
            """), data)
            conn.commit()

    insert_throughput = num_ops / elapsed
    print(f"插入吞吐量: {insert_throughput:.1f} docs/s")

    # SELECT 测试
    print("\n2. SELECT 测试")
    select_count = min(num_ops, 1000)  # 限制查询数量
    with timer(f"查询 {select_count} 次"):
        with engine.connect() as conn:
            for i in range(select_count):
                result = conn.execute(text("""
                    SELECT * FROM users WHERE _id = :id
                """), {'id': f'bench:insert:{i}'})

    select_throughput = select_count / elapsed
    print(f"查询吞吐量: {select_throughput:.1f} ops/s")

    # UPDATE 测试
    print("\n3. UPDATE 测试")
    update_count = min(num_ops, 1000)
    with timer(f"更新 {update_count} 条记录"):
        with engine.connect() as conn:
            for i in range(update_count):
                conn.execute(text("""
                    UPDATE users
                    SET age = age + 1
                    WHERE _id = :id AND type = 'user'
                """), {'id': f'bench:insert:{i}'})
            conn.commit()

    update_throughput = update_count / elapsed
    print(f"更新吞吐量: {update_throughput:.1f} ops/s")

    # DELETE 测试
    print("\n4. DELETE 测试")
    delete_count = min(num_ops, 1000)
    with timer(f"删除 {delete_count} 条记录"):
        with engine.connect() as conn:
            for i in range(delete_count):
                conn.execute(text("""
                    DELETE FROM users
                    WHERE _id = :id AND type = 'user'
                """), {'id': f'bench:delete:{i}'})

    delete_throughput = delete_count / elapsed
    print(f"删除吞吐量: {delete_throughput:.1f} ops/s")

    return {
        'insert': insert_throughput,
        'select': select_throughput,
        'update': update_throughput,
        'delete': delete_throughput
    }

# 运行基准测试
results = benchmark_crud(engine, num_ops=1000)
```

### 2. 并发性能测试

```python
import concurrent.futures
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

def concurrent_select_test(engine, num_threads=10, queries_per_thread=100):
    """并发查询性能测试"""
    print(f"\n{'='*60}")
    print(f"并发查询测试 - {num_threads} 线程，每线程 {queries_per_thread} 查询")
    print(f"{'='*60}")

    def query_task(thread_id):
        """单个线程的查询任务"""
        count = 0
        with engine.connect() as conn:
            for i in range(queries_per_thread):
                result = conn.execute(text("""
                    SELECT COUNT(*) as c FROM users WHERE type = 'user'
                """))
                count += result.fetchone().c
        return count

    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(query_task, i) for i in range(num_threads)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    elapsed = time.time() - start

    total_queries = num_threads * queries_per_thread
    throughput = total_queries / elapsed

    print(f"并发查询完成:")
    print(f"  总查询数: {total_queries}")
    print(f"  总耗时: {elapsed:.3f}s")
    print(f"  吞吐量: {throughput:.1f} queries/s")
    print(f"  平均每个查询: {elapsed/total_queries*1000:.3f}ms")

    return throughput

# 运行并发测试
concurrent_results = concurrent_select_test(engine, num_threads=10, queries_per_thread=100)
```

### 3. 批量操作性能测试

```python
def batch_operations_test(engine):
    """批量操作性能测试"""
    print(f"\n{'='*60}")
    print(f"批量操作性能测试")
    print(f"{'='*60}")

    # 单条插入 vs 批量插入
    batch_sizes = [1, 10, 50, 100, 500, 1000]

    for batch_size in batch_sizes:
        print(f"\n批量大小: {batch_size}")

        # 准备数据
        data = [
            {'id': f'batch:{batch_size}:{i}', 'name': f'User{i}', 'type': 'user'}
            for i in range(batch_size)
        ]

        # 批量插入
        start = time.time()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (_id, name, type)
                VALUES (:id, :name, 'user')
            """), data)
            conn.commit()
        elapsed = time.time() - start

        throughput = batch_size / elapsed
        avg_per_doc = elapsed / batch_size * 1000

        print(f"  耗时: {elapsed:.3f}s")
        print(f"  吞吐量: {throughput:.1f} docs/s")
        print(f"  平均每个文档: {avg_per_doc:.3f}ms")

# 运行批量测试
batch_operations_test(engine)
```

### 4. 异步性能测试

```python
async def async_performance_test(async_engine, num_ops=1000):
    """异步操作性能测试"""
    print(f"\n{'='*60}")
    print(f"异步操作性能测试 - {num_ops} 操作")
    print(f"{'='*60}")

    # 异步批量插入
    print("\n1. 异步批量插入")
    data = [
        {'id': f'async:insert:{i}', 'name': f'User{i}', 'type': 'user'}
        for i in range(num_ops)
    ]

    start = time.time()
    async with async_engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO users (_id, name, type)
            VALUES (:id, :name, 'user')
        """), data)
        await conn.commit()
    elapsed = time.time() - start

    insert_throughput = num_ops / elapsed
    print(f"异步插入吞吐量: {insert_throughput:.1f} docs/s")

    # 异步并发查询
    print("\n2. 异步并发查询")
    query_count = min(num_ops, 1000)

    start = time.time()
    async with async_engine.connect() as conn:
        tasks = []
        for i in range(query_count):
            task = conn.execute(text("""
                SELECT * FROM users WHERE _id = :id
            """), {'id': f'async:insert:{i}'})
            tasks.append(task)

        results = await asyncio.gather(*tasks)
    elapsed = time.time() - start

    async_throughput = query_count / elapsed
    print(f"异步查询吞吐量: {async_throughput:.1f} queries/s")

    return {
        'insert': insert_throughput,
        'select': async_throughput
    }

# 运行异步测试
async_engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')
async_results = asyncio.run(async_performance_test(async_engine, num_ops=5000))
```

### 5. 内存使用测试

```python
import psutil
import os

def memory_usage_test(engine):
    """内存使用测试"""
    print(f"\n{'='*60}")
    print(f"内存使用测试")
    print(f"{'='*60}")

    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    print(f"初始内存: {initial_memory:.2f} MB")

    # 加载大量数据
    with timer("加载 10000 条记录"):
        with engine.connect() as conn:
            data = [
                {'id': f'mem:{i}', 'name': f'User{i}', 'age': i % 100, 'type': 'user'}
                for i in range(10000)
            ]
            conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id, :name, :age, 'user')
            """), data)
            conn.commit()

    peak_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"峰值内存: {peak_memory:.2f} MB")
    print(f"内存增长: {peak_memory - initial_memory:.2f} MB")

    # 查询大量数据（测试结果集内存）
    with timer("查询 10000 条记录"):
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT * FROM users WHERE type = 'user' LIMIT 10000
            """))
            all_rows = result.fetchall()

    query_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"查询后内存: {query_memory:.2f} MB")
    print(f"查询内存增长: {query_memory - peak_memory:.2f} MB")

    # 清理
    with timer("清理数据"):
        with engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM users WHERE _id LIKE 'mem:%'
            """))

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"清理后内存: {final_memory:.2f} MB")

    return {
        'initial': initial_memory,
        'peak': peak_memory,
        'query': query_memory,
        'final': final_memory
    }

# 运行内存测试
memory_results = memory_usage_test(engine)
```

### 6. 完整基准测试报告

```python
def generate_benchmark_report(results):
    """生成基准测试报告"""
    print(f"\n{'='*60}")
    print(f"性能基准测试报告")
    print(f"{'='*60}")

    print("\n📊 CRUD 操作性能:")
    print(f"  INSERT: {results['crud']['insert']:.1f} docs/s")
    print(f"  SELECT: {results['crud']['select']:.1f} ops/s")
    print(f"  UPDATE: {results['crud']['update']:.1f} ops/s")
    print(f"  DELETE: {results['crud']['delete']:.1f} ops/s")

    print("\n🚀 并发查询:")
    print(f"  吞吐量: {results['concurrent']:.1f} queries/s")

    print("\n⚡ 异步操作:")
    print(f"  INSERT: {results['async']['insert']:.1f} docs/s")
    print(f"  SELECT: {results['async']['select']:.1f} queries/s")

    print("\n💾 内存使用:")
    print(f"  初始: {results['memory']['initial']:.2f} MB")
    print(f"  峰值: {results['memory']['peak']:.2f} MB")
    print(f"  查询后: {results['memory']['query']:.2f} MB")

    print(f"\n{'='*60}")
    print(f"基准测试完成")
    print(f"{'='*60}")

# 运行完整基准测试
def run_full_benchmark():
    """运行完整基准测试"""
    engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

    results = {}

    # CRUD 测试
    results['crud'] = benchmark_crud(engine, num_ops=1000)

    # 并发测试
    results['concurrent'] = concurrent_select_test(engine, num_threads=10, queries_per_thread=100)

    # 异步测试
    results['async'] = asyncio.run(async_performance_test(async_engine, num_ops=1000))

    # 内存测试
    results['memory'] = memory_usage_test(engine)

    # 生成报告
    generate_benchmark_report(results)

# 运行完整基准测试
run_full_benchmark()
```

## 性能优化建议

基于基准测试结果：

### 1. 插入优化

- **批量插入**：比单条插入快 10-100 倍
- **推荐批量大小**：100-1000 条记录
- **更大批量**：收益递减，可能导致超时

### 2. 查询优化

- **使用索引**：ORDER BY 字段必须创建索引
- **限制结果集**：始终使用 LIMIT
- **只查询必要字段**：减少数据传输量

### 3. 并发优化

- **连接池大小**：基于并发用户数调整（通常 10-50）
- **线程数**：不超过 CPU 核心数的 2-4 倍
- **异步操作**：适合 I/O 密集型任务

### 4. 内存优化

- **分页查询**：避免一次性加载大量数据
- **流式处理**：使用 fetchmany() 分批获取
- **及时清理**：删除不需要的数据

## 下一步

- [高级特性示例](advanced-features.md)
- [性能优化指南](../dev/performance.md)
- [测试指南](../dev/testing.md)
