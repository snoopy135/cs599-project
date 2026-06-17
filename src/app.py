"""
招聘政策智能问答助手 - 主应用入口
"""
import os
import sys

# 确保项目根目录在 Python 路径中
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)


def create_app():
    """创建 Flask 应用（延迟导入以加速启动反馈）"""
    from flask import Flask, render_template, session, jsonify, request
    from modules.database import init_db, db, Resume
    from modules.auth import auth_bp, login_required
    from modules.resume import resume_bp
    from modules.policy import policy_bp
    from modules.agent import agent_bp
    from modules.api_config import api_config_bp
    import config

    app = Flask(__name__,
                instance_path=os.path.join(BASE_DIR, 'instance'),
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))

    # 加载配置
    app.config.from_object(config)
    app.config['BASE_DIR'] = BASE_DIR

    # 确保目录存在
    config_dirs = [config.DATA_DIR, config.RESUMES_DIR, config.POLICIES_DIR,
                   os.path.join(BASE_DIR, 'instance')]
    for d in config_dirs:
        os.makedirs(d, exist_ok=True)

    # 初始化数据库
    init_db(app)

    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(policy_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(api_config_bp)

    # ========== 通用路由 ==========

    @app.route('/favicon.ico')
    def favicon():
        """忽略浏览器自动请求的 favicon"""
        return '', 204

    @app.route('/admin/default-prompt')
    @login_required
    def default_prompt():
        """返回系统默认提示词文本"""
        prompt_file = os.path.join(BASE_DIR, 'prompts', 'system_prompt.txt')
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                raw = f.read()
            # 去掉 # 注释行，清理空行
            lines = []
            for line in raw.split('\n'):
                stripped = line.strip()
                if stripped.startswith('# '):
                    lines.append(stripped[2:])  # 保留标题文本，去掉 #
                elif stripped.startswith('#'):
                    lines.append(stripped[1:])
                else:
                    lines.append(line.rstrip())
            return '\n'.join(lines)
        except Exception:
            return '（默认提示词文件不存在）', 404

    # ========== 用户端路由 ==========

    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')

    @app.route('/chat')
    def chat():
        """AI 问答聊天页面"""
        return render_template('chat.html')

    # ========== 管理员端路由 ==========

    @app.route('/admin/dashboard')
    @login_required
    def dashboard():
        """管理员仪表盘"""
        from modules.database import Policy, ChatHistory
        resume_count = Resume.query.count()
        policy_count = Policy.query.count()
        chat_count = ChatHistory.query.count()
        recent_resumes = Resume.query.order_by(Resume.submitted_at.desc()).limit(5).all()
        return render_template('admin_dashboard.html',
                               resume_count=resume_count,
                               policy_count=policy_count,
                               chat_count=chat_count,
                               recent_resumes=recent_resumes)

    @app.route('/admin/resumes')
    @login_required
    def admin_resumes():
        """管理员查看简历列表"""
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '').strip()
        per_page = 20

        query = Resume.query
        if search:
            query = query.filter(
                db.or_(
                    Resume.name.contains(search),
                    Resume.email.contains(search),
                    Resume.position.contains(search)
                )
            )

        pagination = query.order_by(Resume.submitted_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        resumes = pagination.items
        return render_template('admin_resumes.html',
                               resumes=resumes,
                               pagination=pagination,
                               search=search)

    @app.route('/admin/resumes/<int:resume_id>')
    @login_required
    def admin_resume_detail(resume_id):
        """简历详情（管理员查看时自动标记为已查看）"""
        from datetime import datetime
        resume = Resume.query.get_or_404(resume_id)
        # 自动标记 HR 已查看
        if resume.status == 'submitted':
            resume.status = 'viewed'
            resume.viewed_at = datetime.now()
            db.session.commit()
        return render_template('admin_resume_detail.html', resume=resume)

    @app.route('/admin/resumes/<int:resume_id>/download')
    @login_required
    def download_resume(resume_id):
        """下载简历文件"""
        from flask import send_file
        resume = Resume.query.get_or_404(resume_id)
        if resume.file_path:
            filepath = os.path.join(config.RESUMES_DIR, resume.file_path)
            if os.path.exists(filepath):
                return send_file(filepath, as_attachment=True,
                                 download_name=f'{resume.name}_简历{os.path.splitext(resume.file_path)[1]}')
        return '文件不存在', 404

    @app.route('/admin/change-password', methods=['POST'])
    @login_required
    def change_password():
        """修改管理员密码"""
        from modules.auth import change_password as cp
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')
        if new_pw != confirm_pw:
            return jsonify({'success': False, 'message': '两次输入的新密码不一致'})
        success, message = cp(session.get('admin_username', 'admin'), old_pw, new_pw)
        return jsonify({'success': success, 'message': message})

    return app


if __name__ == '__main__':
    import threading
    import time
    import urllib.request
    import webbrowser as _wb
    import logging

    # 启用 Windows 终端 ANSI 颜色支持
    if sys.platform == 'win32':
        os.system('')

    # 抑制 Werkzeug 的启动横幅，使用我们自己的输出
    logging.getLogger('werkzeug').setLevel(logging.WARNING)

    # ── 立即反馈 ──
    print('\n  \033[1;35m◈\033[0m 招聘政策智能问答助手', flush=True)
    print('  \033[90m加载中...\033[0m', flush=True)

    # ── 初始化应用 ──
    t0 = time.time()
    try:
        app = create_app()
    except Exception as e:
        print(f'\n  \033[31m✗ 启动失败\033[0m: {e}')
        import traceback
        traceback.print_exc()
        input('\nPress Enter to exit...')
        sys.exit(1)

    init_ms = (time.time() - t0) * 1000
    print(f'  \033[32m✓\033[0m 应用初始化完成 \033[90m({init_ms:.0f}ms)\033[0m', flush=True)

    # ── 后台导入示例政策（不阻塞启动）──
    def _deferred_import_samples():
        try:
            with app.app_context():
                from modules.database import _import_sample_policies
                _import_sample_policies(app)
        except Exception:
            pass  # 静默失败，政策库由管理员手动管理

    threading.Thread(target=_deferred_import_samples, daemon=True).start()
    print('  \033[90m…\033[0m 后台导入示例政策', flush=True)

    # ── 浏览器自动打开 ──
    browser_opened = [False]

    def _try_open_browser():
        # 快速轮询：每 0.12s 检查一次
        for _ in range(60):
            time.sleep(0.12)
            try:
                urllib.request.urlopen('http://127.0.0.1:5000', timeout=0.5)
                _wb.open('http://localhost:5000')
                browser_opened[0] = True
                return
            except Exception:
                pass

    threading.Thread(target=_try_open_browser, daemon=True).start()
    print('  \033[90m…\033[0m 等待服务器就绪', flush=True)

    # ── 启动 ──
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print('\n\033[90m服务器已停止。\033[0m')
    except Exception as e:
        print(f'\n\033[31m✗ 运行错误\033[0m: {e}')
        input('\nPress Enter to exit...')

    # ── 启动完成提示（由 _try_open_browser 输出）──
    if browser_opened[0]:
        print('  \033[32m✓\033[0m 浏览器已打开', flush=True)
    else:
        print(f'\n\033[1m  准备就绪！\033[0m')
        print(f'  \033[36m→\033[0m http://localhost:5000')
        print(f'  \033[36m→\033[0m 管理员: admin / admin123')
        print()
