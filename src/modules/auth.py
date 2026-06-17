"""
认证模块 - 管理员登录/登出
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from modules.database import db, Admin

auth_bp = Blueprint('auth', __name__)


def login_required(f):
    """管理员登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session or not session.get('admin_logged_in'):
            flash('请先登录管理员账号', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def login():
    """管理员登录"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('admin_login.html')

        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            flash('登录成功！', 'success')
            return redirect(url_for('dashboard'))

        flash('用户名或密码错误', 'danger')

    return render_template('admin_login.html')


@auth_bp.route('/admin/logout')
def logout():
    """管理员登出"""
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    flash('已安全退出', 'info')
    return redirect(url_for('auth.login'))


def change_password(username, old_password, new_password):
    """修改管理员密码"""
    admin = Admin.query.filter_by(username=username).first()
    if not admin:
        return False, '用户不存在'
    if not check_password_hash(admin.password_hash, old_password):
        return False, '原密码错误'
    if len(new_password) < 6:
        return False, '新密码长度不能少于6位'
    admin.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return True, '密码修改成功'
