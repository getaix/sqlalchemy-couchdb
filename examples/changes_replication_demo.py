"""
CouchDB 变更 Feed 和复制功能示例

演示如何使用变更监听和数据库复制功能。
"""

import time
from sqlalchemy_couchdb.client import SyncCouchDBClient
from sqlalchemy_couchdb.changes import ChangesListener, ChangesFeed, FeedType, Change
from sqlalchemy_couchdb.replication import Replicator, BidirectionalReplicator, ConflictStrategy


# ============================================================================
# 示例 1: 简单的变更监听
# ============================================================================


def example_simple_changes_listener():
    """示例：简单的变更监听"""
    print("\n=== 示例 1: 简单的变更监听 ===\n")

    # 连接到 CouchDB
    client = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="mydb"
    )
    client.connect()

    # 定义变更处理函数
    def on_change(change: Change):
        print(f"变更检测: {change.id}")
        if change.deleted:
            print("  文档已删除")
        elif change.doc:
            print(f"  文档内容: {change.doc.get('name', 'N/A')}")

    # 创建监听器
    listener = ChangesListener(
        client, on_change=on_change, feed_type=FeedType.NORMAL, include_docs=True
    )

    # 获取变更
    result = listener.get_changes(since="0", limit=10)
    print(f"\n共发现 {len(result.results)} 个变更")
    print(f"最后序列号: {result.last_seq}")


# ============================================================================
# 示例 2: 连续变更监听（实时）
# ============================================================================


def example_continuous_changes_listener():
    """示例：连续变更监听"""
    print("\n=== 示例 2: 连续变更监听 ===\n")

    client = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="mydb"
    )
    client.connect()

    # 定义变更处理函数
    changes_count = 0

    def on_change(change: Change):
        nonlocal changes_count
        changes_count += 1
        print(f"[{changes_count}] 实时变更: {change.id}")

    def on_error(error: Exception):
        print(f"错误: {error}")

    # 创建监听器
    listener = ChangesListener(
        client,
        on_change=on_change,
        on_error=on_error,
        feed_type=FeedType.CONTINUOUS,
        include_docs=True,
    )

    # 启动监听
    print("启动连续监听（10秒后自动停止）...")
    listener.start()

    # 模拟创建一些文档
    for i in range(5):
        time.sleep(1)
        client.create_document(
            {
                "_id": f"example:continuous{i}",
                "type": "example",
                "name": f"Document {i}",
                "timestamp": time.time(),
            }
        )

    # 等待
    time.sleep(5)

    # 停止监听
    listener.stop()
    print(f"\n停止监听，共收到 {changes_count} 个变更")


# ============================================================================
# 示例 3: 使用变更 Feed 管理器
# ============================================================================


def example_changes_feed_manager():
    """示例：使用变更 Feed 管理器"""
    print("\n=== 示例 3: 变更 Feed 管理器 ===\n")

    client = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="mydb"
    )
    client.connect()

    # 创建 Feed 管理器
    feed = ChangesFeed(client, buffer_size=50, auto_reconnect=True)

    # 注册多个处理函数
    feed.on_change(lambda change: print(f"处理器 1: {change.id}"))
    feed.on_change(lambda change: print(f"处理器 2: {change.id} - {change.seq}"))

    # 启动 Feed
    print("启动 Feed 管理器...")
    feed.start(feed_type=FeedType.NORMAL, include_docs=True)

    # 等待处理
    time.sleep(3)

    # 查看缓冲区
    buffer = feed.get_buffer()
    print(f"\n缓冲区中有 {len(buffer)} 个变更")

    # 停止
    feed.stop()


# ============================================================================
# 示例 4: 简单数据库复制
# ============================================================================


def example_simple_replication():
    """示例：简单数据库复制"""
    print("\n=== 示例 4: 简单数据库复制 ===\n")

    # 连接到源数据库
    source = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="source_db"
    )
    source.connect()

    # 连接到目标数据库
    target = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="target_db"
    )
    target.connect()

    # 在源数据库创建一些文档
    print("在源数据库创建文档...")
    for i in range(10):
        source.create_document(
            {
                "_id": f"rep:example{i}",
                "type": "example",
                "value": i,
                "description": f"Example document {i}",
            }
        )

    # 创建复制器
    replicator = Replicator(source, target, batch_size=5)  # 每批复制 5 个文档

    # 执行复制
    print("\n开始复制...")
    result = replicator.replicate()

    # 显示结果
    print("\n复制完成！")
    print(f"  读取文档数: {result.stats.docs_read}")
    print(f"  写入文档数: {result.stats.docs_written}")
    print(f"  失败数: {result.stats.doc_write_failures}")
    print(f"  耗时: {result.stats.duration:.2f} 秒")
    print(f"  速度: {result.stats.docs_per_second:.2f} 文档/秒")


# ============================================================================
# 示例 5: 带过滤的复制
# ============================================================================


def example_filtered_replication():
    """示例：带过滤的复制"""
    print("\n=== 示例 5: 带过滤的复制 ===\n")

    source = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="source_db"
    )
    source.connect()

    target = SyncCouchDBClient(
        host="localhost",
        port=5984,
        username="admin",
        password="123456",
        database="target_db_filtered",
    )
    target.connect()

    # 创建文档（包含需要过滤的）
    print("创建文档...")
    for i in range(20):
        source.create_document(
            {
                "_id": f"filter:doc{i}",
                "type": "example",
                "priority": "high" if i % 3 == 0 else "low",
                "value": i,
            }
        )

    # 定义过滤函数（只复制高优先级文档）
    def filter_high_priority(doc):
        return doc.get("priority") == "high"

    # 创建复制器（带过滤）
    replicator = Replicator(source, target, filter_function=filter_high_priority)

    # 执行复制
    print("\n开始过滤复制（只复制 priority=high 的文档）...")
    result = replicator.replicate()

    print("\n复制完成！")
    print(f"  源文档总数: {result.stats.docs_read}")
    print(f"  复制文档数: {result.stats.docs_written}")
    print(f"  过滤率: {(1 - result.stats.docs_written / result.stats.docs_read) * 100:.1f}%")


# ============================================================================
# 示例 6: 冲突解决策略
# ============================================================================


def example_conflict_resolution():
    """示例：冲突解决策略"""
    print("\n=== 示例 6: 冲突解决 ===\n")

    source = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="source_db"
    )
    source.connect()

    target = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="target_db"
    )
    target.connect()

    # 在两个数据库创建冲突的文档
    print("创建冲突文档...")
    source.create_document(
        {
            "_id": "conflict:doc",
            "type": "example",
            "value": "source_value",
            "updated_at": "2025-11-03T10:00:00Z",
        }
    )

    target.create_document(
        {
            "_id": "conflict:doc",
            "type": "example",
            "value": "target_value",
            "updated_at": "2025-11-03T09:00:00Z",
        }
    )

    # 策略 1: 源优先
    print("\n策略 1: 源优先")
    replicator1 = Replicator(source, target, conflict_strategy=ConflictStrategy.SOURCE_WINS)
    result1 = replicator1.replicate()
    doc1 = target.get_document("conflict:doc")
    print(f"  结果: {doc1['value']}")

    # 策略 2: 最新优先
    print("\n策略 2: 最新优先")
    replicator2 = Replicator(source, target, conflict_strategy=ConflictStrategy.LATEST_WINS)
    result2 = replicator2.replicate()
    doc2 = target.get_document("conflict:doc")
    print(f"  结果: {doc2['value']}")


# ============================================================================
# 示例 7: 双向复制
# ============================================================================


def example_bidirectional_replication():
    """示例：双向复制"""
    print("\n=== 示例 7: 双向复制 ===\n")

    db_a = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="db_a"
    )
    db_a.connect()

    db_b = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="db_b"
    )
    db_b.connect()

    # 在两个数据库创建不同的文档
    print("在数据库 A 创建文档...")
    for i in range(5):
        db_a.create_document({"_id": f"bidir:a{i}", "type": "example", "from": "db_a", "value": i})

    print("在数据库 B 创建文档...")
    for i in range(3):
        db_b.create_document({"_id": f"bidir:b{i}", "type": "example", "from": "db_b", "value": i})

    # 创建双向复制器
    replicator = BidirectionalReplicator(db_a, db_b, continuous=False)

    # 执行双向复制
    print("\n开始双向复制...")
    results = replicator.start()

    # 显示统计
    stats = replicator.get_stats()
    print("\n复制完成！")
    print(f"  A -> B: {stats['a_to_b'].docs_written} 个文档")
    print(f"  B -> A: {stats['b_to_a'].docs_written} 个文档")

    # 验证
    print("\n验证同步结果...")
    print(f"  数据库 A 现在有 {len(db_a._get_all_doc_ids())} 个文档")
    print(f"  数据库 B 现在有 {len(db_b._get_all_doc_ids())} 个文档")


# ============================================================================
# 示例 8: 连续双向复制（实时同步）
# ============================================================================


def example_continuous_bidirectional_replication():
    """示例：连续双向复制"""
    print("\n=== 示例 8: 连续双向复制 ===\n")

    db_a = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="db_a"
    )
    db_a.connect()

    db_b = SyncCouchDBClient(
        host="localhost", port=5984, username="admin", password="123456", database="db_b"
    )
    db_b.connect()

    # 创建连续双向复制器
    replicator = BidirectionalReplicator(db_a, db_b, continuous=True)

    # 启动连续复制
    print("启动连续双向复制...")
    replicator.start()

    # 在两个数据库交替创建文档
    print("\n模拟实时变更...")
    for i in range(5):
        time.sleep(1)

        # 在 A 创建
        db_a.create_document(
            {"_id": f"continuous:a{i}", "type": "example", "from": "db_a", "timestamp": time.time()}
        )
        print(f"  在 A 创建文档 continuous:a{i}")

        time.sleep(1)

        # 在 B 创建
        db_b.create_document(
            {"_id": f"continuous:b{i}", "type": "example", "from": "db_b", "timestamp": time.time()}
        )
        print(f"  在 B 创建文档 continuous:b{i}")

    # 等待同步完成
    print("\n等待同步...")
    time.sleep(5)

    # 停止复制
    replicator.stop()

    # 显示统计
    stats = replicator.get_stats()
    print("\n复制完成！")
    print(f"  A -> B: {stats['a_to_b'].docs_written} 个文档")
    print(f"  B -> A: {stats['b_to_a'].docs_written} 个文档")


# ============================================================================
# 主函数
# ============================================================================


def main():
    """运行所有示例"""
    examples = [
        ("简单的变更监听", example_simple_changes_listener),
        ("连续变更监听", example_continuous_changes_listener),
        ("变更 Feed 管理器", example_changes_feed_manager),
        ("简单数据库复制", example_simple_replication),
        ("带过滤的复制", example_filtered_replication),
        ("冲突解决策略", example_conflict_resolution),
        ("双向复制", example_bidirectional_replication),
        ("连续双向复制", example_continuous_bidirectional_replication),
    ]

    print("=" * 80)
    print("CouchDB 变更 Feed 和复制功能示例")
    print("=" * 80)

    for i, (name, func) in enumerate(examples, 1):
        print(f"\n[{i}/{len(examples)}] {name}")
        try:
            func()
        except Exception as e:
            print(f"\n错误: {e}")

        if i < len(examples):
            input("\n按 Enter 继续下一个示例...")

    print("\n" + "=" * 80)
    print("所有示例运行完成！")
    print("=" * 80)


if __name__ == "__main__":
    # 运行所有示例
    main()

    # 或运行单个示例
    # example_simple_changes_listener()
