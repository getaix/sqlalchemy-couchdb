"""
查询结果缓存模块

提供查询结果的内存缓存，减少重复查询的数据库访问。
支持 LRU 缓存策略和 TTL（生存时间）。
"""

import time
import hashlib
import json
from typing import Any, Dict, List, Optional
from collections import OrderedDict
from threading import Lock


class QueryCache:
    """
    查询结果缓存

    使用 LRU（最近最少使用）策略和 TTL（生存时间）来管理缓存。
    """

    def __init__(self, max_size: int = 100, ttl: float = 300.0):
        """
        初始化查询缓存

        参数:
            max_size: 最大缓存条目数（默认100）
            ttl: 缓存条目的生存时间（秒，默认300）
        """
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, query: Dict[str, Any]) -> str:
        """
        根据查询生成缓存键

        参数:
            query: 查询字典

        返回:
            缓存键（字符串）
        """
        # 将查询序列化为 JSON，然后计算 hash
        query_json = json.dumps(query, sort_keys=True)
        return hashlib.md5(query_json.encode()).hexdigest()

    def get(self, query: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        从缓存中获取查询结果

        参数:
            query: 查询字典

        返回:
            缓存的结果列表，如果不存在或已过期则返回 None
        """
        key = self._make_key(query)

        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # 检查是否过期
            if time.time() - entry["timestamp"] > self.ttl:
                # 过期，删除
                del self._cache[key]
                self._misses += 1
                return None

            # 移动到末尾（LRU）
            self._cache.move_to_end(key)
            self._hits += 1
            return entry["result"]

    def set(self, query: Dict[str, Any], result: List[Dict[str, Any]]) -> None:
        """
        将查询结果添加到缓存

        参数:
            query: 查询字典
            result: 查询结果列表
        """
        key = self._make_key(query)

        with self._lock:
            # 如果键已存在，先删除（以更新顺序）
            if key in self._cache:
                del self._cache[key]

            # 如果缓存已满，删除最老的条目
            elif len(self._cache) >= self.max_size:
                # OrderedDict.popitem(last=False) 删除第一个（最老的）条目
                self._cache.popitem(last=False)

            # 添加新条目
            self._cache[key] = {
                "result": result,
                "timestamp": time.time(),
            }

    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def invalidate(self, table: Optional[str] = None) -> None:
        """
        使缓存失效

        参数:
            table: 表名（可选），如果指定则只删除该表相关的缓存
        """
        with self._lock:
            if table is None:
                # 清空所有缓存
                self._cache.clear()
            else:
                # 删除特定表的缓存
                # 这需要检查每个缓存条目的查询内容
                keys_to_delete = []
                for key, entry in self._cache.items():
                    # 这里简化处理，实际应该解析查询
                    # 为了性能，暂时清空所有缓存
                    keys_to_delete.append(key)

                for key in keys_to_delete:
                    del self._cache[key]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        返回:
            包含缓存统计的字典
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.2f}%",
                "ttl": self.ttl,
            }


# 全局缓存实例（可选使用）
_global_cache: Optional[QueryCache] = None


def get_global_cache(max_size: int = 100, ttl: float = 300.0) -> QueryCache:
    """
    获取或创建全局缓存实例

    参数:
        max_size: 最大缓存条目数
        ttl: 缓存生存时间

    返回:
        QueryCache 实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = QueryCache(max_size=max_size, ttl=ttl)
    return _global_cache


def clear_global_cache() -> None:
    """清空全局缓存"""
    global _global_cache
    if _global_cache:
        _global_cache.clear()
