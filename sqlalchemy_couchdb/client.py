"""
CouchDB HTTP 客户端

基于 httpx 实现的同步和异步 CouchDB 客户端，提供完整的 CouchDB REST API 访问。
"""

import httpx
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, quote

from sqlalchemy_couchdb.exceptions import (
    OperationalError,
    exception_from_response,
)
from sqlalchemy_couchdb.retry import RetryConfig
from sqlalchemy_couchdb.cache import QueryCache


class CouchDBClient:
    """
    CouchDB 客户端基类

    提供 CouchDB HTTP API 的基础功能和 URL 构建方法。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5984,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        use_ssl: bool = False,
        enable_cache: bool = False,
        cache_size: int = 100,
        cache_ttl: float = 300.0,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        初始化 CouchDB 客户端

        参数:
            host: CouchDB 服务器地址
            port: CouchDB 服务器端口
            username: 用户名（可选）
            password: 密码（可选）
            database: 数据库名（可选）
            use_ssl: 是否使用 HTTPS
            enable_cache: 是否启用查询缓存（默认 False）
            cache_size: 缓存大小（默认 100）
            cache_ttl: 缓存生存时间（秒，默认 300）
            retry_config: 重试配置（可选）
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database = database
        self.use_ssl = use_ssl

        # 构建基础 URL
        scheme = "https" if use_ssl else "http"
        self.base_url = f"{scheme}://{host}:{port}"

        # 认证信息
        self.auth = (username, password) if username and password else None

        # 查询缓存（可选）
        self.cache: Optional[QueryCache] = None
        if enable_cache:
            self.cache = QueryCache(max_size=cache_size, ttl=cache_ttl)

        # 重试配置
        self.retry_config = retry_config

    def _build_url(self, path: str) -> str:
        """
        构建完整的 URL

        参数:
            path: API 路径（例如: "/_all_dbs" 或 "/mydb/doc_id"）

        返回:
            完整的 URL
        """
        # 确保路径以 / 开头
        if not path.startswith("/"):
            path = f"/{path}"

        return urljoin(self.base_url, path)

    def _build_db_url(self, path: str = "") -> str:
        """
        构建数据库相关的 URL

        参数:
            path: 数据库内的路径（例如: "doc_id" 或 "_find"）

        返回:
            完整的 URL
        """
        if not self.database:
            raise OperationalError("未指定数据库名称")

        if path:
            return self._build_url(f"/{self.database}/{path}")
        else:
            return self._build_url(f"/{self.database}")

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        处理 HTTP 响应

        参数:
            response: httpx 响应对象

        返回:
            解析后的 JSON 数据

        抛出:
            相应的异常（如果响应失败）
        """
        # 检查响应状态
        if response.status_code >= 400:
            raise exception_from_response(response)

        # 解析 JSON
        try:
            return response.json()
        except Exception as e:
            raise OperationalError(f"无法解析 CouchDB 响应: {e}")


class SyncCouchDBClient(CouchDBClient):
    """
    同步 CouchDB 客户端

    使用 httpx.Client 实现同步 HTTP 请求。
    """

    def __init__(self, *args, **kwargs):
        """初始化同步客户端"""
        super().__init__(*args, **kwargs)
        self.client: Optional[httpx.Client] = None
        self._index_manager = None
        self._view_manager = None
        self._query_analyzer = None

    @property
    def index_manager(self):
        """获取索引管理器"""
        if self._index_manager is None:
            from sqlalchemy_couchdb.management import IndexManager

            self._index_manager = IndexManager(self)
        return self._index_manager

    @property
    def view_manager(self):
        """获取视图管理器"""
        if self._view_manager is None:
            from sqlalchemy_couchdb.management import ViewManager

            self._view_manager = ViewManager(self)
        return self._view_manager

    @property
    def query_analyzer(self):
        """获取查询分析器"""
        if self._query_analyzer is None:
            from sqlalchemy_couchdb.query_analyzer import QueryAnalyzer

            self._query_analyzer = QueryAnalyzer()
        return self._query_analyzer

    def analyze_query_index_needs(self, compiled_query: str, format: str = "text") -> str:
        """
        分析编译后的查询并生成索引建议报告

        参数:
            compiled_query: 编译后的 Mango Query JSON 字符串
            format: 报告格式 ("text", "json", "markdown")

        返回:
            格式化的索引建议报告

        示例:
            >>> query = '{"type": "select", "table": "users", "selector": {"age": {"$gt": 25}}, "sort": [{"name": "asc"}]}'
            >>> report = client.analyze_query_index_needs(query)
            >>> print(report)
        """
        from sqlalchemy_couchdb.query_analyzer import IndexAnalysisReport

        analysis, recommendation = self.query_analyzer.analyze_and_recommend(compiled_query)

        report = IndexAnalysisReport()
        if recommendation:
            report.add_recommendation(recommendation)

        return report.generate_report(format=format)

    def connect(self) -> httpx.Client:
        """
        创建 HTTP 客户端连接

        返回:
            httpx.Client 实例
        """
        if self.client is None:
            # 配置连接池
            limits = httpx.Limits(
                max_connections=100,  # 最大连接数
                max_keepalive_connections=20,  # 保持活跃的连接数
            )

            # 配置超时
            timeout = httpx.Timeout(
                connect=5.0,  # 连接超时
                read=30.0,  # 读取超时
                write=10.0,  # 写入超时
                pool=5.0,  # 连接池超时
            )

            self.client = httpx.Client(
                auth=self.auth,
                limits=limits,
                timeout=timeout,
                follow_redirects=True,
            )

        return self.client

    def close(self):
        """关闭客户端连接"""
        if self.client:
            self.client.close()
            self.client = None

    def ping(self) -> bool:
        """
        检查 CouchDB 服务器是否可访问

        返回:
            True 如果服务器可访问，否则 False
        """
        try:
            response = self.client.get(self._build_url("/"))
            return response.status_code == 200
        except Exception:
            return False

    def create_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新文档

        参数:
            doc: 文档内容（字典）

        返回:
            包含 'id' 和 'rev' 的字典

        示例:
            >>> client.create_document({"name": "Alice", "age": 30})
            {'id': 'abc123', 'rev': '1-xyz'}

            >>> client.create_document({"_id": "user:001", "name": "Bob"})
            {'id': 'user:001', 'rev': '1-xyz'}
        """
        # 使文档类型的缓存失效
        if self.cache and "type" in doc:
            self.cache.invalidate(doc["type"])

        # 检查是否指定了 _id
        if "_id" in doc and doc["_id"]:
            # 有指定 _id，使用 PUT 请求到指定的文档 ID
            doc_id = doc["_id"]
            encoded_id = quote(doc_id, safe="")

            # 创建文档副本，移除 _id 字段（CouchDB PUT 请求不需要文档体中的 _id）
            doc_body = {k: v for k, v in doc.items() if k != "_id"}

            response = self.client.put(
                self._build_db_url(encoded_id),
                json=doc_body,
                headers={"Content-Type": "application/json"},
            )
        else:
            # 没有指定 _id，使用 POST 请求让 CouchDB 自动生成 ID
            response = self.client.post(
                self._build_db_url(),
                json=doc,
                headers={"Content-Type": "application/json"},
            )

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    def get_document(self, doc_id: str) -> Dict[str, Any]:
        """
        获取文档

        参数:
            doc_id: 文档 ID

        返回:
            文档内容

        抛出:
            OperationalError: 如果文档不存在
        """
        # URL 编码文档 ID
        encoded_id = quote(doc_id, safe="")
        response = self.client.get(self._build_db_url(encoded_id))
        return self._handle_response(response)

    def update_document(self, doc_id: str, doc: Dict[str, Any], rev: str) -> Dict[str, Any]:
        """
        更新文档

        参数:
            doc_id: 文档 ID
            doc: 新的文档内容
            rev: 当前文档版本号（_rev）

        返回:
            包含 'id' 和 'rev' 的字典

        抛出:
            IntegrityError: 如果 rev 不匹配（文档冲突）
        """
        # 确保文档包含 _rev
        doc["_rev"] = rev

        encoded_id = quote(doc_id, safe="")
        response = self.client.put(
            self._build_db_url(encoded_id),
            json=doc,
            headers={"Content-Type": "application/json"},
        )

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    def delete_document(self, doc_id: str, rev: str) -> Dict[str, Any]:
        """
        删除文档

        参数:
            doc_id: 文档 ID
            rev: 当前文档版本号（_rev）

        返回:
            包含 'id' 和 'rev' 的字典
        """
        encoded_id = quote(doc_id, safe="")
        response = self.client.delete(self._build_db_url(f"{encoded_id}?rev={rev}"))

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    def find(
        self,
        selector: Dict[str, Any],
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort: Optional[List[Dict[str, str]]] = None,
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        使用 Mango Query 查询文档

        参数:
            selector: 查询选择器（Mango Query 语法）
            fields: 要返回的字段列表（可选）
            limit: 最大返回文档数（可选）
            skip: 跳过的文档数（可选）
            sort: 排序规则（可选）
            use_cache: 是否使用缓存（默认 True）

        返回:
            文档列表

        示例:
            >>> client.find(
            ...     selector={"age": {"$gt": 25}},
            ...     fields=["name", "age"],
            ...     limit=10
            ... )
            [{"name": "Alice", "age": 30}, ...]
        """
        # 构建查询体
        query = {"selector": selector}

        if fields:
            query["fields"] = fields
        if limit is not None:
            query["limit"] = limit
        if skip is not None:
            query["skip"] = skip
        if sort:
            query["sort"] = sort

        # 检查缓存
        if use_cache and self.cache:
            cached_result = self.cache.get(query)
            if cached_result is not None:
                return cached_result

        # 执行查询，如果需要索引则自动创建
        try:
            response = self.client.post(
                self._build_db_url("_find"),
                json=query,
                headers={"Content-Type": "application/json"},
            )

            result = self._handle_response(response)
            docs = result.get("docs", [])

            # 更新缓存
            if use_cache and self.cache:
                self.cache.set(query, docs)

            return docs
        except Exception as e:
            # 检查是否是缺少索引的错误
            if "no_usable_index" in str(e) and sort:
                # 自动创建索引
                self._create_sort_index(sort)

                # 重试查询
                response = self.client.post(
                    self._build_db_url("_find"),
                    json=query,
                    headers={"Content-Type": "application/json"},
                )

                result = self._handle_response(response)
                docs = result.get("docs", [])

                # 更新缓存
                if use_cache and self.cache:
                    self.cache.set(query, docs)

                return docs
            else:
                raise

    def _create_sort_index(self, sort: List[Dict[str, str]]) -> None:
        """
        为排序字段创建索引

        参数:
            sort: 排序规则，如 [{"age": "asc"}, {"name": "desc"}]
        """
        # 提取需要索引的字段
        fields = []
        for sort_item in sort:
            for field_name in sort_item.keys():
                if field_name not in fields:
                    fields.append(field_name)

        # 创建索引请求
        index_request = {
            "index": {"fields": fields},
            "type": "json",
            "name": f"idx_{'_'.join(fields)}",
        }

        try:
            response = self.client.post(
                self._build_db_url("_index"),
                json=index_request,
                headers={"Content-Type": "application/json"},
            )
            self._handle_response(response)
        except Exception:
            # 如果索引已存在或创建失败，忽略错误
            pass

    def bulk_docs(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量创建/更新文档

        参数:
            docs: 文档列表

        返回:
            结果列表，每个结果包含 'id' 和 'rev'

        示例:
            >>> client.bulk_docs([
            ...     {"name": "Alice"},
            ...     {"name": "Bob"}
            ... ])
            [{'id': '...', 'rev': '...'}, ...]
        """
        response = self.client.post(
            self._build_db_url("_bulk_docs"),
            json={"docs": docs},
            headers={"Content-Type": "application/json"},
        )

        return self._handle_response(response)


class AsyncCouchDBClient(CouchDBClient):
    """
    异步 CouchDB 客户端

    使用 httpx.AsyncClient 实现异步 HTTP 请求。
    """

    def __init__(self, *args, **kwargs):
        """初始化异步客户端"""
        super().__init__(*args, **kwargs)
        self.client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> httpx.AsyncClient:
        """
        创建异步 HTTP 客户端连接

        返回:
            httpx.AsyncClient 实例
        """
        if self.client is None:
            limits = httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            )

            timeout = httpx.Timeout(
                connect=5.0,
                read=30.0,
                write=10.0,
                pool=5.0,
            )

            self.client = httpx.AsyncClient(
                auth=self.auth,
                limits=limits,
                timeout=timeout,
                follow_redirects=True,
            )

        return self.client

    async def close(self):
        """关闭异步客户端连接"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def ping(self) -> bool:
        """检查 CouchDB 服务器是否可访问（异步）"""
        try:
            response = await self.client.get(self._build_url("/"))
            return response.status_code == 200
        except Exception:
            return False

    async def create_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """创建新文档（异步）

        参数:
            doc: 文档内容（字典）

        返回:
            包含 'id' 和 'rev' 的字典

        示例:
            >>> await client.create_document({"name": "Alice", "age": 30})
            {'id': 'abc123', 'rev': '1-xyz'}

            >>> await client.create_document({"_id": "user:001", "name": "Bob"})
            {'id': 'user:001', 'rev': '1-xyz'}
        """
        # 检查是否指定了 _id
        if "_id" in doc and doc["_id"]:
            # 有指定 _id，使用 PUT 请求到指定的文档 ID
            doc_id = doc["_id"]
            encoded_id = quote(doc_id, safe="")

            # 创建文档副本，移除 _id 字段（CouchDB PUT 请求不需要文档体中的 _id）
            doc_body = {k: v for k, v in doc.items() if k != "_id"}

            response = await self.client.put(
                self._build_db_url(encoded_id),
                json=doc_body,
                headers={"Content-Type": "application/json"},
            )
        else:
            # 没有指定 _id，使用 POST 请求让 CouchDB 自动生成 ID
            response = await self.client.post(
                self._build_db_url(),
                json=doc,
                headers={"Content-Type": "application/json"},
            )

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    async def get_document(self, doc_id: str) -> Dict[str, Any]:
        """获取文档（异步）"""
        encoded_id = quote(doc_id, safe="")
        response = await self.client.get(self._build_db_url(encoded_id))
        return self._handle_response(response)

    async def update_document(self, doc_id: str, doc: Dict[str, Any], rev: str) -> Dict[str, Any]:
        """更新文档（异步）"""
        doc["_rev"] = rev

        encoded_id = quote(doc_id, safe="")
        response = await self.client.put(
            self._build_db_url(encoded_id),
            json=doc,
            headers={"Content-Type": "application/json"},
        )

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    async def delete_document(self, doc_id: str, rev: str) -> Dict[str, Any]:
        """删除文档（异步）"""
        encoded_id = quote(doc_id, safe="")
        response = await self.client.delete(self._build_db_url(f"{encoded_id}?rev={rev}"))

        result = self._handle_response(response)
        return {"id": result.get("id"), "rev": result.get("rev")}

    async def find(
        self,
        selector: Dict[str, Any],
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        sort: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """使用 Mango Query 查询文档（异步）"""
        query = {"selector": selector}

        if fields:
            query["fields"] = fields
        if limit is not None:
            query["limit"] = limit
        if skip is not None:
            query["skip"] = skip
        if sort:
            query["sort"] = sort

        response = await self.client.post(
            self._build_db_url("_find"),
            json=query,
            headers={"Content-Type": "application/json"},
        )

        result = self._handle_response(response)
        return result.get("docs", [])

    async def bulk_docs(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量创建/更新文档（异步）"""
        response = await self.client.post(
            self._build_db_url("_bulk_docs"),
            json={"docs": docs},
            headers={"Content-Type": "application/json"},
        )

        return self._handle_response(response)
