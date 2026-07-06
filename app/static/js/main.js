// =========================================================================
// Atlas — 前端主脚本
// =========================================================================

document.addEventListener("DOMContentLoaded", () => {
    initUploadForm();
    initSearchForm();
    initQaForm();
    initHistoryRefresh();
    initRoleManagement();
    initAuditRefresh();
    initDocumentSelectAll();
    initDocumentBatchDelete();
    initDeleteModal();
});

// =========================================================================
// 工具函数
// =========================================================================

function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const icons = { success: "✅", danger: "❌", warning: "⚠️", info: "ℹ️" };
    const bgClass = `bg-${type === "danger" ? "danger" : type === "warning" ? "warning" : type === "success" ? "success" : "info"}`;
    const textClass = type === "warning" ? "text-dark" : "text-white";

    const toastEl = document.createElement("div");
    toastEl.className = `toast align-items-center ${textClass} ${bgClass} border-0`;
    toastEl.setAttribute("role", "alert");
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${icons[type] || ""} ${escapeHtml(message)}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>`;
    container.appendChild(toastEl);

    const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
    toast.show();
    toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

function showMessage(targetId, message, type = "info") {
    const target = document.getElementById(targetId);
    if (!target) return;
    target.innerHTML = `<div class="alert alert-${type} py-2 mb-0">${escapeHtml(message)}</div>`;
}

function showLoading(target, text = "加载中...") {
    target.innerHTML = `<div class="text-center py-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div><span class="ms-2 text-secondary">${escapeHtml(text)}</span></div>`;
}

async function requestJSON(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            ...(options.headers || {})
        },
        ...options
    });

    const rawText = await response.text();
    let data = {};

    try {
        data = rawText ? JSON.parse(rawText) : {};
    } catch (error) {
        throw new Error("接口返回了无法解析的内容，请检查后端日志。");
    }

    if (!response.ok) {
        throw new Error(data.message || "请求失败");
    }

    return data;
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function highlightKeyword(text, keyword) {
    if (!keyword || !text) return escapeHtml(text);
    const escaped = escapeHtml(text);
    const pattern = escapeHtml(keyword).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return escaped.replace(new RegExp(`(${pattern})`, "gi"), "<mark>$1</mark>");
}

function formatDate(dateStr) {
    if (!dateStr) return "";
    try {
        const d = new Date(dateStr);
        return d.toLocaleDateString("zh-CN") + " " + d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    } catch {
        return dateStr;
    }
}

// =========================================================================
// 资料上传
// =========================================================================

function initUploadForm() {
    const form = document.getElementById("upload-form");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const fileInput = document.getElementById("upload-file");
        if (!fileInput || !fileInput.files.length) {
            showToast("请先选择文件。", "warning");
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        const msgEl = document.getElementById("upload-message");
        try {
            if (msgEl) showLoading(msgEl, "正在上传并建立索引...");
            const data = await requestJSON("/api/documents/upload", {
                method: "POST",
                body: formData
            });
            if (msgEl) showMessage("upload-message", data.message || "上传成功。", "success");
            showToast("资料上传并索引成功。", "success");
            form.reset();
            await refreshDocumentTables();
        } catch (error) {
            if (msgEl) showMessage("upload-message", error.message, "danger");
            showToast(error.message, "danger");
        }
    });
}

async function refreshDocumentTables() {
    const documentsTableBody = document.querySelector("#document-table tbody");
    const uploadTableBody = document.querySelector("#upload-document-table tbody");
    if (!documentsTableBody && !uploadTableBody) return;

    const data = await requestJSON("/api/documents");
    const items = data.items || [];
    const isDocAdmin = !!document.querySelector(".doc-checkbox");

    const buildDocRows = () => {
        if (!items.length) {
            const colSpan = isDocAdmin ? 8 : 7;
            return `<tr id="empty-doc-row"><td colspan="${colSpan}" class="text-center text-secondary py-4">
                <div class="empty-state"><div class="empty-state-icon">📄</div><div class="empty-state-text">知识库中还没有资料</div></div></td></tr>`;
        }
        return items.map((item) => `
            <tr data-doc-id="${item.id}">
                ${isDocAdmin ? `<td><input type="checkbox" class="doc-checkbox" value="${item.id}"></td>` : ""}
                <td>${item.id}</td>
                <td><a href="#" onclick="showDocumentDetail(${item.id}); return false;">${escapeHtml(item.original_name)}</a></td>
                <td><span class="badge text-bg-light">${escapeHtml(item.status)}</span></td>
                <td>${item.chunk_count ?? 0}</td>
                <td>${escapeHtml(item.uploaded_by || "")}</td>
                <td>${escapeHtml(item.created_at || "")}</td>
                <td>
                    <div class="d-flex gap-1">
                        <button class="btn btn-outline-secondary btn-sm" onclick="showDocumentDetail(${item.id})">详情</button>
                        ${isDocAdmin ? `
                        <button class="btn btn-outline-warning btn-sm" onclick="reindexDocument(${item.id})">重索引</button>
                        <button class="btn btn-outline-danger btn-sm" onclick="deleteDocument(${item.id}, '${escapeHtml(item.original_name)}')">删除</button>
                        ` : ""}
                    </div>
                </td>
            </tr>
        `).join("");
    };

    if (documentsTableBody) {
        documentsTableBody.innerHTML = buildDocRows();
        if (isDocAdmin) {
            document.getElementById("batch-delete-btn")?.classList.add("d-none");
            document.getElementById("select-all-docs").checked = false;
        }
    }

    if (uploadTableBody) {
        uploadTableBody.innerHTML = items.length
            ? items.map((item) => `
                <tr>
                    <td>${item.id}</td>
                    <td>${escapeHtml(item.original_name)}</td>
                    <td><span class="badge text-bg-light">${escapeHtml(item.status)}</span></td>
                    <td>${item.chunk_count ?? 0}</td>
                    <td>${escapeHtml(item.created_at || "")}</td>
                </tr>`).join("")
            : '<tr><td colspan="5" class="text-center text-secondary">暂无资料</td></tr>';
    }
}

// =========================================================================
// 资料 CRUD 操作
// =========================================================================

let pendingDeleteDocId = null;

function initDeleteModal() {
    // 通过 Bootstrap modal 事件清理状态
    const modal = document.getElementById("delete-confirm-modal");
    if (modal) {
        modal.addEventListener("hidden.bs.modal", () => {
            pendingDeleteDocId = null;
        });
    }
}

function deleteDocument(docId, docName) {
    pendingDeleteDocId = docId;
    document.getElementById("delete-doc-name").textContent = docName;
    const modal = new bootstrap.Modal(document.getElementById("delete-confirm-modal"));
    modal.show();
}

async function confirmDeleteDocument() {
    if (!pendingDeleteDocId) return;

    const btn = document.getElementById("confirm-delete-btn");
    btn.disabled = true;
    btn.textContent = "删除中...";

    try {
        const data = await requestJSON(`/api/documents/${pendingDeleteDocId}`, { method: "DELETE" });
        showToast(data.message || "资料已删除。", "success");
        bootstrap.Modal.getInstance(document.getElementById("delete-confirm-modal")).hide();
        await refreshDocumentTables();
    } catch (error) {
        showToast(error.message, "danger");
    } finally {
        btn.disabled = false;
        btn.textContent = "确认删除";
    }
}

async function reindexDocument(docId) {
    if (!confirm("确定要重建该资料的索引吗？此操作会清除旧向量并重新解析。")) return;

    try {
        showToast("正在重建索引...", "info");
        const data = await requestJSON(`/api/documents/${docId}/reindex`, { method: "POST" });
        showToast(data.message || "重建索引成功。", "success");
        await refreshDocumentTables();
    } catch (error) {
        showToast(error.message, "danger");
    }
}

async function showDocumentDetail(docId) {
    const modal = new bootstrap.Modal(document.getElementById("document-detail-modal"));
    const body = document.getElementById("document-detail-body");
    showLoading(body, "正在加载资料详情...");
    modal.show();

    try {
        const data = await requestJSON(`/api/documents/${docId}`);
        const doc = data.data.document;
        const chunks = data.data.chunks || [];

        body.innerHTML = `
            <dl class="row mb-2">
                <dt class="col-sm-3">资料 ID</dt><dd class="col-sm-9">${doc.id}</dd>
                <dt class="col-sm-3">原始文件名</dt><dd class="col-sm-9">${escapeHtml(doc.original_name)}</dd>
                <dt class="col-sm-3">文件类型</dt><dd class="col-sm-9 text-uppercase">${escapeHtml(doc.file_ext)}</dd>
                <dt class="col-sm-3">状态</dt><dd class="col-sm-9"><span class="badge text-bg-light">${escapeHtml(doc.status)}</span></dd>
                <dt class="col-sm-3">文本长度</dt><dd class="col-sm-9">${(doc.content_length || 0).toLocaleString()} 字符</dd>
                <dt class="col-sm-3">分块数量</dt><dd class="col-sm-9">${doc.chunk_count ?? 0} 个片段</dd>
                <dt class="col-sm-3">上传者</dt><dd class="col-sm-9">${escapeHtml(doc.uploaded_by || "")}</dd>
                <dt class="col-sm-3">上传时间</dt><dd class="col-sm-9">${escapeHtml(doc.created_at || "")}</dd>
                <dt class="col-sm-3">更新时间</dt><dd class="col-sm-9">${escapeHtml(doc.updated_at || "")}</dd>
            </dl>
            <hr>
            <h6>分块内容预览（共 ${chunks.length} 块）</h6>
            ${chunks.length ? chunks.map((c, i) => `
                <div class="chunk-preview card mb-2">
                    <div class="card-header py-1 small text-secondary">片段 #${c.chunk_index} — ${c.chunk_id}</div>
                    <div class="card-body py-2">
                        <pre class="chunk-content mb-0">${escapeHtml(c.content_preview || c.content)}</pre>
                    </div>
                </div>
            `).join("") : '<div class="text-secondary">暂无分块数据</div>'}
        `;
    } catch (error) {
        body.innerHTML = `<div class="alert alert-danger">${escapeHtml(error.message)}</div>`;
    }
}

// =========================================================================
// 资料批量操作
// =========================================================================

function initDocumentSelectAll() {
    const selectAll = document.getElementById("select-all-docs");
    if (!selectAll) return;

    selectAll.addEventListener("change", () => {
        const checkboxes = document.querySelectorAll(".doc-checkbox");
        checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
        updateBatchDeleteButton();
    });

    document.addEventListener("change", (e) => {
        if (e.target.classList.contains("doc-checkbox")) {
            updateBatchDeleteButton();
        }
    });
}

function initDocumentBatchDelete() {
    // 委托已在 initDocumentSelectAll 的 checkbox 监听中覆盖
}

function updateBatchDeleteButton() {
    const checked = document.querySelectorAll(".doc-checkbox:checked");
    const btn = document.getElementById("batch-delete-btn");
    if (btn) {
        btn.classList.toggle("d-none", checked.length === 0);
        btn.textContent = `批量删除 (${checked.length})`;
    }
}

async function batchDeleteDocuments() {
    const checked = document.querySelectorAll(".doc-checkbox:checked");
    if (!checked.length) return;

    const ids = Array.from(checked).map(cb => parseInt(cb.value));
    if (!confirm(`确定要删除选中的 ${ids.length} 个资料吗？此操作不可恢复。`)) return;

    try {
        showToast(`正在删除 ${ids.length} 个资料...`, "info");
        const data = await requestJSON("/api/documents/batch-delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ids })
        });
        showToast(data.message || `已删除 ${ids.length} 个资料。`, "success");
        await refreshDocumentTables();
    } catch (error) {
        showToast(error.message, "danger");
    }
}

// =========================================================================
// 语义检索
// =========================================================================

function initSearchForm() {
    const form = document.getElementById("search-form");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        await doSearch(1);
    });
}

async function doSearch(page = 1) {
    const keyword = document.getElementById("search-keyword").value.trim();
    const topK = Number(document.getElementById("search-top-k").value || 5);
    const mode = document.getElementById("search-mode")?.value || "semantic";
    const resultsBox = document.getElementById("search-results");
    const paginationBox = document.getElementById("search-pagination");

    if (!keyword) {
        resultsBox.innerHTML = '<div class="alert alert-warning">请输入检索内容。</div>';
        return;
    }

    try {
        showLoading(resultsBox, "正在检索...");
        const data = await requestJSON("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ keyword, top_k: topK, mode, page, per_page: topK })
        });

        const items = data.items || [];
        const total = data.total || 0;
        const currentPage = data.page || 1;
        const totalPages = Math.ceil(total / topK);

        if (!items.length) {
            resultsBox.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <div class="empty-state-text">没有找到相关片段</div>
                    <div class="small text-secondary">请尝试更换检索词或上传更多资料</div>
                </div>`;
            if (paginationBox) paginationBox.classList.add("d-none");
            await refreshHistoryTables();
            return;
        }

        const modeLabel = { semantic: "语义检索", keyword: "关键词匹配", hybrid: "混合检索" }[mode] || mode;
        resultsBox.innerHTML = `
            <div class="small text-secondary mb-2">${modeLabel} · 共 ${total} 条结果 · 第 ${currentPage}/${totalPages} 页</div>
            ${items.map((item, index) => `
                <div class="search-result-card">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong>结果 ${(currentPage - 1) * topK + index + 1}</strong>
                        <span class="badge ${item.score ? 'text-bg-success' : 'text-bg-secondary'}">${item.score ? `相似度：${item.score}` : '关键词匹配'}</span>
                    </div>
                    <div class="meta mb-2">
                        资料：${escapeHtml(item.metadata?.document_name || "未知资料")}
                        ／ 片段：${item.metadata?.chunk_index ?? "-"}
                    </div>
                    <div class="result-content">${highlightKeyword(item.content || "", keyword)}</div>
                </div>
            `).join("")}`;

        // 分页导航
        if (paginationBox && totalPages > 1) {
            paginationBox.classList.remove("d-none");
            let paginationHtml = "";
            for (let p = 1; p <= totalPages; p++) {
                paginationHtml += `<button class="btn btn-sm ${p === currentPage ? 'btn-primary' : 'btn-outline-secondary'} me-1" onclick="doSearch(${p})">${p}</button>`;
            }
            paginationBox.innerHTML = paginationHtml;
        } else if (paginationBox) {
            paginationBox.classList.add("d-none");
        }

        await refreshHistoryTables();
    } catch (error) {
        resultsBox.innerHTML = `<div class="alert alert-danger">${escapeHtml(error.message)}</div>`;
        showToast(error.message, "danger");
    }
}

// =========================================================================
// RAG 智能问答
// =========================================================================

function initQaForm() {
    const form = document.getElementById("qa-form");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const question = document.getElementById("qa-question").value.trim();
        const topK = Number(document.getElementById("qa-top-k").value || 5);
        const answerBox = document.getElementById("qa-answer");
        const referencesBox = document.getElementById("qa-references");
        const citationsCard = document.getElementById("citations-card");
        const citationsBody = document.getElementById("citations-body");

        if (!question) {
            answerBox.innerHTML = '<div class="text-secondary">请输入问题。</div>';
            return;
        }

        try {
            showLoading(answerBox, "正在检索知识库并生成回答...");
            if (referencesBox) referencesBox.innerHTML = "";
            if (citationsCard) citationsCard.classList.add("d-none");

            const data = await requestJSON("/api/qa", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question, top_k: topK })
            });

            // 渲染答案（支持 Markdown）
            const answer = data.data?.answer || "模型未返回有效回答。";
            if (typeof marked !== "undefined") {
                answerBox.innerHTML = marked.parse(answer);
            } else {
                answerBox.innerHTML = `<pre class="answer-text">${escapeHtml(answer)}</pre>`;
            }

            // 渲染引用来源
            const citations = data.data?.citations || [];
            const references = data.data?.references || [];

            if (referencesBox) {
                referencesBox.innerHTML = references.length
                    ? references.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
                    : "<li>暂无引用</li>";
            }

            if (citationsCard && citations.length) {
                citationsCard.classList.remove("d-none");
                citationsBody.innerHTML = citations.map((c) => `
                    <div class="citation-item mb-2 p-2 border rounded">
                        <div class="small fw-bold">[${c.id}] ${escapeHtml(c.document_name)} — 片段 #${c.chunk_index}</div>
                        <div class="small text-secondary mt-1">
                            <pre class="citation-snippet mb-0">${escapeHtml(c.snippet || "")}</pre>
                        </div>
                    </div>
                `).join("");
            }

            await refreshHistoryTables();
        } catch (error) {
            answerBox.innerHTML = `<div class="alert alert-danger">问答失败：${escapeHtml(error.message)}</div>`;
            if (referencesBox) referencesBox.innerHTML = "<li>暂无引用</li>";
            showToast(error.message, "danger");
        }
    });
}

// =========================================================================
// 历史记录
// =========================================================================

function initHistoryRefresh() {
    const button = document.getElementById("refresh-history-button");
    if (!button) return;

    button.addEventListener("click", async () => {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>刷新中';
        try {
            await refreshHistoryTables();
            showToast("历史记录已刷新。", "success");
        } finally {
            button.disabled = false;
            button.textContent = "刷新数据";
        }
    });
}

async function refreshHistoryTables() {
    const qaHistoryBody = document.querySelector("#history-qa-table tbody");
    const searchHistoryBody = document.querySelector("#history-search-table tbody");
    const qaRecentBody = document.querySelector("#qa-history-table tbody");
    const searchRecentBody = document.querySelector("#search-history-table tbody");

    if (!qaHistoryBody && !searchHistoryBody && !qaRecentBody && !searchRecentBody) return;

    const data = await requestJSON("/api/history");
    const qaItems = data.qa_histories || [];
    const searchItems = data.search_histories || [];

    const qaRows = qaItems.length
        ? qaItems.map((item) => `
            <tr>
                <td>${escapeHtml(item.created_at || "")}</td>
                <td>${escapeHtml(item.question || "")}</td>
                <td>${escapeHtml(item.reference_documents || "")}</td>
            </tr>`).join("")
        : '<tr><td colspan="3" class="text-center text-secondary py-3">暂无问答历史</td></tr>';

    const searchRows = searchItems.length
        ? searchItems.map((item) => `
            <tr>
                <td>${escapeHtml(item.created_at || "")}</td>
                <td>${escapeHtml(item.keyword || "")}</td>
                <td>${item.top_k ?? 0}</td>
            </tr>`).join("")
        : '<tr><td colspan="3" class="text-center text-secondary py-3">暂无检索历史</td></tr>';

    if (qaHistoryBody) qaHistoryBody.innerHTML = qaRows;
    if (qaRecentBody) qaRecentBody.innerHTML = qaRows;
    if (searchHistoryBody) searchHistoryBody.innerHTML = searchRows;
    if (searchRecentBody) searchRecentBody.innerHTML = searchRows;
}

// =========================================================================
// 权限管理
// =========================================================================

function initRoleManagement() {
    const userTable = document.getElementById("user-table");
    const refreshUsersButton = document.getElementById("refresh-users-button");
    if (!userTable && !refreshUsersButton) return;

    if (refreshUsersButton) {
        refreshUsersButton.addEventListener("click", async () => {
            refreshUsersButton.disabled = true;
            try {
                await refreshUserTable();
                showToast("用户列表已刷新。", "success");
            } finally {
                refreshUsersButton.disabled = false;
            }
        });
    }

    if (userTable) {
        userTable.addEventListener("click", async (event) => {
            const button = event.target.closest(".update-role-button");
            if (!button) return;

            const row = button.closest("tr");
            const userId = row.getAttribute("data-user-id");
            const role = row.querySelector(".role-select").value;

            button.disabled = true;
            try {
                const data = await requestJSON(`/api/admin/users/${userId}/role`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ role })
                });
                showToast(data.message || "角色更新成功。", "success");
                await refreshUserTable();
            } catch (error) {
                showToast(`角色更新失败：${error.message}`, "danger");
            } finally {
                button.disabled = false;
            }
        });
    }
}

async function refreshUserTable() {
    const userTableBody = document.querySelector("#user-table tbody");
    if (!userTableBody) return;

    const data = await requestJSON("/api/admin/users");
    const items = data.items || [];

    userTableBody.innerHTML = items.length
        ? items.map((item) => `
            <tr data-user-id="${item.id}">
                <td>${item.id}</td>
                <td>${escapeHtml(item.username)}</td>
                <td>
                    <select class="form-select form-select-sm role-select">
                        <option value="student" ${item.role === "student" ? "selected" : ""}>学生</option>
                        <option value="topic_admin" ${item.role === "topic_admin" ? "selected" : ""}>课题管理员</option>
                        <option value="academic_admin" ${item.role === "academic_admin" ? "selected" : ""}>教务管理员</option>
                        <option value="audit_admin" ${item.role === "audit_admin" ? "selected" : ""}>审计管理员</option>
                    </select>
                </td>
                <td>${escapeHtml(item.created_at || "")}</td>
                <td>${escapeHtml(item.last_login_at || "")}</td>
                <td><button class="btn btn-sm btn-primary update-role-button">保存角色</button></td>
            </tr>`).join("")
        : '<tr><td colspan="6" class="text-center text-secondary py-3">暂无用户</td></tr>';
}

// =========================================================================
// 审计日志
// =========================================================================

function initAuditRefresh() {
    const button = document.getElementById("refresh-audits-button");
    if (!button) return;

    button.addEventListener("click", async () => {
        button.disabled = true;
        try {
            await refreshAuditTable();
            showToast("审计日志已刷新。", "success");
        } finally {
            button.disabled = false;
        }
    });
}

async function refreshAuditTable() {
    const tableBody = document.querySelector("#audit-table tbody");
    if (!tableBody) return;

    const data = await requestJSON("/api/audits");
    const items = data.items || [];

    tableBody.innerHTML = items.length
        ? items.map((item) => `
            <tr>
                <td>${escapeHtml(item.created_at || "")}</td>
                <td>${escapeHtml(item.username || "")}</td>
                <td>${escapeHtml(item.action || "")}</td>
                <td>${escapeHtml((item.target_type || "") + " / " + (item.target_id || ""))}</td>
                <td>${escapeHtml(item.detail || "")}</td>
                <td>${escapeHtml(item.ip_address || "")}</td>
            </tr>`).join("")
        : '<tr><td colspan="6" class="text-center text-secondary py-3">暂无审计日志</td></tr>';
}
