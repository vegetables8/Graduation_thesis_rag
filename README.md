# Flask + SQLite + ChromaDB 毕设选题指导系统

基于 Flask 的 RAG（检索增强生成）选题指南库 Web 应用，集成 ChromaDB 向量检索与智谱 AI 大模型。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | Flask 3.x |
| 数据库 | SQLite + SQLAlchemy |
| 向量数据库 | ChromaDB 1.5.x |
| Embedding | 智谱 AI Embedding API（embedding-3） |
| 大语言模型 | 智谱 AI GLM-4-Flash |
| 前端 | Bootstrap 5.3 + 原生 JavaScript + marked.js |
| 课题资料解析 | PyPDF2, python-docx |

## 功能特性

### 核心功能
- **语义检索**：基于向量相似度的选题指南库搜索，支持语义/关键词/混合三种模式
- **RAG 智能问答**：检索选题指南库 + 大模型生成，答案带引用溯源
- **课题资料管理**：上传、查看、重建索引、删除（含级联清理向量与文件）
- **用户注册**：自助注册，默认获得学生权限
- **密码修改**：登录后修改密码

### 权限体系
| 角色 | 用户名 | 权限 |
|------|--------|------|
| 学生 | student | 检索、问答、历史、注册 |
| 课题管理员 | topic_admin | + 课题资料上传、删除、重索引 |
| 教务管理员 | academic_admin | + 用户角色管理 |
| 审计管理员 | audit_admin | + 审计日志查看 |

### 其他
- 课题资料详情 Modal 展示（分块内容预览）
- 批量课题资料删除
- 搜索分页与结果高亮
- 答案 Markdown 渲染
- Toast 通知系统
- 历史记录 CSV 导出
- 系统健康检查 API

## 项目结构

```text
大三下毕设选题_计算三/
├── app.py                          # 启动入口
├── config.py                       # 配置类（BaseConfig / DevelopmentConfig）
├── .env                            # 环境变量（需自行创建）
├── .env.example                    # 环境变量模板
├── requirements.txt
├── instance/
│   └── app.db                      # SQLite 数据库
├── app/
│   ├── __init__.py                 # 应用工厂 + 启动校验
│   ├── models.py                   # User / Document / DocumentChunk / QueryHistory / SearchHistory / AuditLog
│   ├── decorators.py               # @login_required / @role_required
│   ├── routes/
│   │   ├── auth.py                 # /login, /logout, /register, /change-password
│   │   ├── main.py                 # 页面路由 + API（CRUD、检索、问答、历史、导出、健康检查）
│   │   └── admin.py                # 用户管理 + 审计日志 API
│   ├── services/
│   │   ├── document_service.py     # 上传、解析、索引、删除、重索引、批量删除
│   │   ├── vector_service.py       # ChromaDB 封装
│   │   ├── zhipu_embedding.py      # 智谱 AI Embedding（ChromaDB EmbeddingFunction）
│   │   ├── rag_service.py          # 语义检索、关键词检索、混合检索、RAG 问答
│   │   └── audit_service.py        # 审计日志写入
│   ├── utils/
│   │   ├── file_parser.py          # txt / md / pdf / docx 解析
│   │   └── text_chunker.py         # 段落感知的文本分块
│   ├── templates/                  # Jinja2 模板（10 个页面）
│   ├── static/
│   │   ├── css/custom.css
│   │   └── js/main.js
│   ├── uploads/                    # raw / parsed
│   └── data/chroma_db/             # ChromaDB 持久化
```

## 快速启动

### 1. 创建虚拟环境

```bash
python -m venv .venv_new
.venv_new\Scripts\activate  # Windows
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
copy .env.example .env
# 编辑 .env，填入智谱 AI API Key
```

### 4. 启动

```bash
python app.py
```

访问 `http://127.0.0.1:5000`

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| student | Stu@123 | 学生 |
| topic_admin | TopicAdmin@123 | 课题管理员 |
| academic_admin | AcadAdmin@123 | 教务管理员 |
| audit_admin | Audit@123 | 审计管理员 |

## API 速览

| 端点 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `/api/documents` | GET | 登录 | 课题资料列表 |
| `/api/documents/<id>` | GET | 登录 | 课题资料详情 + 分块 |
| `/api/documents/<id>` | DELETE | topic_admin | 删除课题资料 |
| `/api/documents/<id>/reindex` | POST | topic_admin | 重建索引 |
| `/api/documents/batch-delete` | POST | topic_admin | 批量删除 |
| `/api/documents/upload` | POST | topic_admin | 上传课题资料 |
| `/api/search` | POST | 登录 | 检索（semantic/keyword/hybrid） |
| `/api/search/suggestions` | GET | 登录 | 搜索建议 |
| `/api/qa` | POST | 登录 | RAG 问答 |
| `/api/history` | GET | 登录 | 问答/检索历史 |
| `/api/history/export` | GET | 登录 | 导出 CSV |
| `/api/health` | GET | 登录 | 系统健康检查 |

## 清空数据

```bash
rm instance/app.db
rm -rf app/data/chroma_db
rm -rf app/uploads/raw/*
rm -rf app/uploads/parsed/*
```
