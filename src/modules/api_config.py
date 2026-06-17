"""
API 配置模块 - 管理员修改 AI 模型调用 API
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from modules.database import db, ApiSettings
from modules.auth import login_required

api_config_bp = Blueprint('api_config', __name__)


@api_config_bp.route('/admin/api', methods=['GET'])
@login_required
def api_settings_page():
    """API 配置页面"""
    settings = {}
    for s in ApiSettings.query.all():
        settings[s.key] = s.value

    # 脱敏显示 API Key
    api_key = settings.get('api_key', '')
    if api_key and len(api_key) > 8:
        settings['api_key_display'] = api_key[:4] + '*' * (len(api_key) - 8) + api_key[-4:]
    else:
        settings['api_key_display'] = api_key

    return render_template('admin_api.html', settings=settings)


@api_config_bp.route('/admin/api', methods=['POST'])
@login_required
def save_api_settings():
    """保存 API 配置"""
    allowed_keys = {'api_url', 'api_key', 'model_name', 'system_prompt', 'temperature', 'max_tokens'}

    for key in allowed_keys:
        value = request.form.get(key, '').strip()
        if key == 'api_key' and value and '***' in value:
            # 用户未修改加密字段，跳过
            continue
        setting = ApiSettings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = ApiSettings(key=key, value=value)
            db.session.add(setting)

    db.session.commit()
    flash('API 配置已保存', 'success')
    return redirect(url_for('api_config.api_settings_page'))


@api_config_bp.route('/admin/api/test', methods=['POST'])
@login_required
def test_api_connection():
    """测试 API 连接（支持 OpenAI 及国内模型兼容接口）"""
    import requests

    data = request.get_json()
    api_url = data.get('api_url', '')
    api_key = data.get('api_key', '')
    model_name = data.get('model_name', 'gpt-3.5-turbo')

    if not api_url:
        return jsonify({'success': False, 'message': '请填写 API URL'})
    if not api_key:
        return jsonify({'success': False, 'message': '请填写 API Key'})

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    # 根据 API 类型调整 payload
    payload = {
        'model': model_name,
        'messages': [{'role': 'user', 'content': '你好，请用中文回复"连接测试成功"'}],
        'max_tokens': 50,
    }

    # MiniMax 特殊处理
    if 'minimax.chat' in api_url.lower():
        payload.pop('max_tokens', None)
        payload['tokens_to_generate'] = 50

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            # 尝试多种可能的响应路径
            reply = ''
            try:
                reply = data['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                try:
                    reply = data['choices'][0]['text']
                except (KeyError, IndexError, TypeError):
                    try:
                        reply = data['choices'][0]['messages'][0]['text']
                    except (KeyError, IndexError, TypeError):
                        reply = str(data)[:200]

            # 检查常见的国内 API 错误码
            if 'error' in data:
                err = data['error']
                err_msg = err.get('message', str(err)) if isinstance(err, dict) else str(err)
                return jsonify({
                    'success': False,
                    'message': f'API 返回错误: {err_msg}'
                })

            return jsonify({
                'success': True,
                'message': f'连接成功！模型回复: {reply[:120]}'
            })
        else:
            detail = ''
            try:
                err_data = resp.json()
                if 'error' in err_data:
                    if isinstance(err_data['error'], dict):
                        detail = err_data['error'].get('message', str(err_data['error']))
                    else:
                        detail = str(err_data['error'])
                else:
                    detail = str(err_data)
            except Exception:
                detail = resp.text[:300]
            return jsonify({
                'success': False,
                'message': f'HTTP {resp.status_code}: {detail}'
            })
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': f'无法连接到服务器，请检查 API URL 和网络\n({api_url})'})
    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'message': '连接超时（30秒），请检查网络或 API 地址是否正确'})
    except requests.exceptions.SSLError:
        return jsonify({'success': False, 'message': f'SSL 证书验证失败，请确认 API 地址是否正确\n({api_url})'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'测试失败: {str(e)}'})
