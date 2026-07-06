"""
智谱 AI Embedding API 封装。

说明：
- 使用智谱 AI 的 text-embedding-3 模型进行向量化
- 替代本地 sentence-transformers（依赖 torch，在某些环境下有 DLL 问题）
- 接口文档：https://open.bigmodel.cn/dev/api/vector/embedding
"""

import json
import logging
import time

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class ZhipuEmbeddingFunction:
    """
    自定义 ChromaDB EmbeddingFunction，使用智谱 AI API 进行向量化。

    兼容 ChromaDB 的 EmbeddingFunction 接口，
    可以直接传给 ChromaDB 集合使用。
    """

    # 智谱 AI 限制每次最多 256 段文本
    _BATCH_SIZE = 256
    # 最大重试次数（仅针对可重试的错误）
    _MAX_RETRIES = 2
    # 重试间隔（秒）
    _RETRY_DELAY = 1.0

    def __init__(self, model: str = "text-embedding-3"):
        """
        初始化向量化服务。

        参数：
            model: 智谱 AI Embedding 模型名称
                   可选：text-embedding-3（推荐，1024维度）、text-embedding-2
        """
        self.model = model

    def name(self):
        """返回 Embedding 模型名称，供 ChromaDB 使用。"""
        return self.model

    def __call__(self, input: list[str]) -> list[list[float]]:
        """
        将文本列表转换为向量列表。

        ChromaDB 1.5.x 的核心接口方法。``embed_query`` 的默认实现也会委托到这里。
        因此只需正确实现 __call__ 即可同时支持查询和文档索引。

        注意：ChromaDB 在某些调用路径下可能会将单条文本包装成嵌套列表，
        因此这里对输入做归一化处理，确保传给 API 的一定是扁平的字符串列表。

        参数：
            input: 文本列表（可能包含嵌套列表）

        返回：
            向量列表，每个向量是浮点数列表
        """
        normalized = self._normalize_input(input)
        return self._get_embeddings(normalized)

    def embed_query(self, input):
        """
        ChromaDB 1.5.x 会通过此方法对查询文本做向量化。

        保持与 ChromaDB EmbeddingFunction 协议的默认行为一致：
        直接委托给 __call__，不做额外处理。
        """
        return self.__call__(input)

    @staticmethod
    def _normalize_input(input_data: list) -> list[str]:
        """
        将 ChromaDB 可能传入的嵌套列表归一化为扁平的字符串列表。

        ChromaDB 1.5.x 在某些代码路径下会将单条文本包装成嵌套列表
        （例如 [['text']] 而不是 ['text']），这里统一处理。
        """
        if not input_data:
            return []

        result = []
        for item in input_data:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, list):
                # 递归展平嵌套列表中的字符串
                result.extend(ZhipuEmbeddingFunction._normalize_input(item))
            else:
                # 兜底：转为字符串
                result.append(str(item))
        return result

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _get_api_key(self) -> str:
        """获取并校验 API Key。"""
        api_key = (current_app.config.get("LLM_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(
                "未配置 LLM_API_KEY，无法调用智谱 AI Embedding API。\n"
                "请在项目根目录的 .env 文件中设置：\n"
                "  LLM_API_KEY=你的API密钥\n"
                "或直接在 config.py 的 BaseConfig.LLM_API_KEY 中设置默认值。"
            )
        return api_key

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        调用智谱 AI Embedding API 获取向量。

        智谱 AI 的 Embedding API 一次最多支持 256 段文本，
        如果超过这个数量，会自动分批处理。

        注意：为保证输入格式正确，入口处统一做一次归一化。
        """
        # 归一化输入，兼容 ChromaDB 可能传入的嵌套列表格式
        texts = self._normalize_input(texts)
        if not texts:
            return []

        api_key = self._get_api_key()
        base_url = current_app.config.get(
            "EMBEDDING_BASE_URL",
            "https://open.bigmodel.cn/api/embedding/v1",
        )
        model = current_app.config.get("EMBEDDING_MODEL", "text-embedding-3")

        all_embeddings = []
        total_batches = (len(texts) + self._BATCH_SIZE - 1) // self._BATCH_SIZE

        for batch_idx in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[batch_idx:batch_idx + self._BATCH_SIZE]
            current_batch_no = batch_idx // self._BATCH_SIZE + 1
            logger.debug(
                "Embedding 批次 %d/%d：%d 段文本",
                current_batch_no,
                total_batches,
                len(batch),
            )

            embeddings = self._call_api_with_retry(
                batch, model, base_url, api_key
            )
            all_embeddings.extend(embeddings)

        return all_embeddings

    def _call_api_with_retry(
        self,
        texts: list[str],
        model: str,
        base_url: str,
        api_key: str,
    ) -> list[list[float]]:
        """带重试的 API 调用。"""

        last_error = None
        for attempt in range(1 + self._MAX_RETRIES):
            try:
                return self._call_api(texts, model, base_url, api_key)
            except requests.Timeout:
                last_error = f"Embedding API 请求超时（第 {attempt + 1} 次尝试）"
                logger.warning(last_error)
            except requests.ConnectionError:
                last_error = f"Embedding API 连接失败（第 {attempt + 1} 次尝试）"
                logger.warning(last_error)
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "?"
                # 429 (rate limit) 和 5xx 可重试，4xx 不重试
                if status in (429, 500, 502, 503, 504):
                    last_error = f"Embedding API HTTP {status}（第 {attempt + 1} 次尝试）"
                    logger.warning(last_error)
                else:
                    raise RuntimeError(self._format_api_error(exc)) from exc
            except RuntimeError:
                raise  # 不重试我们自己抛出的 RuntimeError

            if attempt < self._MAX_RETRIES:
                time.sleep(self._RETRY_DELAY * (attempt + 1))

        raise RuntimeError(f"{last_error}，已重试 {self._MAX_RETRIES} 次仍失败")

    def _call_api(
        self,
        texts: list[str],
        model: str,
        base_url: str,
        api_key: str,
    ) -> list[list[float]]:
        """
        调用智谱 AI Embedding API。

        智谱 AI Embedding API 请求格式：
        POST /embeddings
        {
            "model": "text-embedding-3",
            "input": ["文本1", "文本2", ...]
        }
        """
        url = f"{base_url.rstrip('/')}/embeddings"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        payload = {
            "model": model,
            "input": texts,
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=current_app.config.get("LLM_TIMEOUT", 60),
        )
        response.raise_for_status()

        data = response.json()

        # 按索引排序，确保返回顺序与输入一致
        embeddings = data.get("data", [])
        embeddings.sort(key=lambda x: x.get("index", 0))

        if not embeddings:
            raise RuntimeError("Embedding API 返回了空的数据列表")

        return [item["embedding"] for item in embeddings]

    @staticmethod
    def _format_api_error(exc: requests.HTTPError) -> str:
        """格式化 API 错误信息，包含服务端返回的详细错误。"""
        base_msg = f"Embedding API 调用失败：HTTP {exc.response.status_code}"
        try:
            error_detail = exc.response.json()
            # 智谱 API 的错误格式：{"error": {"code": "...", "message": "..."}}
            if "error" in error_detail:
                err = error_detail["error"]
                code = err.get("code", "")
                msg = err.get("message", "")
                return f"{base_msg} - [{code}] {msg}"
            return f"{base_msg} - {json.dumps(error_detail, ensure_ascii=False)}"
        except Exception:
            return f"{base_msg} - {exc.response.text[:500]}"
