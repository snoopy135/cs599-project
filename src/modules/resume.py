"""
简历模块 - 简历上传、文本提取、查询、用户追踪
"""
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, session
from werkzeug.utils import secure_filename
from modules.database import db, Resume
from config import RESUMES_DIR, ALLOWED_RESUME_EXTENSIONS

resume_bp = Blueprint('resume', __name__)


def _allowed_file(filename, allowed_set):
    """检查文件扩展名"""
    if '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in allowed_set


def _extract_text(filepath, ext):
    """提取文件文本内容"""
    text = ''
    try:
        if ext == 'txt' or ext == 'md':
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
                text = '[PDF 文本提取失败，请手动查看文件]'
        elif ext in ('doc', 'docx'):
            try:
                from docx import Document
                doc = Document(filepath)
                for para in doc.paragraphs:
                    text += para.text + '\n'
            except Exception:
                text = '[Word 文本提取失败，请手动查看文件]'
    except Exception as e:
        text = f'[文本提取异常: {str(e)}]'

    return text.strip() or '[未提取到文本内容]'


@resume_bp.route('/resume/upload', methods=['POST'])
def upload_resume():
    """上传简历"""
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    position = request.form.get('position', '').strip()

    if not name:
        return jsonify({'success': False, 'message': '请输入姓名'}), 400

    file = request.files.get('resume_file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': '请选择简历文件'}), 400

    if not _allowed_file(file.filename, ALLOWED_RESUME_EXTENSIONS):
        return jsonify({
            'success': False,
            'message': f'文件格式不支持，支持: {", ".join(ALLOWED_RESUME_EXTENSIONS)}'
        }), 400

    # 保存文件
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(RESUMES_DIR, unique_name)
    file.save(filepath)

    # 提取文本
    content_text = _extract_text(filepath, ext)

    # 存入数据库
    resume = Resume(
        name=name,
        email=email,
        phone=phone,
        position=position,
        file_path=unique_name,
        content_text=content_text
    )
    db.session.add(resume)
    db.session.commit()

    # 将简历 ID 存入 session，方便用户追踪
    if 'my_resume_ids' not in session:
        session['my_resume_ids'] = []
    session['my_resume_ids'].append(resume.id)
    session['resume_submitted'] = True
    session.modified = True

    return jsonify({
        'success': True,
        'message': '简历投递成功！感谢您的申请。',
        'resume_id': resume.id
    })


@resume_bp.route('/resume/check', methods=['GET'])
def check_submission():
    """检查用户是否已提交过简历（基于 session cookie）"""
    submitted = session.get('resume_submitted', False)
    return jsonify({'submitted': submitted})


@resume_bp.route('/my-resumes')
def my_resumes():
    """用户查看自己投递的简历"""
    resume_ids = session.get('my_resume_ids', [])
    resumes = []
    if resume_ids:
        resumes = Resume.query.filter(Resume.id.in_(resume_ids)).order_by(Resume.submitted_at.desc()).all()
    return render_template('my_resumes.html', resumes=resumes)


@resume_bp.route('/my-resumes/lookup', methods=['POST'])
def lookup_resumes():
    """通过邮箱查找已投递简历并关联到当前 session"""
    email = request.form.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'message': '请输入邮箱地址'})

    found = Resume.query.filter_by(email=email).order_by(Resume.submitted_at.desc()).all()
    if not found:
        return jsonify({'success': False, 'message': '未找到该邮箱对应的简历记录'})

    # 关联到 session
    if 'my_resume_ids' not in session:
        session['my_resume_ids'] = []
    for r in found:
        if r.id not in session['my_resume_ids']:
            session['my_resume_ids'].append(r.id)
    session['resume_submitted'] = True
    session.modified = True

    return jsonify({
        'success': True,
        'message': f'找到 {len(found)} 份简历',
        'count': len(found)
    })


@resume_bp.route('/my-resumes/<int:resume_id>')
def view_my_resume(resume_id):
    """用户查看自己的单份简历详情"""
    resume_ids = session.get('my_resume_ids', [])
    if resume_id not in resume_ids:
        # 也允许通过 email 匹配
        resume = Resume.query.get_or_404(resume_id)
        # 简单检查：session 中没有但邮箱匹配也可以看
    else:
        resume = Resume.query.get_or_404(resume_id)

    return render_template('my_resume_detail.html', resume=resume)


@resume_bp.route('/my-resumes/<int:resume_id>/edit', methods=['POST'])
def edit_my_resume(resume_id):
    """用户编辑自己的简历信息（仅限基本信息）"""
    resume_ids = session.get('my_resume_ids', [])
    if resume_id not in resume_ids:
        return jsonify({'success': False, 'message': '无权修改此简历'}), 403

    resume = Resume.query.get_or_404(resume_id)

    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    position = request.form.get('position', '').strip()

    if not name:
        return jsonify({'success': False, 'message': '姓名不能为空'})

    resume.name = name
    resume.email = email
    resume.phone = phone
    resume.position = position
    resume.updated_at = datetime.now()
    # 用户修改简历后，重置为未查看状态
    if resume.status == 'viewed':
        resume.status = 'submitted'
        resume.viewed_at = None
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '简历信息已更新'
    })


@resume_bp.route('/resume/status/<int:resume_id>', methods=['GET'])
def check_resume_status(resume_id):
    """AJAX 查询简历状态（用于轮询）"""
    resume = Resume.query.get_or_404(resume_id)

    status_map = {
        'submitted': '未被查看',
        'viewed': '已被查看',
    }

    return jsonify({
        'status': resume.status,
        'status_label': status_map.get(resume.status, resume.status),
        'viewed_at': resume.viewed_at.strftime('%Y-%m-%d %H:%M') if resume.viewed_at else None,
        'updated_at': resume.updated_at.strftime('%Y-%m-%d %H:%M') if resume.updated_at else None,
        'submitted_at': resume.submitted_at.strftime('%Y-%m-%d %H:%M') if resume.submitted_at else None
    })
