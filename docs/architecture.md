# 基于agent智能化改造的企业招聘信息问答助手 — 架构说明

> **文档版本**：v1.0  
> **最后更新**：2026-06-16  
> **项目方向**：企业级应用软件的 Agent 改造

---

## 目录

1. [架构总览](#1-架构总览)
2. [分层架构](#2-分层架构)
3. [模块详解](#3-模块详解)
4. [数据模型](#4-数据模型)
5. [核心流程](#5-核心流程)
6. [路由设计](#6-路由设计)
7. [前端架构](#7-前端架构)
8. [安全设计](#8-安全设计)
9. [关键设计决策](#9-关键设计决策)
10. [扩展点与未来演进](#10-扩展点与未来演进)

---

## 1. 架构总览

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              浏览器 (Browser)                             │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │   首页/聊天    │ │  简历追踪     │ │  管理员登录   │ │  管理后台     │   │
│  │  index/chat  │ │  my-resumes  │ │  admin/login │ │ admin/*      │   │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │
│         │                │                │                │            │
│         │    SSE / AJAX  │    AJAX        │    POST+Flash   │   AJAX    │
└─────────┼────────────────┼────────────────┼────────────────┼────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Flask 应用层 (app.py)                             │
│                                                                          │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  auth_bp     │ │  resume_bp   │ │  policy_bp   │ │  agent_bp    │   │
│  │  认证蓝图     │ │  简历蓝图     │ │  政策蓝图     │ │  AI Agent    │   │
│  │              │ │              │ │              │ │  蓝图         │   │
│  │ · 登录/登出   │ │ · 上传/编辑   │ │ · 增删改查    │ │ · RAG 检索   │   │
│  │ · Session    │ │ · 邮箱查找    │ │ · 文本提取    │ │ · LLM 调用   │   │
│  │ · 密码哈希    │ │ · 状态追踪    │ │ · TF-IDF    │ │ · SSE 流式   │   │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬───────┘   │
│         │                │                │                │            │
│  ┌──────┴────────────────┴────────────────┴────────────────┴───────┐   │
│  │                    api_config_bp (API 配置)                       │   │
│  │              多提供商自动检测 + 连接测试 + 配置持久化                │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          数据访问层 (database.py)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Admin   │  │ ApiSettings│ │  Resume  │  │  Policy  │  │ChatHistory│ │
│  │  管理员   │  │  API 配置  │  │  简历    │  │  政策库   │  │  对话历史  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                         SQLite (instance/app.db)                        │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           外部服务 (External)                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   OpenAI API     │  │   DeepSeek API   │  │   Zhipu / 其他   │      │
│  │  (GPT-4o/3.5)   │  │  (DeepSeek-V3)   │  │   国内模型 API    │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 技术特征

| 维度 | 特征 |
|------|------|
| **架构风格** | 单体应用 + Blueprint 模块化，前后端不分离（服务端模板渲染 + 原生 JS AJAX） |
| **Agent 智能化** | RAG 检索增强生成：TF-IDF 检索 → LLM 合成 → 降级策略（纯检索回退） |
| **数据库** | SQLite 单文件数据库，通过 Flask-SQLAlchemy ORM 操作，支持无感迁移 |
| **前端交互** | Bootstrap 5 响应式布局 + 原生 JS（无框架），核心交互走 AJAX/SSE |
| **部署模式** | 单进程 Flask 开发服务器（`app.run`），适合内网/本机部署 |
| **可移植性** | 全相对路径、SQLite 数据库文件随项目移动、无外部服务依赖 |

---

## 2. 分层架构

```
┌─────────────────────────────────────────────┐
│              表示层 (Presentation)            │
│  templates/ (Jinja2 模板) + static/ (CSS/JS) │
├─────────────────────────────────────────────┤
│              路由层 (Routing)                 │
│  app.py 主路由 + 5 个 Blueprint              │
├─────────────────────────────────────────────┤
│            业务逻辑层 (Business Logic)         │
│  modules/agent.py    — RAG + LLM 合成        │
│  modules/policy.py   — 检索算法 + 文档管理    │
│  modules/resume.py   — 简历追踪状态机         │
│  modules/auth.py     — 认证与密码管理         │
│  modules/api_config.py — API 自动检测与配置    │
├─────────────────────────────────────────────┤
│              数据访问层 (Data Access)          │
│  modules/database.py — ORM 模型 + 迁移 + 初始化│
├─────────────────────────────────────────────┤
│              基础设施层 (Infrastructure)       │
│  config.py — 全局配置 / SQLite — 数据持久化    │
│  prompts/ — 系统提示词 / data/ — 文件存储      │
└─────────────────────────────────────────────┘
```

### 分层原则

- **表示层**不包含业务逻辑，仅负责渲染和用户交互事件绑定
- **路由层**作为薄层，负责 URL 映射、请求参数提取、权限检查
- **业务逻辑层**集中于 `modules/` 下各 Blueprint 的私有函数中，与 Flask 请求上下文解耦
- **数据访问层**通过 SQLAlchemy 模型统一封装，业务代码不直接写 SQL
- 层间依赖单向向下：表示层 → 路由层 → 业务层 → 数据层

---

## 3. 模块详解

### 3.1 主入口 — `app.py`

**职责**：应用工厂、启动流程编排、浏览器自动打开

```
启动时序:
  python app.py
    ├── 1. 仅加载 os, sys (轻量模块) → 立即打印欢迎横幅 (~0ms)
    ├── 2. create_app()
    │     ├── 导入 Flask/SQLAlchemy/Blueprints (延迟导入)
    │     ├── 加载 config.py 配置
    │     ├── 初始化数据库 init_db()
    │     │     ├── db.create_all() 创建表
    │     │     ├── 自动迁移 _migrate_resume_table()
    │     │     ├── 创建默认管理员 _create_default_admin()
    │     │     └── 可选导入示例政策
    │     └── 注册 5 个 Blueprint
    ├── 3. 后台线程：导入示例政策（不阻塞）
    ├── 4. 后台线程：轮询端口就绪 → 自动打开浏览器
    └── 5. app.run(host='0.0.0.0', port=5000)
```

**关键设计**：
- **延迟导入**：Flask、SQLAlchemy 等重模块仅在 `create_app()` 内部导入，确保启动后立即有终端输出
- **后台线程**：示例政策导入和浏览器轮询均不阻塞主线程
- **ANSI 彩色输出**：Windows 终端通过 `os.system('')` 启用 VT100 支持

### 3.2 数据库模块 — `modules/database.py`

**职责**：ORM 模型定义、数据库初始化、无感迁移、示例数据导入

#### 模型定义

| 模型 | 表名 | 核心字段 | 说明 |
|------|------|----------|------|
| `Admin` | `admin` | id, username, password_hash, created_at | 管理员账号 |
| `ApiSettings` | `api_settings` | id, key, value, updated_at | KV 配置存储 |
| `Resume` | `resumes` | id, name, email, phone, position, file_path, content_text, **status**, **viewed_at**, updated_at, submitted_at | 简历 + 追踪状态 |
| `Policy` | `policies` | id, title, category, file_path, content_text, created_at, updated_at | 政策文档 |
| `ChatHistory` | `chat_history` | id, session_id (索引), role, content, created_at | 对话历史 |

#### 数据库迁移策略

```
_migrate_resume_table() 流程:
  1. 通过 SQLAlchemy inspector 检查现有列
  2. 对缺失列使用 ALTER TABLE ADD COLUMN (带默认值)
  3. 幂等安全：已有列不重复添加
  4. 事务保护：conn.commit()
```

该策略避免了 SQLite 不完整 DDL 支持的限制，支持从旧版本数据库平滑升级。

### 3.3 AI Agent 模块 — `modules/agent.py`

这是本项目的**核心智能化模块**，实现了完整的 Agent 流水线。

#### 3.3.1 Agent 架构

```
用户输入
    │
    ▼
┌────────────────────┐
│  1. Session 管理    │  _get_or_create_session_id()
│  2. 保存用户消息     │  _save_message(session_id, 'user', query)
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  3. RAG 检索阶段    │  _build_context_prompt(query)
│                    │    ├── search_policies(query, top_k=5)
│                    │    └── 组装政策上下文 Prompt
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  4. LLM 生成阶段   │  _call_llm_api(system_prompt, context, query, history)
│                    │    ├── _detect_api_type(api_url) → 提供商适配
│                    │    ├── 构建 Messages: System + History + User
│                    │    └── HTTP POST → 解析响应
└───────┬────────────┘
        │
        ▼
┌────────────────────┐
│  5. 降级策略        │  API 不可用 or 无政策 → 检索原文 or 提示信息
│  6. 保存 AI 回答   │  _save_message(session_id, 'assistant', answer)
│  7. 返回 JSON      │  {answer, sources, fallback_mode}
└────────────────────┘
```

#### 3.3.2 多提供商 API 适配

`_detect_api_type(api_url)` 函数通过 URL 模式匹配自动检测 API 类型：

```
┌──────────────────────┬──────────────────┬─────────────────────────────────┐
│ API 提供商           │ URL 特征          │ 适配策略                         │
├──────────────────────┼──────────────────┼─────────────────────────────────┤
│ OpenAI               │ api.openai.com    │ 标准格式（无需额外处理）          │
│ DeepSeek             │ deepseek.com      │ 标准格式                        │
│ 智谱 GLM             │ bigmodel.cn       │ 标准格式                        │
│ 月之暗面 Kimi        │ moonshot.cn       │ 标准格式                        │
│ 阿里通义千问         │ dashscope.aliyuncs│ 标准格式                        │
│ 百川智能             │ baichuan-ai.com   │ 标准格式                        │
│ 字节豆包             │ volces/volcengine │ 标准格式                        │
│ SiliconFlow          │ siliconflow.cn    │ 标准格式                        │
│ MiniMax              │ minimax.chat      │ 禁用 stream，使用不同响应路径    │
│ Ollama               │ ollama            │ 禁用 stream（默认）              │
└──────────────────────┴──────────────────┴─────────────────────────────────┘
```

返回值结构：
```python
{
    'supports_stream': bool,        # 是否支持 SSE 流式
    'supports_max_tokens': bool,    # max_tokens vs max_completion_tokens
    'use_json_content_type': bool,  # Content-Type
    'extra_headers': {},            # 额外请求头
    'extra_payload': {},            # 额外请求体字段
    'response_path': ('choices', 0, 'message', 'content'),  # 响应提取路径
}
```

#### 3.3.3 双模式响应

| 模式 | 路由 | 响应方式 | 适用场景 |
|------|------|----------|----------|
| 标准模式 | `POST /chat/send` | JSON 一次性返回 | 常规使用、非流式 API |
| 流式模式 | `POST /chat/stream` | SSE 逐字推送 | 支持 streaming 的 API |

流式模式使用 Flask `Response + stream_with_context`，前端通过 `EventSource` 或 `fetch` 读取 SSE 流。

### 3.4 政策库模块 — `modules/policy.py`

#### 3.4.1 CRUD 管理

标准的 RESTful 风格资源管理：
- `GET /admin/policies` — 列表页（按分类筛选）
- `POST /admin/policies/upload` — 上传新文档
- `GET /admin/policies/<id>` — 获取详情（JSON）
- `PUT /admin/policies/<id>` — 更新内容
- `DELETE /admin/policies/<id>` — 删除（含关联文件清理）

#### 3.4.2 检索引擎 — `search_policies()`

```
┌─────────────────────────────────────────────────────────────┐
│                     检索算法流程                              │
│                                                              │
│  输入: query (用户问题), top_k (返回数量，默认5)              │
│                                                              │
│  1. Token 化: _tokenize(query)                               │
│     ├── 检测中文: '一' <= ch <= '鿿'                         │
│     ├── 中文: 生成 1-gram + 2-gram + 3-gram                  │
│     │   例: "招聘政策" → ['招','聘','政','策','招聘','聘政',  │
│     │                    '政策','招聘政','聘政策']             │
│     └── 英文: 按空格分词                                     │
│                                                              │
│  2. 评分策略 (对每条 Policy):                                │
│     ├── 完整子串匹配: +20 分                                 │
│     ├── 长子串匹配: +子串长度×2 分                           │
│     └── N-gram 计数: +出现次数×token长度 分                  │
│                                                              │
│  3. 片段提取:                                                │
│     ├── 定位最佳匹配位置 (最长子串首次出现处)                 │
│     └── 截取上下文 ~600 字 (向前200 + 向后400)               │
│                                                              │
│  4. 排序返回: 按 score 降序，取 top_k                        │
└─────────────────────────────────────────────────────────────┘
```

**设计权衡**：
- ✅ 零外部依赖：无需 jieba、scikit-learn 等分词库
- ✅ 中文友好：N-gram 天然适配中文（无词边界）
- ✅ 轻量快速：全内存扫描，适用于百级政策库
- ⚠️ 局限：纯关键词匹配，不包含语义理解；政策量级 > 1000 时需升级为向量检索

### 3.5 简历模块 — `modules/resume.py`

#### 3.5.1 简历追踪状态机

```
                    ┌──────────────┐
                    │  submitted   │  ← 初始状态（投递成功）
                    │  "未被查看"   │
                    └──────┬───────┘
                           │
                HR 访问简历详情页面
                (admin_resume_detail)
                           │
                           ▼
                    ┌──────────────┐
                    │   viewed     │  ← HR 已查看
                    │  "已被查看"   │
                    └──────┬───────┘
                           │
              用户编辑简历信息
              (edit_my_resume)
                           │
                           ▼
                    ┌──────────────┐
                    │  submitted   │  ← 自动回退
                    │  "未被查看"   │
                    └──────────────┘
```

**自动状态切换**（非手动）：
- `submitted → viewed`：管理员访问 `GET /admin/resumes/<id>` 时**自动触发**
- `viewed → submitted`：用户通过 `POST /my-resumes/<id>/edit` 修改简历时**自动触发**，同时清除 `viewed_at`

#### 3.5.2 用户会话追踪

```
Session 关联机制:
  POST /resume/upload
    └── session['my_resume_ids'].append(resume_id)
    └── session['resume_submitted'] = True
  
  GET /my-resumes
    └── Resume.query.filter(Resume.id.in_(session['my_resume_ids']))
  
  POST /my-resumes/lookup  (跨浏览器找回)
    └── 通过邮箱查找 → 关联到当前 session
```

#### 3.5.3 文档解析

统一的 `_extract_text(filepath, ext)` 函数，支持：
- `.txt` / `.md` → 直接读取（UTF-8）
- `.pdf` → PyPDF2 逐页提取
- `.docx` → python-docx 段落提取
- 所有异常均降级为友好提示字符串，不中断流程

### 3.6 认证模块 — `modules/auth.py`

```
认证流程:
  POST /admin/login
    ├── 查 Admin 表
    ├── werkzeug.security.check_password_hash()
    ├── session['admin_logged_in'] = True
    └── redirect → dashboard

权限检查:
  @login_required 装饰器
    ├── 检查 session['admin_logged_in']
    ├── → 通过: 执行原函数
    └── → 未登录: redirect → /admin/login + Flash 消息
```

密码使用 `werkzeug.security.generate_password_hash()` 哈希存储，默认管理员 `admin/admin123` 在首次 `init_db()` 时创建。

### 3.7 API 配置模块 — `modules/api_config.py`

```
配置存储:
  ApiSettings 表 (KV 结构)
  ├── api_url        → https://api.openai.com/v1/chat/completions
  ├── api_key        → sk-*** (脱敏显示)
  ├── model_name     → gpt-3.5-turbo
  ├── system_prompt  → (管理员自定义，为空则用默认文件)
  ├── temperature    → 0.7
  └── max_tokens     → 2000
```

**连接测试**：`POST /admin/api/test` 发送简单对话测试请求，自动适配不同 API 的响应格式（多重 try-except 路径提取）。

---

## 4. 数据模型

### 4.1 ER 图

```
┌──────────────┐       ┌──────────────────┐
│    Admin     │       │   ApiSettings    │
├──────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)          │
│ username     │       │ key (UNIQUE)     │
│ password_hash│       │ value            │
│ created_at   │       │ updated_at       │
└──────────────┘       └──────────────────┘

┌──────────────┐       ┌──────────────────┐
│   Resume     │       │    Policy        │
├──────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)          │
│ name         │       │ title            │
│ email        │       │ category         │
│ phone        │       │ file_path        │
│ position     │       │ content_text     │
│ file_path    │       │ created_at       │
│ content_text │       │ updated_at       │
│ status    ───┼─┐     └──────────────────┘
│ viewed_at    │ │
│ updated_at   │ │  ┌──────────────────┐
│ submitted_at │ │  │  ChatHistory     │
└──────────────┘ │  ├──────────────────┤
                 │  │ id (PK)          │
                 └──│ session_id (IDX) │
    状态机:         │ role             │
    submitted ──→   │ content          │
    viewed          │ created_at       │
                    └──────────────────┘
```

### 4.2 关键索引

| 表 | 索引列 | 用途 |
|----|--------|------|
| ChatHistory | session_id | 按会话快速查询历史 |
| Admin | username (UNIQUE) | 登录查找 |
| ApiSettings | key (UNIQUE) | 配置项精确查找 |

---

## 5. 核心流程

### 5.1 RAG 问答完整流程

```
┌─────────────────────────────────────────────────────────────────────┐
│ 用户: "公司试用期多久？"                                               │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ 1. 路由分发       │ ──→ │ 2. Session 管理   │ ──→ │ 3. 保存用户消息   │
│ POST /chat/send  │     │ _get_or_create   │     │ ChatHistory      │
│ agent.send_msg() │     │ _session_id()    │     │ (role='user')    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        │
        ▼
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│ 4. 检索阶段       │ ──→ │ 5. 获取历史       │ ──→ │ 6. LLM 调用      │
│ search_policies  │     │ _get_recent      │     │ _call_llm_api    │
│ ("试用期多久")    │     │ _history()       │     │                  │
│                  │     │                  │     │ System Prompt:   │
│ Token 化:        │     │ 最近 10 轮       │     │ "你是专业招聘    │
│ ['试','用','期', │     │ User/Assistant   │     │  政策助手..."    │
│  '试用','用期',  │     │ 消息对            │     │                  │
│  '试用期']      │     │                  │     │ Context:         │
│                  │     │                  │     │ 【政策文档1】     │
│ 匹配结果:        │     │                  │     │ 标题: 入职管理..  │
│ 政策A (score:42) │     │                  │     │ 试用期一般为3-6   │
│ 政策B (score:18) │     │                  │     │ 个月...          │
│                  │     │                  │     │                  │
│ 返回 top-5       │     │                  │     │ User:            │
│ 上下文片段        │     │                  │     │ "请参考以上政策..."│
└──────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                           │
                                              ┌────────────┴─────────┐
                                              │ 成功?                 │
                                              ├── Yes → 解析回答      │
                                              └── No  → 降级为检索原文 │
                                                           │
                                                           ▼
                                              ┌──────────────────────┐
                                              │ 7. 保存 AI 回答       │
                                              │ ChatHistory          │
                                              │ (role='assistant')   │
                                              │                      │
                                              │ 8. 返回 JSON          │
                                              │ {answer, sources,     │
                                              │  fallback_mode}       │
                                              └──────────────────────┘
```

### 5.2 简历追踪流程

```
┌──────────────────────────────────────────────────────┐
│                   用户端视角                           │
│                                                       │
│  POST /resume/upload                                  │
│    └── session['my_resume_ids'] ← resume.id           │
│    └── status = 'submitted'                           │
│                                                       │
│  GET /my-resumes                                      │
│    └── 查询 session['my_resume_ids'] 关联的简历        │
│    └── 显示状态徽章: 🟡 未被查看 / 🔵 已被查看          │
│                                                       │
│  GET /my-resumes/<id>                                 │
│    └── 详情页 + 两步进度条                             │
│    └── 显示 viewed_at 时间 (如有)                      │
│                                                       │
│  POST /my-resumes/<id>/edit                           │
│    └── 更新基本信息                                    │
│    └── 如果 status == 'viewed' → 重置为 'submitted'   │
│                                                       │
│  POST /my-resumes/lookup                              │
│    └── 邮箱查找 → 关联到当前 session                   │
│    └── 支持跨浏览器找回                                │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│                   管理员视角                           │
│                                                       │
│  GET /admin/resumes                                   │
│    └── 列表: 分页 + 搜索 + 状态标签                    │
│                                                       │
│  GET /admin/resumes/<id>                              │
│    └── 查看详情                                        │
│    └── 自动: status = 'viewed', viewed_at = now()     │
│                                                       │
│  GET /admin/resumes/<id>/download                     │
│    └── 下载原始简历文件                                │
└──────────────────────────────────────────────────────┘
```

### 5.3 启动流程时序

```
main()
 │
 ├─ [0ms]    print 欢迎横幅 ◈ + "加载中..."
 ├─ [0ms]    create_app()
 │             ├─ import Flask, SQLAlchemy, Blueprints (延迟导入)
 │             ├─ app = Flask(...)
 │             ├─ init_db(app)
 │             │    ├─ db.create_all()
 │             │    ├─ _migrate_resume_table()
 │             │    ├─ _create_default_admin()
 │             │    └─ _init_default_api_settings()
 │             └─ register 5 Blueprints
 │
 ├─ [~50ms]  print "✓ 应用初始化完成 (XXms)"
 │
 ├─ [~50ms]  Thread-1: _deferred_import_samples()  ← 后台，不阻塞
 │             └─ _import_sample_policies(app)
 │                └─ 如果 Policy 表为空 → 导入 data/policies/*.txt
 │
 ├─ [~50ms]  Thread-2: _try_open_browser()  ← 后台轮询
 │             └─ loop: urllib.request.urlopen('http://127.0.0.1:5000')
 │                └─ 成功 → webbrowser.open('http://localhost:5000')
 │
 ├─ [~50ms]  app.run(host='0.0.0.0', port=5000)  ← 阻塞主线程
 │
 └─ [~200ms] Thread-2 检测就绪 → 打开浏览器 → print "✓ 浏览器已打开"
```

---

## 6. 路由设计

### 6.1 完整路由表

```
┌───────┬──────────────────────────────────┬──────────┬──────────────────────┐
│ 蓝图   │ 路由                             │ 方法     │ 说明                 │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│ app   │ /                                │ GET      │ 首页 (聊天 + 投递)    │
│       │ /chat                            │ GET      │ AI 问答聊天页面       │
│       │ /favicon.ico                     │ GET      │ 忽略 favicon 请求     │
│       │ /admin/dashboard                 │ GET      │ 管理仪表盘            │
│       │ /admin/resumes                   │ GET      │ 简历列表 (分页+搜索)   │
│       │ /admin/resumes/<id>              │ GET      │ 简历详情 (自动标记已看) │
│       │ /admin/resumes/<id>/download     │ GET      │ 下载简历文件           │
│       │ /admin/change-password           │ POST     │ 修改管理员密码         │
│       │ /admin/default-prompt            │ GET      │ 查看默认系统提示词     │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│ auth  │ /admin/login                     │ GET/POST │ 管理员登录/登出       │
│       │ /admin/logout                    │ GET      │                       │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│resume │ /resume/upload                   │ POST     │ 上传简历              │
│       │ /resume/check                    │ GET      │ 检查是否已投递         │
│       │ /resume/status/<id>              │ GET      │ AJAX 查询简历状态      │
│       │ /my-resumes                      │ GET      │ 用户简历列表           │
│       │ /my-resumes/lookup               │ POST     │ 邮箱查找简历           │
│       │ /my-resumes/<id>                 │ GET      │ 简历详情              │
│       │ /my-resumes/<id>/edit            │ POST     │ 编辑简历 (重置状态)    │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│policy │ /admin/policies                  │ GET      │ 政策库管理页           │
│       │ /admin/policies/upload           │ POST     │ 上传政策文档           │
│       │ /admin/policies/<id>             │ GET      │ 获取政策 JSON          │
│       │ /admin/policies/<id>             │ PUT      │ 更新政策文本           │
│       │ /admin/policies/<id>             │ DELETE   │ 删除政策               │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│ agent │ /chat/send                       │ POST     │ 发送消息 (一次性)      │
│       │ /chat/stream                     │ POST     │ 发送消息 (SSE 流式)    │
│       │ /chat/history                    │ GET      │ 获取聊天历史           │
│       │ /chat/clear                      │ POST     │ 清除对话历史           │
├───────┼──────────────────────────────────┼──────────┼──────────────────────┤
│api_cfg│ /admin/api                       │ GET      │ API 配置页面           │
│       │ /admin/api                       │ POST     │ 保存 API 配置          │
│       │ /admin/api/test                  │ POST     │ 测试 API 连接          │
└───────┴──────────────────────────────────┴──────────┴──────────────────────┘
```

### 6.2 权限矩阵

| 路由前缀 | 权限要求 |
|----------|----------|
| `/` `/chat` `/resume/*` `/my-resumes/*` | 无（公开访问） |
| `/admin/*` (除 `/admin/login`) | `@login_required`（管理员 Session） |
| `/admin/login` `/admin/logout` | 无（认证入口） |

---

## 7. 前端架构

### 7.1 页面组件树

```
base.html (母版)
├── 导航栏 (session 感知: 管理员菜单 vs 用户链接)
├── Flash 消息区
├── {% block content %} ... {% endblock %}
├── resume_modal.html (仅非管理员用户)
│   └── Bootstrap Modal — 简历投递表单
├── resume_toast.html (仅非管理员用户)
│   └── 右下角 Toast — 10 秒自动弹出提示
├── Bootstrap 5 JS (CDN)
├── resume-popup.js (全局)
│   ├── 10 秒计时 → 显示 Toast
│   ├── 点击 "投递简历" → 打开 Modal
│   ├── 表单提交 → AJAX POST /resume/upload
│   └── 成功 → 1.5s 后跳转 /my-resumes
└── {% block extra_scripts %} ... {% endblock %}

index.html
└── 左侧: 聊天区域 (chat.js)
│   ├── 欢迎区 + 快捷问题标签
│   ├── 消息列表 (user / assistant)
│   ├── 输入区 (Input + 发送按钮)
│   └── "新对话" 按钮
└── 右侧: 简历投递卡片 (仅非管理员)
    ├── 投递按钮
    └── 已投递状态指示器

chat.html (同 index.html 聊天区布局)

my_resumes.html
├── 简历卡片列表 (statue badge + 操作按钮)
├── 邮箱查找区 (当无简历时显示)
└── 编辑 Modal (修改基本信息)

my_resume_detail.html
├── 状态头部 (图标 + 时间)
├── 两步进度条 (投递成功 → HR 查看)
├── 基本信息表格
└── 简历文本预览
```

### 7.2 前端状态管理

```
客户端持久化:
  localStorage['resume_submitted']  → 是否已投递 (跨会话)
  sessionStorage['resume_toast_closed'] → Toast 是否已关闭 (当前标签页)

服务端状态 (通过 Session Cookie):
  session['my_resume_ids']         → 用户关联的简历 ID 列表
  session['resume_submitted']      → 投递标记
  session['chat_session_id']       → 对话会话 ID
  session['admin_logged_in']       → 管理员登录状态
```

### 7.3 流式渲染 (SSE)

```
chat.js 发送消息:
  ┌──────────────────────────────────────────────────┐
  │ fetch('/chat/send', {method:'POST', body: JSON}) │
  │   → 一次性获得完整回答                             │
  └──────────────────────────────────────────────────┘

实时流式 (可选升级路径):
  ┌──────────────────────────────────────────────────┐
  │ EventSource('/chat/stream') 或                   │
  │ fetch('/chat/stream') → ReadableStream           │
  │   → chunk → addMessage('assistant', delta)       │
  │   → {done: true} → 显示来源引用                   │
  └──────────────────────────────────────────────────┘
```

当前前端 `chat.js` 使用标准 `/chat/send` 一次性请求，服务端 `agent.py` 同时提供了 `/chat/stream` SSE 端点以备升级。

---

## 8. 安全设计

| 安全措施 | 实现方式 |
|----------|----------|
| **密码存储** | Werkzeug `generate_password_hash()` (PBKDF2 + Salt) |
| **Session 安全** | Flask Session Cookie + `SECRET_KEY` 签名 |
| **API Key 保护** | 存储于后端 SQLite，前端仅显示脱敏版本 (`sk-a***b`) |
| **文件上传安全** | `secure_filename()` 防路径遍历 + 扩展名白名单 |
| **文件大小限制** | `MAX_CONTENT_LENGTH = 16MB` |
| **CSRF 防护** | Flask Session + SameSite Cookie（默认） |
| **管理员权限** | `@login_required` 装饰器拦截所有 `/admin/*` 路由 |
| **用户简历隔离** | 仅能通过 session 中的 ID 列表访问自己的简历 |

### 安全注意事项

- 当前版本使用 Flask 开发服务器，**不建议直接暴露到公网**
- `SECRET_KEY` 在 `config.py` 中有默认值，**生产环境应通过环境变量覆盖**
- 管理员默认密码 `admin123` 应在首次登录后修改

---

## 9. 关键设计决策

### 9.1 为什么自研 RAG 而非使用 LangChain？

| 维度 | 自研 RAG | LangChain |
|------|----------|-----------|
| 依赖体积 | 零额外依赖 | ~50+ 传递依赖 |
| 启动速度 | 即时 | 需加载多个模块 |
| 中文分词 | 自定义 N-gram，适配无词界语言 | 需配置 jieba 等 |
| 学习成本 | 直接可读的 Python 代码 | 需理解 Chain/Agent 抽象 |
| 灵活性 | 完全可控的检索+生成流程 | 受框架约束 |
| 适用规模 | ✅ 百级政策文档 | 千级以上 + 需向量库 |

**决策**：项目定位为本地小规模部署，政策文档量在 100 以内，自研 RAG 在保持轻量的同时满足需求。

### 9.2 为什么使用 SQLite 而非 MySQL/PostgreSQL？

- **零配置**：无需安装数据库服务，项目文件夹可以直接复制到任何机器运行
- **可移植性**：单文件数据库随项目移动
- **足够的能力**：SQLAlchemy ORM 屏蔽了 SQLite 与生产数据库的差异，未来可无缝切换
- **适合的规模**：单机内网部署，并发量低

### 9.3 为什么前后端不分离？

- **快速交付**：服务端模板渲染 + 原生 JS 是最小可行的技术组合
- **零构建工具**：无需 Webpack/Vite/Node.js 工具链
- **部署简单**：一个 `python app.py` 即可运行全栈
- **渐进增强**：关键交互（聊天、简历上传）使用 AJAX 保持 SPA 体验

### 9.4 简历状态为什么自动切换而非手动？

决策演变过程：
1. 初始设计：HR 手动下拉选择状态（`submitted → viewed → contacted`）
2. 用户反馈：状态应由行为自动决定，不应由 HR 手动修改
3. 简化：去掉 `contacted`，仅保留 `submitted` 和 `viewed`
4. 自动逻辑：HR 查看详情时自动标记 `viewed`；用户编辑简历时自动回退 `submitted`

这确保了状态是一个**可信的信号**（由系统行为产生），而非人为判断。

### 9.5 启动优化策略

| 优化 | 效果 |
|------|------|
| 延迟导入重模块 | 首行输出延迟从 ~800ms 降至 ~0ms |
| 后台导入示例政策 | 服务器无需等待政策导入即可接收请求 |
| 后台轮询浏览器 | 不阻塞 Flask 启动，准备就绪立即打开 |
| 抑制 Werkzeug 日志 | 减少终端噪音，自定义简洁输出 |
| 快速轮询 (120ms 间隔) | 浏览器在服务器就绪后 ~200ms 内打开 |

---

## 10. 扩展点与未来演进

### 10.1 短期优化

| 方向 | 具体措施 | 优先级 |
|------|----------|--------|
| 向量检索升级 | 引入 `sentence-transformers` 做语义向量检索，替换纯 TF-IDF | 中 |
| 流式 SSE 前端 | 当前 `chat.js` 使用 `/chat/send`，升级为 `/chat/stream` SSE | 中 |
| 分页优化 | 政策库/聊天历史支持前端分页加载 | 低 |
| 简历附件预览 | 管理员端 PDF 在线预览（iframe embed） | 低 |

### 10.2 中期演进

| 方向 | 具体措施 | 优先级 |
|------|----------|--------|
| Docker 容器化 | 编写 Dockerfile + docker-compose，一键部署 | 中 |
| 日志系统 | 集成 Python logging → 文件日志 + 按日轮转 | 中 |
| HTTPS 支持 | 使用 `waitress` / `gunicorn` 替代 Flask 开发服务器 | 中 |
| API 限流 | 对聊天接口增加频率限制，防止滥用 | 低 |
| 数据导出 | 简历数据 CSV 导出、政策库版本管理 | 低 |

### 10.3 长期愿景

| 方向 | 描述 |
|------|------|
| Agent 多轮自主推理 | 从单轮 RAG 升级为 ReAct Agent：自主判断检索是否充分、是否需要追问用户 |
| 政策冲突检测 | 当多篇政策文档对同一问题有不同规定时，Agent 主动标注差异 |
| 知识图谱 | 抽取政策中的实体关系（如 "校园招聘 → 要求 → 本科以上学历"），支持结构化查询 |
| 多语言支持 | 英文简历解析、双语政策问答 |

---

> **附录**：本文档应与 [README.md](README.md) 配合阅读。README 面向用户和部署者，本文档面向开发者和架构评审。
