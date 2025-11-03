"""
高级功能演示

演示 SQLAlchemy CouchDB 驱动的高级功能：
1. 查询缓存
2. 重试机制
3. 索引管理
4. 视图管理
5. 聚合查询
"""

import sys

# 添加父目录到路径（如果需要）
sys.path.insert(0, "..")

from sqlalchemy_couchdb.client import SyncCouchDBClient
from sqlalchemy_couchdb.retry import RetryConfig
from sqlalchemy_couchdb.advanced import QueryProcessor


def demo_query_cache():
    """演示查询缓存功能"""
    print("=" * 60)
    print("演示 1: 查询缓存")
    print("=" * 60)

    # 创建启用缓存的客户端
    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="test_db",
        enable_cache=True,  # 启用缓存
        cache_size=100,
        cache_ttl=300.0,  # 5分钟
    )

    client.connect()

    # 准备测试数据
    print("\n1. 插入测试数据...")
    for i in range(5):
        doc = {"type": "demo_users", "name": f"User{i}", "age": 20 + i}
        client.create_document(doc)

    # 第一次查询（从数据库）
    print("\n2. 第一次查询（从数据库）...")
    selector = {"type": "demo_users", "age": {"$gte": 22}}
    results1 = client.find(selector, use_cache=True)
    print(f"   找到 {len(results1)} 条记录")

    # 第二次查询（从缓存）
    print("\n3. 第二次查询（从缓存）...")
    results2 = client.find(selector, use_cache=True)
    print(f"   找到 {len(results2)} 条记录")

    # 查看缓存统计
    print("\n4. 缓存统计:")
    stats = client.cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # 清空缓存
    print("\n5. 清空缓存...")
    client.cache.clear()

    client.close()
    print("\n✅ 查询缓存演示完成\n")


def demo_retry_mechanism():
    """演示重试机制"""
    print("=" * 60)
    print("演示 2: 重试机制")
    print("=" * 60)

    # 创建带重试配置的客户端
    retry_config = RetryConfig(
        max_retries=3,
        retry_delay=0.5,
        backoff_factor=2.0,
        retry_on_status_codes=(502, 503, 504),
    )

    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="test_db",
        retry_config=retry_config,
    )

    client.connect()

    print("\n✅ 重试机制配置完成")
    print(f"   最大重试次数: {retry_config.max_retries}")
    print(f"   初始延迟: {retry_config.retry_delay}秒")
    print(f"   退避因子: {retry_config.backoff_factor}")
    print(f"   重试状态码: {retry_config.retry_on_status_codes}")

    # 注意：实际重试会在网络错误时自动触发
    # 这里只是展示配置

    client.close()
    print("\n✅ 重试机制演示完成\n")


def demo_index_management():
    """演示索引管理"""
    print("=" * 60)
    print("演示 3: 索引管理")
    print("=" * 60)

    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="test_db",
    )

    client.connect()

    # 获取索引管理器
    index_mgr = client.index_manager

    print("\n1. 创建索引...")
    try:
        result = index_mgr.create_index(fields=["age", "name"], name="idx_demo_age_name")
        print(f"   索引创建成功: {result.get('name')}")
    except Exception as e:
        print(f"   索引可能已存在: {e}")

    print("\n2. 列出所有索引...")
    indexes = index_mgr.list_indexes()
    print(f"   共有 {len(indexes)} 个索引:")
    for idx in indexes[:5]:  # 只显示前5个
        print(f"   - {idx.get('name')}: 字段 {idx.get('def', {}).get('fields')}")

    print("\n3. 查找特定字段的索引...")
    found_idx = index_mgr.find_index_by_fields(["age", "name"])
    if found_idx:
        print(f"   找到索引: {found_idx.get('name')}")
    else:
        print("   未找到匹配的索引")

    client.close()
    print("\n✅ 索引管理演示完成\n")


def demo_view_management():
    """演示视图管理"""
    print("=" * 60)
    print("演示 4: 视图管理")
    print("=" * 60)

    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="test_db",
    )

    client.connect()

    # 获取视图管理器
    view_mgr = client.view_manager

    print("\n1. 创建视图（按年龄统计）...")
    try:
        map_func = """
        function(doc) {
            if (doc.type === 'demo_users' && doc.age) {
                emit(doc.age, 1);
            }
        }
        """

        result = view_mgr.create_view(
            design_doc="analytics",
            view_name="count_by_age",
            map_function=map_func,
            reduce_function="_count",
        )
        print("   视图创建成功")
    except Exception as e:
        print(f"   视图创建错误（可能已存在）: {e}")

    print("\n2. 查询视图...")
    try:
        result = view_mgr.query_view(design_doc="analytics", view_name="count_by_age", group=True)
        print("   查询结果:")
        rows = result.get("rows", [])[:5]  # 只显示前5个
        for row in rows:
            print(f"   年龄 {row['key']}: {row['value']} 人")
    except Exception as e:
        print(f"   查询视图错误: {e}")

    client.close()
    print("\n✅ 视图管理演示完成\n")


def demo_aggregation_queries():
    """演示聚合查询"""
    print("=" * 60)
    print("演示 5: 聚合查询")
    print("=" * 60)

    client = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="test_db",
    )

    client.connect()

    # 插入更多测试数据
    print("\n1. 准备测试数据...")
    test_data = [
        {"type": "employees", "name": "Alice", "department": "Engineering", "salary": 80000},
        {"type": "employees", "name": "Bob", "department": "Engineering", "salary": 75000},
        {"type": "employees", "name": "Charlie", "department": "Sales", "salary": 60000},
        {"type": "employees", "name": "David", "department": "Sales", "salary": 65000},
        {"type": "employees", "name": "Eve", "department": "HR", "salary": 70000},
    ]

    for doc in test_data:
        try:
            client.create_document(doc)
        except Exception:
            pass  # 可能已存在

    # 查询所有员工
    print("\n2. 查询所有员工...")
    results = client.find({"type": "employees"})
    print(f"   共有 {len(results)} 名员工")

    # 使用 QueryProcessor 进行聚合
    print("\n3. 计算平均工资...")
    avg_salary = QueryProcessor.avg(results, "salary")
    print(f"   平均工资: ${avg_salary:,.2f}")

    print("\n4. 计算工资总和...")
    total_salary = QueryProcessor.sum(results, "salary")
    print(f"   工资总和: ${total_salary:,.2f}")

    print("\n5. 查找最高和最低工资...")
    max_salary = QueryProcessor.max(results, "salary")
    min_salary = QueryProcessor.min(results, "salary")
    print(f"   最高工资: ${max_salary:,.2f}")
    print(f"   最低工资: ${min_salary:,.2f}")

    print("\n6. 按部门分组统计...")
    grouped = QueryProcessor.group_by(
        results, group_fields=["department"], aggregate_func="avg", aggregate_field="salary"
    )
    print("   各部门平均工资:")
    for row in grouped:
        print(f"   {row['department']}: ${row['avg_salary']:,.2f}")

    print("\n7. 计数不同部门...")
    dept_count = QueryProcessor.count_distinct(results, "department")
    print(f"   共有 {dept_count} 个不同部门")

    client.close()
    print("\n✅ 聚合查询演示完成\n")


def main():
    """运行所有演示"""
    print("\n" + "=" * 60)
    print("SQLAlchemy CouchDB - 高级功能演示")
    print("=" * 60 + "\n")

    try:
        demo_query_cache()
        demo_retry_mechanism()
        demo_index_management()
        demo_view_management()
        demo_aggregation_queries()

        print("=" * 60)
        print("🎉 所有演示完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 演示过程中出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
