"""
配置文件 - 所有路径均使用相对于项目根目录的路径
"""
import os
import sys

# 项目根目录 (app.py 所在目录)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 数据目录
DATA_DIR = os.path.join(BASE_DIR, 'data')
RESUMES_DIR = os.path.join(DATA_DIR, 'resumes')
POLICIES_DIR = os.path.join(DATA_DIR, 'policies')

# 数据库路径 (Flask-SQLAlchemy 会自动创建 instance 目录)
# 使用相对路径确保可移植性
DATABASE_PATH = os.path.join(BASE_DIR, 'instance', 'app.db')

# 确保必要目录存在
for d in [DATA_DIR, RESUMES_DIR, POLICIES_DIR, os.path.join(BASE_DIR, 'instance')]:
    os.makedirs(d, exist_ok=True)

# Flask 配置
SECRET_KEY = os.environ.get('SECRET_KEY', 'recruitment-qa-assistant-secret-key-2024')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# 上传文件配置
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 最大 16MB
ALLOWED_RESUME_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
ALLOWED_POLICY_EXTENSIONS = {'pdf', 'txt', 'md', 'docx'}

# 默认管理员凭据 (仅首次运行时创建)
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = 'admin123'

# 默认 API 配置
DEFAULT_API_URL = 'https://api.openai.com/v1/chat/completions'
DEFAULT_MODEL_NAME = 'gpt-3.5-turbo'

# RAG 检索配置
TOP_K_RESULTS = 5          # 检索返回的相关政策片段数
MAX_HISTORY_ROUNDS = 10    # 保留最近 N 轮对话
