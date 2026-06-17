"""
数据库模块 - 初始化数据库和所有表结构
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Admin(db.Model):
    """管理员表"""
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)


class ApiSettings(db.Model):
    """API 配置表 - 以 key-value 形式存储"""
    __tablename__ = 'api_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, default='')
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class Resume(db.Model):
    """简历表"""
    __tablename__ = 'resumes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), default='')
    phone = db.Column(db.String(50), default='')
    position = db.Column(db.String(200), default='')
    file_path = db.Column(db.String(500), default='')
    content_text = db.Column(db.Text, default='')
    status = db.Column(db.String(30), default='submitted')  # submitted/viewed/contacted
    viewed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    submitted_at = db.Column(db.DateTime, default=datetime.now)


class Policy(db.Model):
    """政策库表"""
    __tablename__ = 'policies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(100), default='综合')
    file_path = db.Column(db.String(500), default='')
    content_text = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class ChatHistory(db.Model):
    """聊天历史表"""
    __tablename__ = 'chat_history'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now)


def init_db(app, import_samples=True):
    """初始化数据库并创建默认管理员"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _migrate_resume_table()
        _create_default_admin()
        _init_default_api_settings()
        if import_samples:
            _import_sample_policies(app)


def _migrate_resume_table():
    """为旧版数据库添加新字段（安全迁移）"""
    import sqlalchemy as sa
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    existing_cols = {c['name'] for c in inspector.get_columns('resumes')}

    with db.engine.connect() as conn:
        if 'status' not in existing_cols:
            conn.execute(text("ALTER TABLE resumes ADD COLUMN status VARCHAR(30) DEFAULT 'submitted'"))
        if 'viewed_at' not in existing_cols:
            conn.execute(text('ALTER TABLE resumes ADD COLUMN viewed_at DATETIME'))
        if 'updated_at' not in existing_cols:
            conn.execute(text('ALTER TABLE resumes ADD COLUMN updated_at DATETIME'))
        conn.commit()


def _create_default_admin():
    """创建默认管理员（如不存在）"""
    from werkzeug.security import generate_password_hash
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(
            username='admin',
            password_hash=generate_password_hash('admin123')
        )
        db.session.add(admin)
        db.session.commit()


def _init_default_api_settings():
    """初始化默认 API 配置（如不存在）"""
    defaults = {
        'api_url': 'https://api.openai.com/v1/chat/completions',
        'api_key': '',
        'model_name': 'gpt-3.5-turbo',
        'system_prompt': '',
        'temperature': '0.7',
        'max_tokens': '2000',
    }
    for key, value in defaults.items():
        if not ApiSettings.query.filter_by(key=key).first():
            setting = ApiSettings(key=key, value=value)
            db.session.add(setting)
    db.session.commit()


def _import_sample_policies(app):
    """如果政策库为空，自动导入示例政策文档"""
    if Policy.query.count() > 0:
        return

    import os
    # 相对于项目根目录
    policies_dir = os.path.join(app.config.get('BASE_DIR', os.path.dirname(os.path.dirname(__file__))),
                                'data', 'policies')
    if not os.path.exists(policies_dir):
        return

    files = os.listdir(policies_dir)
    for filename in files:
        filepath = os.path.join(policies_dir, filename)
        if not os.path.isfile(filepath):
            continue

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext not in ('txt', 'md', 'pdf', 'docx'):
            continue

        # 提取文件名作为标题
        title = os.path.splitext(filename)[0]
        # 处理下划线命名
        title = title.replace('_', ' ').replace('-', ' ').title()

        content_text = ''
        try:
            if ext in ('txt', 'md'):
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content_text = f.read()
            elif ext == 'pdf':
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(filepath)
                    for page in reader.pages:
                        t = page.extract_text()
                        if t:
                            content_text += t + '\n'
                except Exception:
                    continue
            elif ext == 'docx':
                try:
                    from docx import Document
                    doc = Document(filepath)
                    for para in doc.paragraphs:
                        content_text += para.text + '\n'
                except Exception:
                    continue
        except Exception:
            continue

        if not content_text.strip():
            continue

        # 尝试从内容中提取分类
        category = '综合'
        content_lower = content_text.lower()
        if '校园' in content_text:
            category = '校园招聘'
        elif '社会招聘' in content_text or '社招' in content_text:
            category = '社会招聘'
        elif '实习' in content_text:
            category = '实习生'
        elif '推荐' in content_text:
            category = '内部推荐'
        elif '面试' in content_text or '录用' in content_text:
            category = '面试录用'
        elif '入职' in content_text:
            category = '入职管理'
        elif '薪资' in content_text or '福利' in content_text or '工资' in content_text:
            category = '薪资福利'

        policy = Policy(
            title=title,
            category=category,
            file_path=filename,
            content_text=content_text.strip()
        )
        db.session.add(policy)

    db.session.commit()
