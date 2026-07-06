document.addEventListener("DOMContentLoaded", () => {
    bindUploadForm();
    bindSearch();
    bindQa();
    bindRoleUpdate();
});

function bindUploadForm() {
    const form = document.getElementById("upload-form");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const fileInput = document.getElementById("upload-file");
        if (!fileInput.files.length) {
            showMessage("upload-message", "请先选择文件。", "warning");
            return;
        }

        const formData = new FormData();
        formData.append("file", fileInput.files[0]);

        try {
            showMessage("upload-message", "正在上传并建立索引，请稍候...", "info");
            const response = await fetch("/api/documents/upload", {
                method: "POST",
                body: formData
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.message || "上传失败");
            }
            showMessage("upload-message", data.message, "success");
            await refreshDocuments();
        } catch (error) {
            showMessage("upload-message", error.message, "danger");
        }
    });
}

async function refreshDocuments() {
    const table = document.querySelector("#document-table tbody");
    if (!table) return;

    const data = await requestJSON("/api/documents");
    if (!data.items.length) {
        table.innerHTML = '<tr><td colspan="6" class="text-center text-muted">暂无文档</td></tr>';
        return;
    }

    table.innerHTML = data.items.map((item) => `
        <tr>
            <td>${item.id}</td>
            <td>${item.original_name}</td>
            <td><span class="badge text-bg-secondary">${item.status}</span></td>
            <td>${item.chunk_count}</td>
            <td>${item.uploaded_by}</td>
            <td>${item.created_at}</td>
        </tr>
    `).join("");
}

function bindSearch() {
    const button = document.getElementById("search-button");
    if (!button) return;

    button.addEventListener("click", async () => {
        const keyword = document.getElementById("search-keyword").value.trim();
        const topK = Number(document.getElementById("search-top-k").value || 5);
        const resultsBox = document.getElementById("search-results");

        if (!keyword) {
            resultsBox.innerHTML = '<div class="alert alert-warning">请输入检索内容。</div>';
            return;
        }

        try {
            resultsBox.innerHTML = '<div class="text-muted">正在检索，请稍候...</div>';
            const data = await requestJSON("/api/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    keyword,
                    top_k: topK
                })
            });

            const items = data.items || [];
            if (!items.length) {
                resultsBox.innerHTML = '<div class="alert alert-secondary">没有找到相关片段。</div>';
                return;
            }

            resultsBox.innerHTML = items.map((item, index) => `
                <div class="search-result-card">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <strong>结果 ${index + 1}</strong>
                        <span class="badge text-bg-success">相似度：${item.score ?? "未知"}</span>
                    </div>
                    <div class="meta mb-2">
                        文档：${item.metadata.document_name || "未知"} / 片段：${item.metadata.chunk_index ?? "-"}
                    </div>
                    <div>${escapeHtml(item.content)}</div>
                </div>
            `).join("");

            await refreshHistories();
        } catch (error) {
            resultsBox.innerHTML = `<div class="alert alert-danger">${error.message}</div>`;
        }
    });
}

function bindQa() {
    const button = document.getElementById("qa-button");
    if (!button) return;

    button.addEventListener("click", async () => {
        const question = document.getElementById("qa-question").value.trim();
        const topK = Number(document.getElementById("qa-top-k").value || 5);
        const answerBox = document.getElementById("qa-answer");
        const refBox = document.getElementById("qa-references");

        if (!question) {
            answerBox.textContent = "请输入问题。";
            return;
        }

        try {
            answerBox.textContent = "正在检索相关上下文并生成回答，请稍候...";
            const data = await requestJSON("/api/qa", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    question,
                    top_k: topK
                })
            });

            answerBox.textContent = data.data.answer || "暂无回答";
            const references = data.data.references || [];
            refBox.innerHTML = references.length
                ? references.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
                : "<li>暂无引用</li>";

            await refreshHistories();
        } catch (error) {
            answerBox.textContent = `问答失败：${error.message}`;
        }
    });
}

async function refreshHistories() {
    const qaTable = document.querySelector("#qa-history-table tbody");
    const searchTable = document.querySelector("#search-history-table tbody");
    if (!qaTable || !searchTable) return;

    const data = await requestJSON("/api/history");
    const qaItems = data.qa_histories || [];
    const searchItems = data.search_histories || [];

    qaTable.innerHTML = qaItems.length
        ? qaItems.map((item) => `
            <tr>
                <td>${item.created_at}</td>
                <td>${escapeHtml(item.question)}</td>
                <td>${escapeHtml(item.reference_documents)}</td>
            </tr>
        `).join("")
        : '<tr><td colspan="3" class="text-center text-muted">暂无问答历史</td></tr>';

    searchTable.innerHTML = searchItems.length
        ? searchItems.map((item) => `
            <tr>
                <td>${item.created_at}</td>
                <td>${escapeHtml(item.keyword)}</td>
                <td>${item.top_k}</td>
            </tr>
        `).join("")
        : '<tr><td colspan="3" class="text-center text-muted">暂无检索历史</td></tr>';
}

function bindRoleUpdate() {
    const buttons = document.querySelectorAll(".update-role-button");
    if (!buttons.length) return;

    buttons.forEach((button) => {
        button.addEventListener("click", async (event) => {
            const row = event.target.closest("tr");
            const userId = row.getAttribute("data-user-id");
            const role = row.querySelector(".role-select").value;

            try {
                const data = await requestJSON(`/api/admin/users/${userId}/role`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ role })
                });
                window.alert(data.message);
            } catch (error) {
                window.alert(`角色更新失败：${error.message}`);
            }
        });
    });
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}
