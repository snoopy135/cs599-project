"""
政策库模块 - 政策文档上传、管理、检索
"""
import os
import uuid
from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename
from modules.database import db, Policy
from config import POLICIES_DIR, ALLOWED_POLICY_EXTENSIONS
from modules.auth import login_required

policy_bp = Blueprint('policy', __name__)


def _allowed_file(filename):
    if '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_POLICY_EXTENSIONS


def _extract_text(filepath, ext):
    """提取政策文档文本内容"""
    text = ''
    try:
        if ext in ('txt', 'md'):
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        elif ext == 'pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text += t + '\n'
            except Exception:
                text = ''
        elif ext == 'docx':
            try:
                from docx import Document
                doc = Document(filepath)
                for para in doc.paragraphs:
                    text += para.text + '\n'
            except Exception:
                text = ''
    except Exception:
        text = ''
    return text.strip()


@policy_bp.route('/admin/policies', methods=['GET'])
@login_required
def list_policies():
    """政策库管理页面"""
    policies = Policy.query.order_by(Policy.updated_at.desc()).all()
    categories = db.session.query(Policy.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    return render_template('admin_policies.html',
                           policies=policies,
                           categories=categories)


@policy_bp.route('/admin/policies/upload', methods=['POST'])
@login_required
def upload_policy():
    """上传政策文档"""
    title = request.form.get('title', '').strip()
    category = request.form.get('category', '综合').strip()

    if not title:
        return jsonify({'success': False, 'message': '请输入政策标题'}), 400

    file = request.files.get('policy_file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': '请选择政策文件'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'success': False, 'message': '文件格式不支持'}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(POLICIES_DIR, unique_name)
    file.save(filepath)

    content_text = _extract_text(filepath, ext)
    if not content_text:
        return jsonify({'success': False, 'message': '无法从文件中提取文本内容'}), 400

    policy = Policy(
        title=title,
        category=category,
        file_path=unique_name,
        content_text=content_text
    )
    db.session.add(policy)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'政策「{title}」上传成功',
        'policy': {'id': policy.id, 'title': policy.title, 'category': policy.category}
    })


@policy_bp.route('/admin/policies/<int:policy_id>', methods=['GET'])
@login_required
def get_policy(policy_id):
    """获取单个政策详情"""
    policy = Policy.query.get_or_404(policy_id)
    return jsonify({
        'id': policy.id,
        'title': policy.title,
        'category': policy.category,
        'content_text': policy.content_text[:5000],
        'created_at': policy.created_at.isoformat()
    })


@policy_bp.route('/admin/policies/<int:policy_id>', methods=['PUT'])
@login_required
def update_policy(policy_id):
    """更新政策文本"""
    policy = Policy.query.get_or_404(policy_id)
    data = request.get_json()
    if 'content_text' in data:
        policy.content_text = data['content_text']
    if 'title' in data:
        policy.title = data['title']
    if 'category' in data:
        policy.category = data['category']
    db.session.commit()
    return jsonify({'success': True, 'message': '政策已更新'})


@policy_bp.route('/admin/policies/<int:policy_id>', methods=['DELETE'])
@login_required
def delete_policy(policy_id):
    """删除政策"""
    policy = Policy.query.get_or_404(policy_id)
    # 删除文件
    if policy.file_path:
        file_path = os.path.join(POLICIES_DIR, policy.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
    db.session.delete(policy)
    db.session.commit()
    return jsonify({'success': True, 'message': '政策已删除'})


def _has_chinese(text):
    """检查文本是否包含中文字符"""
    for ch in text:
        if '一' <= ch <= '鿿':
            return True
    return False


def _tokenize(text):
    """
    智能分词: 中文使用字符 n-gram，英文使用空格分词
    """
    tokens = []
    if _has_chinese(text):
        # 中文: 生成 2-gram 和 3-gram
        clean = ''.join(ch for ch in text if '一' <= ch <= '鿿' or ch.isalnum())
        # 单字
        tokens.extend(clean)
        # 2-gram
        for i in range(len(clean) - 1):
            tokens.append(clean[i:i+2])
        # 3-gram
        for i in range(len(clean) - 2):
            tokens.append(clean[i:i+3])
    else:
        # 英文: 空格分词
        tokens = text.lower().split()
    return tokens


def search_policies(query, top_k=5):
    """
    检索相关政策文档 (支持中英文混合搜索)
    使用字符 n-gram 匹配，不依赖外部分词库
    返回 top_k 个最相关的政策片段
    """
    policies = Policy.query.all()
    if not policies:
        return []

    # 对查询进行分词
    query_tokens = _tokenize(query)

    # 去重并过滤过短的 token
    query_terms = [t for t in set(query_tokens) if len(t) >= 1]

    results = []
    for policy in policies:
        content = policy.content_text
        if not content:
            continue

        content_lower = content.lower()
        query_lower = query.lower()

        # 方法1: 子串匹配（最直观的中文匹配方式）
        score = 0
        # 尝试匹配完整查询
        if query_lower in content_lower:
            score += 20
        else:
            # 尝试匹配较长的查询子串
            for sub_len in range(len(query) - 1, 2, -1):
                for i in range(len(query) - sub_len + 1):
                    sub = query[i:i+sub_len]
                    if sub in content:
                        score += sub_len * 2
                        break
                if score > 0:
                    break

        # 方法2: n-gram token 匹配
        for term in query_terms:
            if len(term) >= 2:
                count = content.count(term)
                score += count * len(term)

        if score > 0:
            # 找到最佳匹配位置
            best_idx = 0
            for sub_len in range(min(len(query), 10), 2, -1):
                for i in range(len(query) - sub_len + 1):
                    sub = query[i:i+sub_len]
                    idx = content.find(sub)
                    if idx >= 0:
                        best_idx = idx
                        break
                if best_idx > 0:
                    break

            # 提取相关片段 (约 600 字)
            start = max(0, best_idx - 200)
            end = min(len(content), best_idx + 600)
            snippet = content[start:end]
            if start > 0:
                snippet = '...' + snippet
            if end < len(content):
                snippet = snippet + '...'

            results.append({
                'policy_id': policy.id,
                'title': policy.title,
                'category': policy.category,
                'snippet': snippet,
                'score': score
            })

    # 按分数排序
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:top_k]
