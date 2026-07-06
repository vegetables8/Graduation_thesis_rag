import logging

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, session, url_for

from app.decorators import login_required, role_required
from app.models import AuditLog, Document, DocumentChunk, QueryHistory, SearchHistory, User
from app.services.document_service import document_service
from app.services.rag_service import rag_service

logger = logging.getLogger(__name__)


main_bp = Blueprint("main", __name__)


def _safe_top_k(raw_value, default: int = 5) -> int:
    """限制前端提交的 top_k，避免传入过大值影响接口性能。"""

    try:
        top_k = int(raw_value or default)
    except (TypeError, ValueError):
        top_k = default
    return max(1, min(top_k, 10))


def _get_user_qa_histories(user: User, limit: int = 20) -> list[QueryHistory]:
    return (
        QueryHistory.query.filter_by(user_id=user.id)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def _get_user_search_histories(user: User, limit: int = 20) -> list[SearchHistory]:
    return (
        SearchHistory.query.filter_by(user_id=user.id)
        .order_by(SearchHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def _dashboard_context(user: User) -> dict:
    """组装多个页面会复用的首页统计信息。"""

    return {
        "stats": {
            "document_count": Document.query.count(),
            "qa_count": QueryHistory.query.filter_by(user_id=user.id).count(),
            "search_count": SearchHistory.query.filter_by(user_id=user.id).count(),
            "user_count": User.query.count() if user.role == "academic_admin" else None,
            "audit_count": AuditLog.query.count() if user.role == "audit_admin" else None,
        },
        "recent_documents": Document.query.order_by(Document.created_at.desc()).limit(8).all(),
        "recent_qa_histories": _get_user_qa_histories(user, limit=5),
        "recent_search_histories": _get_user_search_histories(user, limit=5),
    }


@main_bp.route("/")
def index():
    """根路径根据登录状态自动跳转。"""

    if session.get("user_id"):
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """首页概览页。"""

    current_user = g.current_user
    return render_template(
        "dashboard.html",
        current_user=current_user,
        **_dashboard_context(current_user),
    )


@main_bp.route("/search")
@login_required
def search_page():
    """语义检索页。"""

    current_user = g.current_user
    return render_template(
        "search.html",
        current_user=current_user,
        recent_searches=_get_user_search_histories(current_user, limit=10),
    )


@main_bp.route("/chat")
@login_required
def chat_page():
    """RAG 问答页。"""

    current_user = g.current_user
    return render_template(
        "chat.html",
        current_user=current_user,
        recent_qa_histories=_get_user_qa_histories(current_user, limit=10),
    )


@main_bp.route("/documents")
@login_required
def documents_page():
    """课题资料中心页。所有已登录角色都可以查看选题指南库课题资料清单。"""

    current_user = g.current_user
    return render_template(
        "documents.html",
        current_user=current_user,
        documents=Document.query.order_by(Document.created_at.desc()).all(),
    )


@main_bp.route("/upload")
@role_required("topic_admin")
def upload_page():
    """课题资料上传与索引页，仅课题管理员可访问。"""

    current_user = g.current_user
    return render_template(
        "upload.html",
        current_user=current_user,
        documents=Document.query.order_by(Document.created_at.desc()).all(),
    )


@main_bp.route("/history")
@login_required
def history_page():
    """历史记录页。"""

    current_user = g.current_user
    return render_template(
        "history.html",
        current_user=current_user,
        qa_histories=_get_user_qa_histories(current_user, limit=30),
        search_histories=_get_user_search_histories(current_user, limit=30),
    )


@main_bp.route("/users")
@role_required("academic_admin")
def users_page():
    """权限管理页面。"""

    current_user = g.current_user
    return render_template(
        "users.html",
        current_user=current_user,
        users=User.query.order_by(User.id.asc()).all(),
    )


@main_bp.route("/audits")
@role_required("audit_admin")
def audits_page():
    """审计中心页面。"""

    current_user = g.current_user
    return render_template(
        "audits.html",
        current_user=current_user,
        audits=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all(),
    )


@main_bp.route("/profile")
@login_required
def profile_page():
    """个人中心页。"""

    current_user = g.current_user
    permission_descriptions = {
        "student": [
            "可执行语义检索",
            "可发起真实大模型问答",
            "可查看自己的检索与问答历史",
        ],
        "topic_admin": [
            "拥有学生全部能力",
            "可上传课题资料并触发解析、分块与向量化",
            "可维护选题指南库课题资料资源",
        ],
        "academic_admin": [
            "拥有学生全部能力",
            "可管理 4 类固定角色的账号权限",
            "可进入权限管理页面调整角色",
        ],
        "audit_admin": [
            "拥有学生全部能力",
            "可查看系统审计日志",
            "可检查登录、拒绝访问、上传、问答等关键操作记录",
        ],
    }
    return render_template(
        "profile.html",
        current_user=current_user,
        permission_descriptions=permission_descriptions.get(current_user.role, []),
    )


@main_bp.route("/api/documents", methods=["GET"])
@login_required
def document_list():
    """返回选题指南库课题资料列表。"""

    documents = [
        doc.to_dict()
        for doc in Document.query.order_by(Document.created_at.desc()).all()
    ]
    return jsonify({"ok": True, "items": documents})


@main_bp.route("/api/documents/upload", methods=["POST"])
@role_required("topic_admin")
def upload_document():
    """上传文档并同步完成解析、分块与索引。"""

    current_user = g.current_user
    if "file" not in request.files:
        return jsonify({"ok": False, "message": "未检测到上传文件。"}), 400

    file_storage = request.files["file"]
    if not file_storage.filename:
        return jsonify({"ok": False, "message": "文件名不能为空。"}), 400

    if not document_service.allowed_file(file_storage.filename):
        return jsonify({"ok": False, "message": "仅支持 txt、md、pdf、docx 文件。"}), 400

    try:
        document = document_service.save_upload(file_storage, current_user)
        result = document_service.parse_and_index(document, current_user)
        return jsonify({"ok": True, "message": "文档上传并建立向量索引成功。", "data": result})
    except ValueError as exc:
        # 配置缺失或数据校验失败（如 API Key 未配置、文档为空）
        logger.warning("文档上传失败（配置/数据问题）：%s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.error("文档上传异常：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"处理失败：{exc}"}), 500


# ---------------------------------------------------------------------------
# 文档 CRUD API
# ---------------------------------------------------------------------------


@main_bp.route("/api/documents/<int:doc_id>", methods=["GET"])
@login_required
def document_detail(doc_id: int):
    """获取文档详情（含分块列表）。"""

    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"ok": False, "message": "文档不存在。"}), 404
    return jsonify({"ok": True, "data": document_service.get_document_detail(doc)})


@main_bp.route("/api/documents/<int:doc_id>", methods=["DELETE"])
@role_required("topic_admin")
def delete_document(doc_id: int):
    """删除文档（级联清理向量和文件）。"""

    current_user = g.current_user
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"ok": False, "message": "文档不存在。"}), 404

    try:
        result = document_service.delete_document(doc, current_user)
        return jsonify({"ok": True, "message": "文档已删除。", "data": result})
    except Exception as exc:
        logger.error("删除文档失败：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"删除失败：{exc}"}), 500


@main_bp.route("/api/documents/<int:doc_id>/reindex", methods=["POST"])
@role_required("topic_admin")
def reindex_document(doc_id: int):
    """重新解析并索引文档。"""

    current_user = g.current_user
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"ok": False, "message": "文档不存在。"}), 404

    try:
        result = document_service.reindex_document(doc, current_user)
        return jsonify({"ok": True, "message": "重建索引成功。", "data": result})
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.error("重建索引失败：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"重建索引失败：{exc}"}), 500


@main_bp.route("/api/documents/batch-delete", methods=["POST"])
@role_required("topic_admin")
def batch_delete_documents():
    """批量删除文档。"""

    current_user = g.current_user
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])

    if not ids or not isinstance(ids, list):
        return jsonify({"ok": False, "message": "请提供要删除的文档 ID 列表。"}), 400

    try:
        result = document_service.batch_delete_documents(ids, current_user)
        return jsonify({"ok": True, "message": f"已删除 {result['deleted_count']} 个文档。", "data": result})
    except ValueError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.error("批量删除失败：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"批量删除失败：{exc}"}), 500


# ---------------------------------------------------------------------------
# 检索 / 问答 API
# ---------------------------------------------------------------------------


@main_bp.route("/api/search", methods=["POST"])
@login_required
def semantic_search():
    """执行检索（支持 semantic / keyword / hybrid 三种模式）。"""

    current_user = g.current_user
    payload = request.get_json(silent=True) or {}
    keyword = (payload.get("keyword") or "").strip()
    top_k = _safe_top_k(payload.get("top_k"), default=5)
    mode = payload.get("mode", "semantic")
    document_id = payload.get("document_id")
    page = max(1, int(payload.get("page", 1)))
    per_page = min(max(1, int(payload.get("per_page", top_k))), 50)

    if not keyword:
        return jsonify({"ok": False, "message": "检索关键词不能为空。"}), 400

    if mode not in ("semantic", "keyword", "hybrid"):
        return jsonify({"ok": False, "message": "mode 仅支持 semantic / keyword / hybrid。"}), 400

    try:
        if mode == "keyword":
            results = rag_service.keyword_search(keyword, per_page * 2, current_user, document_id)
        elif mode == "hybrid":
            results = rag_service.hybrid_search(keyword, per_page * 2, current_user, document_id)
        else:
            results = rag_service.semantic_search(keyword, per_page * 2, current_user)

        # Python 侧分页
        total = len(results)
        start = (page - 1) * per_page
        paged = results[start:start + per_page]

        return jsonify({
            "ok": True,
            "items": paged,
            "total": total,
            "page": page,
            "per_page": per_page,
            "mode": mode,
        })
    except ValueError as exc:
        logger.warning("检索失败（配置问题）：%s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 500
    except Exception as exc:
        logger.error("检索异常：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"检索失败：{exc}"}), 500


@main_bp.route("/api/search/suggestions", methods=["GET"])
@login_required
def search_suggestions():
    """搜索建议：基于用户历史检索记录做前缀匹配。"""

    current_user = g.current_user
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "suggestions": []})
    suggestions = rag_service.get_search_suggestions(q, current_user)
    return jsonify({"ok": True, "suggestions": suggestions})


@main_bp.route("/api/qa", methods=["POST"])
@login_required
def qa():
    """执行 RAG 问答。"""

    current_user = g.current_user
    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    top_k = _safe_top_k(payload.get("top_k"), default=5)
    if not question:
        return jsonify({"ok": False, "message": "问题不能为空。"}), 400

    try:
        result = rag_service.answer_question(question, top_k, current_user)
        return jsonify({"ok": True, "data": result})
    except ValueError as exc:
        # 配置类错误（如 API Key 未配置），给出明确指引
        logger.warning("RAG 问答失败（配置问题）：%s", exc)
        return jsonify({"ok": False, "message": str(exc)}), 500
    except Exception as exc:
        logger.error("RAG 问答异常：%s", exc, exc_info=True)
        return jsonify({"ok": False, "message": f"问答失败：{exc}"}), 500


@main_bp.route("/api/history", methods=["GET"])
@login_required
def history():
    """返回当前登录用户自己的检索与问答历史。"""

    current_user = g.current_user
    histories = [item.to_dict() for item in _get_user_qa_histories(current_user, limit=50)]
    searches = [item.to_dict() for item in _get_user_search_histories(current_user, limit=50)]
    return jsonify({"ok": True, "qa_histories": histories, "search_histories": searches})


@main_bp.route("/api/history/export", methods=["GET"])
@login_required
def export_history():
    """导出当前用户的问答历史为 CSV。"""

    import csv
    import io

    current_user = g.current_user
    qa_items = _get_user_qa_histories(current_user, limit=500)
    search_items = _get_user_search_histories(current_user, limit=500)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["类型", "时间", "问题/关键词", "答案/结果数"])
    for item in qa_items:
        writer.writerow(["问答", item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                         item.question, item.answer[:200]])
    for item in search_items:
        writer.writerow(["检索", item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                         item.keyword, f"top_k={item.top_k}"])

    from flask import Response
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=history_export.csv"},
    )


@main_bp.route("/api/health", methods=["GET"])
@login_required
def health_check():
    """系统健康检查。"""

    import chromadb
    from app.models import Document, DocumentChunk, User

    health = {
        "status": "ok",
        "document_count": Document.query.count(),
        "chunk_count": DocumentChunk.query.count(),
        "user_count": User.query.count(),
        "api_key_configured": bool((current_app.config.get("LLM_API_KEY") or "").strip()),
        "embedding_model": current_app.config.get("EMBEDDING_MODEL", ""),
        "llm_model": current_app.config.get("LLM_MODEL", ""),
    }

    # ChromaDB 连通性
    try:
        from app.services.vector_service import vector_store
        col = vector_store.collection
        health["chromadb_collection"] = col.name
        health["chromadb_count"] = col.count()
    except Exception as exc:
        health["chromadb_error"] = str(exc)

    return jsonify({"ok": True, "health": health})
