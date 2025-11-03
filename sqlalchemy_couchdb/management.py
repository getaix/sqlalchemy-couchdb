"""
索引和视图管理模块

提供 CouchDB 索引和视图的创建、查询、删除等管理功能。
"""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy_couchdb.exceptions import OperationalError, ProgrammingError


class IndexManager:
    """
    CouchDB 索引管理器

    提供索引的创建、删除、查询等功能。
    """

    def __init__(self, client):
        """
        初始化索引管理器

        参数:
            client: SyncCouchDBClient 或 AsyncCouchDBClient 实例
        """
        self.client = client

    def create_index(
        self,
        fields: List[str],
        name: Optional[str] = None,
        ddoc: Optional[str] = None,
        index_type: str = "json",
    ) -> Dict[str, Any]:
        """
        创建索引

        参数:
            fields: 索引字段列表，如 ["age", "name"]
            name: 索引名称（可选，默认自动生成）
            ddoc: 设计文档名称（可选）
            index_type: 索引类型（默认 "json"）

        返回:
            创建结果字典

        示例:
            >>> manager.create_index(["age", "name"], name="idx_age_name")
            {'result': 'created', 'id': '_design/...', 'name': 'idx_age_name'}
        """
        # 构建索引请求
        index_request = {
            "index": {"fields": fields},
            "type": index_type,
        }

        if name:
            index_request["name"] = name
        else:
            # 自动生成索引名称
            index_request["name"] = f"idx_{'_'.join(fields)}"

        if ddoc:
            index_request["ddoc"] = ddoc

        try:
            response = self.client.client.post(
                self.client._build_db_url("_index"),
                json=index_request,
                headers={"Content-Type": "application/json"},
            )

            return self.client._handle_response(response)
        except Exception as e:
            raise ProgrammingError(f"创建索引失败: {str(e)}") from e

    def list_indexes(self) -> List[Dict[str, Any]]:
        """
        列出所有索引

        返回:
            索引列表

        示例:
            >>> manager.list_indexes()
            [
                {
                    "ddoc": "_design/...",
                    "name": "idx_age_name",
                    "type": "json",
                    "def": {"fields": [{"age": "asc"}, {"name": "asc"}]}
                },
                ...
            ]
        """
        try:
            response = self.client.client.get(self.client._build_db_url("_index"))
            result = self.client._handle_response(response)
            return result.get("indexes", [])
        except Exception as e:
            raise OperationalError(f"获取索引列表失败: {str(e)}") from e

    def delete_index(self, ddoc: str, name: str) -> Dict[str, Any]:
        """
        删除索引

        参数:
            ddoc: 设计文档 ID（如 "_design/a5f4711fc9448864a13c81dc71e660b524d7410c"）
            name: 索引名称

        返回:
            删除结果字典

        示例:
            >>> manager.delete_index("_design/xyz", "idx_age_name")
            {'ok': True}
        """
        try:
            # CouchDB 删除索引的 API:
            # DELETE /{db}/_index/{designdoc}/json/{name}
            # ddoc 格式: "_design/..." 需要去掉 "_design/" 前缀

            ddoc_name = ddoc.replace("_design/", "")
            path = f"_index/{ddoc_name}/json/{name}"

            response = self.client.client.delete(self.client._build_db_url(path))
            return self.client._handle_response(response)
        except Exception as e:
            raise OperationalError(f"删除索引失败: {str(e)}") from e

    def find_index_by_fields(self, fields: List[str]) -> Optional[Dict[str, Any]]:
        """
        根据字段查找索引

        参数:
            fields: 字段列表

        返回:
            匹配的索引信息，如果不存在则返回 None
        """
        indexes = self.list_indexes()

        for index in indexes:
            # 检查索引字段是否匹配
            index_fields = index.get("def", {}).get("fields", [])

            # 提取字段名
            index_field_names = []
            for field_def in index_fields:
                if isinstance(field_def, dict):
                    index_field_names.extend(field_def.keys())
                elif isinstance(field_def, str):
                    index_field_names.append(field_def)

            if set(index_field_names) == set(fields):
                return index

        return None


class ViewManager:
    """
    CouchDB 视图管理器

    提供视图的创建、查询、删除等功能。
    """

    def __init__(self, client):
        """
        初始化视图管理器

        参数:
            client: SyncCouchDBClient 或 AsyncCouchDBClient 实例
        """
        self.client = client

    def create_view(
        self,
        design_doc: str,
        view_name: str,
        map_function: str,
        reduce_function: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建视图

        参数:
            design_doc: 设计文档名称（不含 "_design/" 前缀）
            view_name: 视图名称
            map_function: Map 函数（JavaScript 代码字符串）
            reduce_function: Reduce 函数（可选，JavaScript 代码字符串）

        返回:
            创建结果字典

        示例:
            >>> manager.create_view(
            ...     "analytics",
            ...     "by_age",
            ...     "function(doc) { if (doc.age) emit(doc.age, 1); }",
            ...     "_count"
            ... )
        """
        # 构建设计文档
        design_doc_id = f"_design/{design_doc}"

        # 尝试获取现有设计文档
        try:
            existing_doc = self.client.get_document(design_doc_id)
        except:
            # 设计文档不存在，创建新的
            existing_doc = {"_id": design_doc_id, "views": {}}

        # 添加或更新视图
        if "views" not in existing_doc:
            existing_doc["views"] = {}

        view_def = {"map": map_function}
        if reduce_function:
            view_def["reduce"] = reduce_function

        existing_doc["views"][view_name] = view_def

        # 保存设计文档
        try:
            if "_rev" in existing_doc:
                # 更新现有文档
                return self.client.update_document(
                    design_doc_id, existing_doc, existing_doc["_rev"]
                )
            else:
                # 创建新文档
                response = self.client.client.put(
                    self.client._build_db_url(design_doc_id),
                    json=existing_doc,
                    headers={"Content-Type": "application/json"},
                )
                return self.client._handle_response(response)
        except Exception as e:
            raise ProgrammingError(f"创建视图失败: {str(e)}") from e

    def query_view(
        self,
        design_doc: str,
        view_name: str,
        key: Optional[Any] = None,
        start_key: Optional[Any] = None,
        end_key: Optional[Any] = None,
        limit: Optional[int] = None,
        descending: bool = False,
        include_docs: bool = False,
        group: bool = False,
        reduce: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        查询视图

        参数:
            design_doc: 设计文档名称
            view_name: 视图名称
            key: 精确键匹配（可选）
            start_key: 起始键（可选）
            end_key: 结束键（可选）
            limit: 限制结果数量（可选）
            descending: 是否降序（默认 False）
            include_docs: 是否包含完整文档（默认 False）
            group: 是否按键分组（用于 reduce，默认 False）
            reduce: 是否执行 reduce（可选，默认自动检测）

        返回:
            查询结果字典

        示例:
            >>> manager.query_view("analytics", "by_age", start_key=25, end_key=35)
        """
        # 构建查询参数
        params = {}

        if key is not None:
            params["key"] = json.dumps(key)
        if start_key is not None:
            params["startkey"] = json.dumps(start_key)
        if end_key is not None:
            params["endkey"] = json.dumps(end_key)
        if limit is not None:
            params["limit"] = limit
        if descending:
            params["descending"] = "true"
        if include_docs:
            params["include_docs"] = "true"
        if group:
            params["group"] = "true"
        if reduce is not None:
            params["reduce"] = "true" if reduce else "false"

        # 构建 URL
        design_doc_id = f"_design/{design_doc}"
        path = f"{design_doc_id}/_view/{view_name}"

        try:
            response = self.client.client.get(self.client._build_db_url(path), params=params)
            return self.client._handle_response(response)
        except Exception as e:
            raise OperationalError(f"查询视图失败: {str(e)}") from e

    def delete_view(self, design_doc: str, view_name: str) -> Dict[str, Any]:
        """
        删除视图

        参数:
            design_doc: 设计文档名称
            view_name: 视图名称

        返回:
            删除结果字典
        """
        design_doc_id = f"_design/{design_doc}"

        try:
            # 获取设计文档
            doc = self.client.get_document(design_doc_id)

            # 删除视图
            if "views" in doc and view_name in doc["views"]:
                del doc["views"][view_name]

                # 如果没有其他视图了，删除整个设计文档
                if not doc["views"]:
                    return self.client.delete_document(design_doc_id, doc["_rev"])
                else:
                    # 更新设计文档
                    return self.client.update_document(design_doc_id, doc, doc["_rev"])
            else:
                raise OperationalError(f"视图 '{view_name}' 不存在")

        except Exception as e:
            raise OperationalError(f"删除视图失败: {str(e)}") from e
