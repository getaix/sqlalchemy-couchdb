"""
辅助函数 - 简化常见操作

提供便捷的批量操作接口，绕过SQLAlchemy参数绑定的限制。
"""

import uuid
from typing import List, Dict, Any
from sqlalchemy import Table
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine


def bulk_insert(engine, table: Table, records: List[Dict[str, Any]]) -> int:
    """
    批量插入记录

    使用CouchDB的_bulk_docs API进行高效的批量插入。
    绕过SQLAlchemy的参数绑定机制，直接使用Client。

    参数:
        engine: SQLAlchemy Engine对象（同步或异步）
        table: 要插入的表对象
        records: 记录列表，每个记录是一个字典

    返回:
        插入的记录数

    示例:
        >>> from sqlalchemy_couchdb.helpers import bulk_insert
        >>> users = Table('users', metadata, ...)
        >>> records = [
        ...     {'name': 'Alice', 'age': 30},
        ...     {'name': 'Bob', 'age': 25},
        ... ]
        >>> count = bulk_insert(engine, users, records)
        >>> print(f"插入了 {count} 条记录")

    注意:
        - 此函数绕过SQLAlchemy ORM和Core API，直接使用HTTP Client
        - 使用CouchDB的_bulk_docs API，性能优于逐条插入
        - 不会触发SQLAlchemy的事件系统
        - 记录中的_id字段如果未提供会自动生成UUID
        - 记录中的_rev字段会被忽略（新插入的文档不需要_rev）
    """
    if not isinstance(engine, Engine):
        raise TypeError("bulk_insert 需要同步的 Engine 对象，对于异步引擎请使用 async_bulk_insert")

    # 获取 client
    raw_conn = engine.raw_connection()
    try:
        client = raw_conn.client

        # 构建文档列表
        documents = []
        for record in records:
            doc = {"type": table.name}

            # 如果记录中有 _id，使用它；否则生成 UUID
            if "_id" in record:
                doc["_id"] = record["_id"]
            else:
                doc["_id"] = str(uuid.uuid4())

            # 如果记录中有 _rev，也添加（用于更新文档）
            if "_rev" in record:
                doc["_rev"] = record["_rev"]

            # 添加其他字段
            for key, value in record.items():
                if key not in ("_id", "_rev"):
                    doc[key] = value

            documents.append(doc)

        # 调用 bulk_docs
        from sqlalchemy_couchdb.exceptions import IntegrityError

        results = client.bulk_docs(documents)

        # 统计成功数量
        success_count = 0
        errors = []

        for idx, result in enumerate(results):
            if result.get("error"):
                errors.append(
                    {
                        "index": idx,
                        "error": result.get("error"),
                        "reason": result.get("reason"),
                        "id": result.get("id"),
                    }
                )
            else:
                success_count += 1

        # 如果有错误，抛出异常
        if errors:
            error_summary = f"批量插入部分失败: {len(errors)}/{len(results)} 失败"
            error_details = "\n".join(
                [
                    f"  [{e['index']}] {e['error']}: {e['reason']} (id={e.get('id', 'N/A')})"
                    for e in errors[:5]
                ]
            )
            if len(errors) > 5:
                error_details += f"\n  ... 以及其他 {len(errors) - 5} 个错误"

            raise IntegrityError(f"{error_summary}\n{error_details}")

        return success_count

    finally:
        raw_conn.close()


async def async_bulk_insert(engine, table: Table, records: List[Dict[str, Any]]) -> int:
    """
    异步批量插入记录

    异步版本的bulk_insert函数。

    参数:
        engine: SQLAlchemy AsyncEngine对象
        table: 要插入的表对象
        records: 记录列表，每个记录是一个字典

    返回:
        插入的记录数

    示例:
        >>> from sqlalchemy_couchdb.helpers import async_bulk_insert
        >>> users = Table('users', metadata, ...)
        >>> records = [
        ...     {'name': 'Alice', 'age': 30},
        ...     {'name': 'Bob', 'age': 25},
        ... ]
        >>> count = await async_bulk_insert(async_engine, users, records)
        >>> print(f"插入了 {count} 条记录")
    """
    if not isinstance(engine, AsyncEngine):
        raise TypeError(
            "async_bulk_insert 需要异步的 AsyncEngine 对象，对于同步引擎请使用 bulk_insert"
        )

    # 获取 client - 使用 connect() 方法
    async with engine.connect() as conn:
        # 获取原始连接
        raw_conn = await conn.get_raw_connection()
        client = raw_conn.driver_connection.client

        # 构建文档列表
        documents = []
        for record in records:
            doc = {"type": table.name}

            # 如果记录中有 _id，使用它；否则生成 UUID
            if "_id" in record:
                doc["_id"] = record["_id"]
            else:
                doc["_id"] = str(uuid.uuid4())

            # 如果记录中有 _rev，也添加（用于更新文档）
            if "_rev" in record:
                doc["_rev"] = record["_rev"]

            # 添加其他字段
            for key, value in record.items():
                if key not in ("_id", "_rev"):
                    doc[key] = value

            documents.append(doc)

        # 调用 bulk_docs
        from sqlalchemy_couchdb.exceptions import IntegrityError

        results = await client.bulk_docs(documents)

        # 统计成功数量
        success_count = 0
        errors = []

        for idx, result in enumerate(results):
            if result.get("error"):
                errors.append(
                    {
                        "index": idx,
                        "error": result.get("error"),
                        "reason": result.get("reason"),
                        "id": result.get("id"),
                    }
                )
            else:
                success_count += 1

        # 如果有错误，抛出异常
        if errors:
            error_summary = f"批量插入部分失败: {len(errors)}/{len(results)} 失败"
            error_details = "\n".join(
                [
                    f"  [{e['index']}] {e['error']}: {e['reason']} (id={e.get('id', 'N/A')})"
                    for e in errors[:5]
                ]
            )
            if len(errors) > 5:
                error_details += f"\n  ... 以及其他 {len(errors) - 5} 个错误"

            raise IntegrityError(f"{error_summary}\n{error_details}")

        return success_count
