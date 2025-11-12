"""
异步 DBAPI 2.0 实现

提供符合 DB-API 2.0 规范的异步连接和游标对象。
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy_couchdb.client import AsyncCouchDBClient
from sqlalchemy_couchdb.exceptions import ProgrammingError


class AsyncConnection:
    """
    DBAPI 2.0 异步连接对象

    代表与 CouchDB 数据库的异步连接。
    """

    def __init__(self, client: AsyncCouchDBClient):
        """
        初始化异步连接

        参数:
            client: AsyncCouchDBClient 实例
        """
        self.client = client
        self._closed = False

    def cursor(self) -> "AsyncCursor":
        """
        创建异步游标对象

        返回:
            AsyncCursor 实例
        """
        if self._closed:
            raise ProgrammingError("无法在已关闭的连接上创建游标")

        return AsyncCursor(self)

    def commit(self):
        """
        提交事务（同步）

        注意: CouchDB 自动提交每个操作，此方法为空操作。
        SQLAlchemy 在 greenlet 外部同步调用此方法。
        """
        # CouchDB 没有事务概念，自动提交
        pass

    def rollback(self):
        """
        回滚事务（同步）

        注意: CouchDB 不支持事务回滚，此方法为空操作。
        SQLAlchemy 在 greenlet 外部同步调用此方法。
        """
        # CouchDB 自动提交，不支持回滚
        # 为了兼容性，不抛出异常
        pass

    async def close(self):
        """关闭异步连接"""
        if not self._closed:
            await self.client.close()
            self._closed = True

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()


class AsyncCursor:
    """
    DBAPI 2.0 异步游标对象

    用于执行异步查询和获取结果。
    """

    def __init__(self, connection: AsyncConnection):
        """
        初始化异步游标

        参数:
            connection: AsyncConnection 实例
        """
        self.connection = connection
        self.client = connection.client

        # 查询结果
        self._rows: List[Tuple] = []
        self._row_index = 0

        # 游标属性
        self.description: Optional[List[Tuple]] = None
        self.rowcount: int = -1
        self.arraysize: int = 1

        self._closed = False

    async def execute(self, operation: str, parameters: Optional[Dict[str, Any]] = None):
        """
        执行数据库操作（异步）

        参数:
            operation: 操作字符串
            parameters: 参数字典

        返回:
            self
        """
        if self._closed:
            raise ProgrammingError("无法在已关闭的游标上执行操作")

        # 重置状态
        self._rows = []
        self._row_index = 0
        self.description = None
        self.rowcount = -1

        try:
            # 特殊命令
            if operation == "PING":
                result = await self.client.ping()
                self._rows = [(result,)]
                self.rowcount = 1
                return self

            # 解析 JSON 操作
            op_data = json.loads(operation)
            op_type = op_data.get("type")

            if op_type == "select":
                await self._execute_select(op_data, parameters)

            elif op_type == "insert":
                await self._execute_insert(op_data, parameters)

            elif op_type == "update":
                await self._execute_update(op_data, parameters)

            elif op_type == "delete":
                await self._execute_delete(op_data, parameters)

            else:
                raise ProgrammingError(f"不支持的操作类型: {op_type}")

        except json.JSONDecodeError as e:
            # 检测是否是原生 SQL（而不是编译后的 JSON）
            if operation.strip().upper().startswith(('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
                raise ProgrammingError(
                    f"CouchDB dialect 不支持原生 SQL 语句。\n"
                    f"收到的语句: {operation[:100]}{'...' if len(operation) > 100 else ''}\n\n"
                    f"请使用 SQLAlchemy Core/ORM API 代替 text() 语句。\n"
                    f"例如：\n"
                    f"  ❌ 错误: session.execute(text('SELECT * FROM users'))\n"
                    f"  ✅ 正确: session.execute(select(users_table))\n\n"
                    f"CouchDB 使用 Mango Query，不是 SQL 数据库。"
                )
            else:
                raise ProgrammingError(f"无法解析操作（期望 JSON 格式）: {e}\n操作内容: {operation[:100]}")

        return self

    async def _execute_select(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 SELECT 查询（异步）"""
        selector = op_data.get("selector", {})
        fields = op_data.get("fields")
        limit = op_data.get("limit")
        skip = op_data.get("skip", 0)
        sort = op_data.get("sort")
        is_count = op_data.get("is_count", False)

        # 应用参数
        if parameters:
            selector = self._apply_parameters(selector, parameters)

        # 执行查询
        docs = await self.client.find(
            selector=selector, fields=fields, limit=limit, skip=skip, sort=sort
        )

        # COUNT 查询特殊处理
        if is_count:
            # 返回分段计数结果
            count = len(docs)
            # 总数估算 = skip + 当前段的数量
            estimated_total = skip + count
            # 如果当前段查满了，说明可能还有更多数据
            has_more = (count == limit)

            # 返回格式：[(estimated_total,)]
            self.description = [("count", None, None, None, None, None, None)]
            self._rows = [(estimated_total,)]
            self.rowcount = 1
            # 存储元数据，供上层使用
            self._count_metadata = {
                "segment_count": count,
                "skip": skip,
                "has_more": has_more,
                "estimated_total": estimated_total
            }
            return

        # 普通查询：转换为行
        if docs:
            if fields:
                columns = fields
            else:
                columns = list(docs[0].keys())

            self.description = [(col, None, None, None, None, None, None) for col in columns]
            self._rows = [tuple(doc.get(col) for col in columns) for doc in docs]
            self.rowcount = len(self._rows)
        else:
            self.rowcount = 0

    async def _execute_insert(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 INSERT 操作（异步）"""
        doc = op_data.get("document", {})

        if parameters:
            doc = self._apply_parameters(doc, parameters)

        result = await self.client.create_document(doc)
        self.rowcount = 1

        self._rows = [(result["id"], result["rev"])]
        self.description = [
            ("id", None, None, None, None, None, None),
            ("rev", None, None, None, None, None, None),
        ]

    async def _execute_update(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 UPDATE 操作（异步）"""
        selector = op_data.get("selector", {})
        updates = op_data.get("updates", {})

        if parameters:
            selector = self._apply_parameters(selector, parameters)
            updates = self._apply_parameters(updates, parameters)

        # 查找要更新的文档
        docs = await self.client.find(selector=selector)

        # 更新每个文档
        updated_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            doc_rev = doc["_rev"]
            updated_doc = {**doc, **updates}

            await self.client.update_document(doc_id, updated_doc, doc_rev)
            updated_count += 1

        self.rowcount = updated_count

    async def _execute_delete(self, op_data: Dict, parameters: Optional[Dict]):
        """执行 DELETE 操作（异步）"""
        selector = op_data.get("selector", {})

        if parameters:
            selector = self._apply_parameters(selector, parameters)

        # 查找要删除的文档
        docs = await self.client.find(selector=selector)

        # 删除每个文档
        deleted_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            doc_rev = doc["_rev"]

            await self.client.delete_document(doc_id, doc_rev)
            deleted_count += 1

        self.rowcount = deleted_count

    def _apply_parameters(self, data: Any, parameters: Dict) -> Any:
        """递归应用参数到数据结构"""
        if isinstance(data, dict):
            return {k: self._apply_parameters(v, parameters) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._apply_parameters(item, parameters) for item in data]
        elif isinstance(data, str) and data.startswith(":"):
            param_name = data[1:]
            value = parameters.get(param_name, data)
            return self._serialize_value(value)
        else:
            return data

    def _serialize_value(self, value: Any) -> Any:
        """序列化值为 JSON 兼容格式"""
        from datetime import datetime, date

        if value is None:
            return None
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, (dict, list, str, int, float, bool)):
            return value
        else:
            return str(value)

    async def executemany(self, operation: str, seq_of_parameters: List[Dict[str, Any]]):
        """
        执行批量操作（异步）

        对于 INSERT 操作，使用 CouchDB 的 _bulk_docs API 进行批量插入。
        对于其他操作类型，回退到逐条执行。

        参数:
            operation: 操作字符串（JSON格式）
            seq_of_parameters: 参数字典列表

        返回:
            self（支持链式调用）
        """
        if self._closed:
            from sqlalchemy_couchdb.exceptions import ProgrammingError

            raise ProgrammingError("无法在已关闭的游标上执行操作")

        if not seq_of_parameters:
            # 空参数列表，直接返回
            return self

        # 重置状态
        self._rows = []
        self._row_index = 0
        self.description = None
        self.rowcount = -1

        try:
            # 解析操作
            op_data = json.loads(operation)
            op_type = op_data.get("type")

            if op_type == "insert":
                # INSERT 批量操作 - 使用 _bulk_docs
                await self._execute_bulk_insert(op_data, seq_of_parameters)
            else:
                # 其他操作 - 回退到循环执行
                for parameters in seq_of_parameters:
                    await self.execute(operation, parameters)

        except json.JSONDecodeError as e:
            from sqlalchemy_couchdb.exceptions import ProgrammingError

            raise ProgrammingError(f"无法解析操作: {e}")

        return self

    async def _execute_bulk_insert(self, op_data: Dict, seq_of_parameters: List[Dict]):
        """
        执行批量 INSERT 操作（异步）

        使用 CouchDB 的 _bulk_docs API 一次性插入多条文档。

        参数:
            op_data: 操作数据（包含表名和文档模板）
            seq_of_parameters: 参数字典列表
        """
        table = op_data.get("table")
        doc_template = op_data.get("document", {})

        # 构建批量文档列表
        documents = []
        for parameters in seq_of_parameters:
            # 复制文档模板
            doc = doc_template.copy()

            # 应用参数
            if parameters:
                doc = self._apply_parameters(doc, parameters)

            documents.append(doc)

        # 调用 bulk_docs API（异步）
        from sqlalchemy_couchdb.exceptions import IntegrityError

        results = await self.client.bulk_docs(documents)

        # 处理结果
        success_count = 0
        errors = []

        for idx, result in enumerate(results):
            if result.get("error"):
                # 记录错误
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
                    for e in errors[:5]  # 最多显示5个错误
                ]
            )
            if len(errors) > 5:
                error_details += f"\n  ... 以及其他 {len(errors) - 5} 个错误"

            raise IntegrityError(f"{error_summary}\n{error_details}")

        # 设置返回结果
        self.rowcount = success_count

        # 构建返回的行（_id, _rev）
        self._rows = [
            (result.get("id"), result.get("rev")) for result in results if not result.get("error")
        ]

        # 设置列描述
        self.description = [
            ("id", None, None, None, None, None, None),
            ("rev", None, None, None, None, None, None),
        ]

    def fetchone(self) -> Optional[Tuple]:
        """
        获取下一行（同步）

        注意: 结果在 execute() 时已经获取并缓存，
        此方法只是从缓存中返回数据（同步操作）。
        """
        if self._row_index < len(self._rows):
            row = self._rows[self._row_index]
            self._row_index += 1
            return row
        return None

    def fetchmany(self, size: Optional[int] = None) -> List[Tuple]:
        """
        获取多行（同步）

        注意: 结果在 execute() 时已经获取并缓存，
        此方法只是从缓存中返回数据（同步操作）。
        """
        if size is None:
            size = self.arraysize

        rows = self._rows[self._row_index : self._row_index + size]
        self._row_index += len(rows)
        return rows

    def fetchall(self) -> List[Tuple]:
        """
        获取所有剩余行（同步）

        注意: 结果在 execute() 时已经获取并缓存，
        此方法只是从缓存中返回数据（同步操作）。
        """
        rows = self._rows[self._row_index :]
        self._row_index = len(self._rows)
        return rows

    def close(self):
        """
        关闭游标（同步）

        注意：SQLAlchemy 在 greenlet 外部同步调用此方法。
        """
        self._closed = True
        self._rows = []

    async def _async_soft_close(self):
        """
        异步软关闭游标

        SQLAlchemy 2.0+ 异步支持所需的方法。
        "软"关闭意味着不清理结果数据，只做必要的清理工作。
        在 CouchDB dialect 中，结果已经缓存在内存中，不需要额外清理。
        """
        # 软关闭：不清理结果，保持 _rows 和 _row_index 不变
        # 这样用户仍然可以使用 fetchall() 等方法获取结果
        pass

    def __iter__(self):
        """同步迭代器接口"""
        return self

    def __next__(self):
        """获取下一行（同步迭代器）"""
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row

    def __aiter__(self):
        """异步迭代器接口"""
        # 重置迭代位置
        self._async_iter_index = self._row_index
        return self

    async def __anext__(self):
        """获取下一行（异步迭代器）"""
        if self._async_iter_index >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._async_iter_index]
        self._async_iter_index += 1
        return row
