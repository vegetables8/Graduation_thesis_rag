import json
import logging

import requests
from flask import current_app

from app import db
from app.models import DocumentChunk, QueryHistory, SearchHistory
from app.services.audit_service import write_audit_log
from app.services.vector_service import vector_store

logger = logging.getLogger(__name__)


class RagService:
    """负责语义检索与问答生成。"""

    @staticmethod
    def semantic_search(keyword: str, top_k: int, current_user) -> list[dict]:
        """执行语义检索并记录历史。"""

        try:
            results = vector_store.query(keyword, top_k=top_k)
        except ValueError:
            raise  # 配置类错误直接抛出，让路由层统一处理
        except Exception as exc:
            raise RuntimeError(
                f"语义检索时向量数据库查询失败：{exc}"
            ) from exc

        history = SearchHistory(
            user_id=current_user.id,
            keyword=keyword,
            top_k=top_k,
            results_json=json.dumps(results, ensure_ascii=False),
        )
        db.session.add(history)
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="semantic_search",
            target_type="knowledge_base",
            detail=f"检索关键词：{keyword}，返回数量：{len(results)}",
        )
        return results

    @staticmethod
    def keyword_search(keyword: str, top_k: int, current_user,
                       document_id: int = None) -> list[dict]:
        """关键词检索：在 SQLite DocumentChunk 表中做 LIKE 匹配。"""

        query = DocumentChunk.query
        if document_id:
            query = query.filter_by(document_id=document_id)

        # 分词：按空格拆分关键词，每个词独立匹配
        terms = keyword.split()
        filters = []
        for term in terms:
            filters.append(DocumentChunk.content.contains(term))
        if filters:
            from sqlalchemy import or_
            query = query.filter(or_(*filters))

        chunks = query.limit(top_k).all()

        results = []
        for chunk in chunks:
            results.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "score": None,  # 关键词匹配无相似度分数
                "metadata": {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                },
            })

        history = SearchHistory(
            user_id=current_user.id,
            keyword=keyword,
            top_k=top_k,
            results_json=json.dumps(results, ensure_ascii=False),
        )
        db.session.add(history)
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="keyword_search",
            target_type="knowledge_base",
            detail=f"关键词检索：{keyword}，返回：{len(results)}",
        )
        return results

    @staticmethod
    def hybrid_search(keyword: str, top_k: int, current_user,
                      document_id: int = None) -> list[dict]:
        """混合检索：合并语义检索与关键词检索结果，去重并排序。"""

        semantic_results = RagService.semantic_search(keyword, top_k * 2, current_user)
        keyword_results = RagService.keyword_search(keyword, top_k * 2, current_user, document_id)

        # 以 chunk_id 去重，语义结果优先
        seen = set()
        merged = []
        for r in semantic_results + keyword_results:
            cid = r.get("chunk_id", "")
            if cid and cid in seen:
                continue
            seen.add(cid)
            # 混合评分：语义分数权重 0.7 + 关键词权重 0.3
            r["_score"] = (r.get("score") or 0.3) * 0.7 + (0.5 if not r.get("score") else 0) * 0.3
            merged.append(r)

        # 按评分排序取 top_k
        merged.sort(key=lambda x: x.get("_score", 0), reverse=True)
        result = merged[:top_k]
        for r in result:
            r.pop("_score", None)

        return result

    @staticmethod
    def get_search_suggestions(prefix: str, current_user, limit: int = 6) -> list[str]:
        """基于当前用户最近搜索历史的关键词前缀匹配。"""

        histories = (
            SearchHistory.query
            .filter_by(user_id=current_user.id)
            .filter(SearchHistory.keyword.like(f"{prefix}%"))
            .order_by(SearchHistory.created_at.desc())
            .limit(limit)
            .all()
        )
        seen = set()
        suggestions = []
        for h in histories:
            kw = h.keyword.strip()
            if kw and kw not in seen:
                seen.add(kw)
                suggestions.append(kw)
        return suggestions

    @staticmethod
    def answer_question(question: str, top_k: int, current_user) -> dict:
        """执行 RAG 问答流程：检索 + 大模型生成。"""

        # 步骤 1：语义检索
        try:
            results = vector_store.query(question, top_k=top_k)
        except ValueError:
            raise  # 配置类错误直接抛出
        except Exception as exc:
            raise RuntimeError(
                f"RAG 问答检索阶段失败：{exc}"
            ) from exc

        # 步骤 2：构造上下文（带编号标记）
        context_blocks = []
        references = []
        citations = []

        for idx, item in enumerate(results, start=1):
            metadata = item.get("metadata", {})
            name = metadata.get("document_name", "未知文档")
            chunk_idx = metadata.get("chunk_index", 0)
            content = item.get("content", "")

            references.append(f"{name}#片段{chunk_idx}")
            context_blocks.append(
                f"【引用来源 [{idx}]：文档《{name}》片段 #{chunk_idx}】\n{content}"
            )
            citations.append({
                "id": idx,
                "document_name": name,
                "chunk_index": chunk_idx,
                "snippet": content[:200] + ("..." if len(content) > 200 else ""),
            })

        context = "\n\n".join(context_blocks)

        # 步骤 3：调用大模型生成答案
        try:
            answer = RagService._generate_answer(question, context)
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"RAG 问答生成阶段失败：{exc}"
            ) from exc

        # 步骤 4：记录历史
        history = QueryHistory(
            user_id=current_user.id,
            question=question,
            answer=answer,
            retrieved_context=context,
            reference_documents="；".join(references),
        )
        db.session.add(history)
        db.session.commit()

        write_audit_log(
            user=current_user,
            action="rag_question_answer",
            target_type="knowledge_base",
            detail=f"问题：{question}，引用片段数：{len(results)}",
        )

        return {
            "answer": answer,
            "references": references,
            "citations": citations,
            "results": results,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _get_api_key() -> str:
        """获取并校验 LLM API Key。"""
        api_key = (current_app.config.get("LLM_API_KEY") or "").strip()
        if not api_key:
            raise ValueError(
                "未配置 LLM_API_KEY，无法调用大模型 API。\n"
                "请在项目根目录的 .env 文件中设置：\n"
                "  LLM_API_KEY=你的API密钥\n"
                "或直接在 config.py 的 BaseConfig.LLM_API_KEY 中设置默认值。"
            )
        return api_key

    @staticmethod
    def _generate_answer(question: str, context: str) -> str:
        """
        使用真实第三方 HTTP 大模型接口生成答案。

        本项目按要求只允许第三方 HTTP API，不允许：
        1. mock
        2. Ollama
        3. Docker 容器中的本地模型
        """

        if not context.strip():
            return "选题指南库中暂未检索到足够相关的内容，请先上传课题资料并建立索引。"

        api_key = RagService._get_api_key()
           #上下文提示词工程
        prompt = (
            "你是高校毕设选题指导系统的智能助手。\n"
            "请严格依据给定的选题指南上下文作答，不允许编造不存在的信息。\n"
            "如果上下文证据不足，请直接说明「选题指南资料不足」。\n\n"
            "重要：请在回答中使用 [1] [2] 等编号标注你所依据的引用来源，"
            "编号与上下文中的「引用来源 [N]」一一对应。\n\n"
            f"选题指南上下文：\n{context[:12000]}\n\n"
            f"用户问题：{question}\n\n"
            "请使用中文输出，先给出结论，再分点说明依据，并在每个依据后标注引用编号。"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": current_app.config["LLM_MODEL"],
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个严谨、可审计的高校毕设选题指导助手，只依据检索证据回答问题，帮助学生了解选题方向、评分标准和往届优秀案例。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "temperature": 0.2,
            "top_p": 0.7,
        }

        try:
            response = requests.post(
                f"{current_app.config['LLM_BASE_URL'].rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=current_app.config.get("LLM_TIMEOUT", 60),
            )
            response.raise_for_status()
        except requests.Timeout:
            raise RuntimeError(
                f"大模型 API 请求超时（{current_app.config.get('LLM_TIMEOUT', 60)} 秒），请稍后重试。"
            )
        except requests.ConnectionError:
            raise RuntimeError(
                "无法连接到大模型 API 服务器，请检查网络连接和 LLM_BASE_URL 配置。"
            )
        except requests.HTTPError as exc:
            detail = ""
            try:
                err = exc.response.json()
                if "error" in err:
                    detail = f" - {err['error'].get('message', '')}"
            except Exception:
                pass
            raise RuntimeError(
                f"大模型 API 返回错误（HTTP {exc.response.status_code}）{detail}"
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"大模型 API 请求异常：{exc}") from exc

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            logger.warning("大模型 API 返回为空：%s", json.dumps(data, ensure_ascii=False)[:500])
            raise RuntimeError("大模型未返回有效回答，请稍后重试。")

        message = choices[0].get("message", {})
        content = (message.get("content") or "").strip()
        if not content:
            raise RuntimeError("大模型返回内容为空，请尝试重新提问。")
        return content


rag_service = RagService()
