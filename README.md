# 招聘政策智能问答助手

## 项目简介

面向企业招聘场景的智能问答系统 —— 求职者可通过网页投递简历并实时追踪 HR 查看状态，AI 助手基于内部招聘政策库（RAG）提供精准的政策咨询问答。管理员可通过后台管理简历、维护政策库，并灵活配置多种大模型 API。项目支持本地一键部署，开箱即用。

## 方向

方向二：企业级应用软件的 Agent 改造

## 技术栈

| 层面 | 技术 | 说明 |
|------|------|------|
| AI IDE | VS Code / Trae CN | 开发环境 |
| LLM | DeepSeek / OpenAI / Zhipu / Moonshot / Qwen / Baichuan / SiliconFlow / Ollama | 支持 8+ 国内外大模型 API |
| 后端框架 | Python Flask 3.1 | Blueprint 模块化架构 |
| 数据库 | SQLite + Flask-SQLAlchemy | 单文件数据库，便于随项目移动 |
| 前端 | HTML5 + Bootstrap 5 + 原生 JavaScript | 响应式 UI，无构建工具依赖 |
| RAG 引擎 | 自研 TF-IDF + 中文 N-gram 分词 | 轻量级，无需外部向量数据库 |
| AI Agent | 自建 RAG Agent（检索 + LLM 合成 + 降级） | 支持流式 SSE 响应 |
| 认证 | Flask Session + Werkzeug 密码哈希 | 管理员密码登录保护 |

## 目录结构

```
src/
├── app.py                          # Flask 主应用入口，延迟导入优化启动
├── config.py                       # 全局配置（路径、密钥、RAG 参数）
├── requirements.txt                # Python 依赖清单
├── run.bat / run.sh                # Windows / Linux 一键启动脚本
├── run.ps1                         # PowerShell 启动脚本
├── instance/                       # 自动生成
│   └── app.db                      # SQLite 数据库文件
├── data/
│   ├── resumes/                    # 用户上传的简历文件
│   └── policies/                   # 招聘政策文档库（.txt / .md / .pdf / .docx）
├── static/
│   ├── css/
│   │   └── style.css               # 全局自定义样式（CSS 变量主题）
│   └── js/
│       ├── chat.js                 # AI 聊天界面 SSE 流式交互
│       └── resume-popup.js         # 10 秒自动弹窗简历投递
├── templates/
│   ├── base.html                   # 母版布局（导航栏 + 响应式）
│   ├── index.html                  # 首页（功能入口 + 简历投递）
│   ├── chat.html                   # AI 问答聊天页面（流式对话）
│   ├── my_resumes.html             # 用户端：我的简历列表（状态追踪 + 编辑）
│   ├── my_resume_detail.html       # 用户端：简历详情（两步进度条）
│   ├── admin_login.html            # 管理员登录
│   ├── admin_dashboard.html        # 管理后台仪表盘
│   ├── admin_api.html              # AI 模型 API 配置（8+ 预设）
│   ├── admin_resumes.html          # 管理员简历列表（搜索 + 分页）
│   ├── admin_resume_detail.html    # 管理员简历详情（自动标记已查看）
│   ├── admin_policies.html         # 政策库管理（上传 / 编辑 / 删除）
│   ├── resume_modal.html           # 简历投递模态框组件
│   └── resume_toast.html           # 简历投递 Toast 提示组件
├── modules/
│   ├── __init__.py
│   ├── database.py                 # 数据库模型定义 + 初始化 + 迁移
│   ├── auth.py                     # 管理员认证（登录 / 登出 / 装饰器）
│   ├── resume.py                   # 简历上传、文本提取、用户追踪
│   ├── policy.py                   # 政策库管理 + TF-IDF 检索引擎
│   ├── agent.py                    # AI Agent：RAG 检索 + LLM 合成 + SSE 流式
│   └── api_config.py               # API 配置读写 + 连接测试
└── prompts/
    └── system_prompt.txt           # 默认系统提示词（Agent 人格定义）
```

## 环境搭建

### 1. 依赖安装

```bash
# 要求 Python 3.9+
pip install -r requirements.txt
```

依赖列表：

| 包名 | 用途 |
|------|------|
| Flask 3.1 | Web 框架 |
| Flask-Login | 会话管理 |
| Flask-SQLAlchemy | ORM 数据库操作 |
| PyPDF2 | PDF 简历 / 政策文档解析 |
| python-docx | Word 文档解析 |
| requests | 外部 API 调用 |
| python-dotenv | 环境变量加载 |

### 2. 环境变量配置

> API Key 等敏感信息通过网页后台配置，不硬编码在代码中。 首次启动后，使用管理员账号登录并设置对应API，在「API 配置」页面设置 API URL 和 Key。

### 3. 启动步骤

**方式一：一键启动**

```bash
# Windows
run.bat

# Linux / Mac
chmod +x run.sh && ./run.sh
```

**方式二：手动启动**

```bash
pip install -r requirements.txt
python app.py
```

启动后在终端看到如下输出即成功：

```
  ◈ 招聘政策智能问答助手
  加载中...
  ✓ 应用初始化完成 (XXms)
  … 后台导入示例政策
  … 等待服务器就绪
  ✓ 浏览器已打开
```

浏览器自动打开后：
- 普通用户：访问 `http://localhost:5000` 投递简历、咨询 AI 助手
- 管理员：访问 `http://localhost:5000/admin/login`，默认账号 `admin` / `admin123`

### 4. 配置 AI 模型

管理员登录后进入「API 配置」页面，支持预设一键填充：

| 预设分类 | 可选模型 |
|----------|----------|
| 🌍 国际 | OpenAI GPT-4o / GPT-3.5 |
| 🇨🇳 中国 | DeepSeek / Zhipu GLM-4 / Moonshot Kimi / Qwen DashScope / Baichuan / SiliconFlow |
| 💻 本地 | Ollama LLaMA3 / Qwen2.5 |

系统会根据 API URL 自动检测提供商类型，适配不同的认证方式、请求格式和响应路径。保存前请检测模型是否可用。

## 项目状态

- [x] Proposal — 需求分析与技术方案
- [x] MVP — 核心功能完整实现（简历投递、AI 问答、政策库管理、多模型 API）
- [x] Enhancement — 简历追踪、中国模型支持、启动优化、自动状态管理
- [ ] Final — 性能优化与生产部署（Docker 化、HTTPS、日志系统）
