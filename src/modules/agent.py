"""
AI Agent 模块 - RAG 检索增强生成
1. 检索阶段: TF-IDF/关键词匹配检索相关政策文档
2. 生成阶段: 调用配置的 LLM API 合成回答
3. 降级策略: API 不可用时返回纯检索结果
"""
import os
import json
import uuid
import requests
from flask import Blueprint, request, jsonify, Response, session, stream_with_context
from modules.database import db, ApiSettings, ChatHistory
from modules.policy import search_policies
from config import MAX_HISTORY_ROUNDS

agent_bp = Blueprint('agent', __name__)


def _get_api_settings():
    """获取当前 API 配置"""
    settings = {}
    for s in ApiSettings.query.all():
        settings[s.key] = s.value
    return settings


def _get_system_prompt():
    """获取系统提示词"""
    # 优先使用数据库中的自定义提示词
    settings = _get_api_settings()
    custom_prompt = settings.get('system_prompt', '')
    if custom_prompt and custom_prompt.strip():
        return custom_prompt.strip()

    # 使用默认提示词文件
    prompt_file = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'prompts', 'system_prompt.txt')
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return '你是一个专业的企业招聘政策问答助手。请基于政策库内容回答问题。'


def _get_or_create_session_id():
    """获取或创建会话 ID"""
    if 'chat_session_id' not in session:
        session['chat_session_id'] = uuid.uuid4().hex
    return session['chat_session_id']


def _get_recent_history(session_id, rounds=MAX_HISTORY_ROUNDS):
    """获取最近 N 轮对话历史"""
    messages = ChatHistory.query \
        .filter_by(session_id=session_id) \
        .order_by(ChatHistory.created_at.desc()) \
        .limit(rounds * 2) \
        .all()
    messages.reverse()
    return [{'role': m.role, 'content': m.content} for m in messages]


def _save_message(session_id, role, content):
    """保存聊天消息"""
    msg = ChatHistory(session_id=session_id, role=role, content=content)
    db.session.add(msg)
    db.session.commit()


def _build_context_prompt(query, top_k=5):
    """检索相关政策并构建上下文 prompt"""
    results = search_policies(query, top_k=top_k)

    if not results:
        return None, []

    context_parts = []
    for i, r in enumerate(results, 1):
        context_parts.append(
            f"【政策文档{i}】标题：{r['title']} | 分类：{r['category']}\n{r['snippet']}"
        )

    context_text = '\n\n---\n\n'.join(context_parts)
    return context_text, results


def _detect_api_type(api_url):
    """根据 API URL 检测 API 类型，返回特殊配置"""
    api_url_lower = api_url.lower()
    config = {
        'supports_stream': True,
        'supports_max_tokens': True,
        'use_json_content_type': True,
        'extra_headers': {},
        'extra_payload': {},
        'response_path': ('choices', 0, 'message', 'content'),  # 标准 OpenAI 路径
    }

    if 'ollama' in api_url_lower:
        config['supports_stream'] = True
        config['extra_payload']['stream'] = False
    elif 'deepseek.com' in api_url_lower:
        # DeepSeek 完全兼容 OpenAI 格式
        pass
    elif 'bigmodel.cn' in api_url_lower:
        # 智谱 GLM — OpenAI 兼容
        pass
    elif 'moonshot.cn' in api_url_lower:
        # 月之暗面 Kimi — OpenAI 兼容
        pass
    elif 'dashscope.aliyuncs.com' in api_url_lower:
        # 阿里通义千问 — OpenAI 兼容模式
        pass
    elif 'baichuan-ai.com' in api_url_lower:
        # 百川智能 — OpenAI 兼容
        pass
    elif 'volces.com' in api_url_lower or 'volcengine.com' in api_url_lower:
        # 字节豆包 — OpenAI 兼容
        pass
    elif 'siliconflow.cn' in api_url_lower:
        # SiliconFlow (硅基流动) — OpenAI 兼容
        pass
    elif 'minimax.chat' in api_url_lower:
        # MiniMax — 使用不同格式
        config['supports_stream'] = False
        config['use_json_content_type'] = True
        config['response_path'] = ('choices', 0, 'messages', 0, 'text')

    return config


def _call_llm_api(system_prompt, context, query, history):
    """调用 LLM API 生成回答（支持 OpenAI 及国内模型兼容接口）"""
    settings = _get_api_settings()
    api_url = settings.get('api_url', 'https://api.openai.com/v1/chat/completions')
    api_key = settings.get('api_key', '')
    model_name = settings.get('model_name', 'gpt-3.5-turbo')
    temperature = float(settings.get('temperature', '0.7'))
    max_tokens = int(settings.get('max_tokens', '2000'))

    if not api_key:
        return None, 'API Key 未配置，请管理员在后台设置。以下为检索到的相关政策原文：\n\n'

    # 检测 API 类型
    api_config = _detect_api_type(api_url)

    # 构建消息
    messages = [{'role': 'system', 'content': system_prompt}]

    # 加入历史对话
    for h in history[-MAX_HISTORY_ROUNDS * 2:]:
        messages.append({'role': h['role'], 'content': h['content']})

    # 构建用户消息
    if context:
        user_message = (
            f"请参考以下招聘政策文档内容回答用户问题。\n\n"
            f"=== 相关政策文档 ===\n{context}\n=== 政策文档结束 ===\n\n"
            f"用户问题：{query}\n\n"
            f"请基于以上政策内容给出专业回答。如果政策内容不足以回答该问题，请如实告知。"
        )
    else:
        user_message = (
            f"用户问题：{query}\n\n"
            f"注意：当前政策库中未检索到相关内容，请告知用户'当前政策库中暂无相关信息，建议联系HR部门获取最新政策'。"
        )

    messages.append({'role': 'user', 'content': user_message})

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    # 添加特定 API 所需的额外请求头
    headers.update(api_config['extra_headers'])

    payload = {
        'model': model_name,
        'messages': messages,
        'temperature': temperature,
    }

    # 处理 max_tokens — 某些 API 使用 max_completion_tokens
    if api_config['supports_max_tokens']:
        payload['max_tokens'] = max_tokens
    else:
        payload['max_completion_tokens'] = max_tokens

    # 添加特定 API 的额外参数
    payload.update(api_config['extra_payload'])

    try:
        resp = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            # 按检测到的路径提取回复内容
            try:
                answer = data
                for key in api_config['response_path']:
                    if isinstance(key, int):
                        answer = answer[key]
                    else:
                        answer = answer.get(key, '')
                return answer, None
            except (KeyError, IndexError, TypeError):
                # 回退到标准路径
                try:
                    answer = data['choices'][0]['message']['content']
                    return answer, None
                except Exception:
                    return None, f'API 返回格式异常: {json.dumps(data, ensure_ascii=False)[:300]}'
        else:
            error_msg = f'API 调用失败 (HTTP {resp.status_code})'
            try:
                error_detail = resp.json()
                # 提取常见错误信息字段
                if 'error' in error_detail:
                    if isinstance(error_detail['error'], dict):
                        error_msg += f': {error_detail["error"].get("message", error_detail["error"])}'
                    else:
                        error_msg += f': {error_detail["error"]}'
                else:
                    error_msg += f': {error_detail}'
            except Exception:
                error_msg += f': {resp.text[:300]}'
            return None, error_msg
    except requests.exceptions.Timeout:
        return None, 'API 请求超时（120秒），请检查网络或增加超时时间'
    except requests.exceptions.ConnectionError:
        return None, f'无法连接到 API 服务器 ({api_url})，请检查 API 地址和网络连接'
    except requests.exceptions.SSLError:
        return None, f'SSL 证书验证失败 ({api_url})，请检查 API 地址是否正确'
    except Exception as e:
        return None, f'API 调用异常: {str(e)}'


@agent_bp.route('/chat/send', methods=['POST'])
def send_message():
    """处理用户消息并返回 AI 回答"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请提供消息内容'}), 400

    query = data.get('message', '').strip()
    if not query:
        return jsonify({'success': False, 'message': '消息不能为空'}), 400

    session_id = _get_or_create_session_id()

    # 保存用户消息
    _save_message(session_id, 'user', query)

    # 1. 检索阶段
    context, sources = _build_context_prompt(query)

    # 2. 获取历史
    history = _get_recent_history(session_id)

    # 3. 生成阶段
    system_prompt = _get_system_prompt()
    answer, error = _call_llm_api(system_prompt, context, query, history)

    # 4. 降级策略
    fallback_mode = False
    if error:
        fallback_mode = True
        if context:
            # 降级: 返回检索到的政策原文 + 错误信息
            answer = (
                f"⚠️ **注意：AI 模型暂时不可用（{error}）**\n\n"
                f"以下是从政策库中检索到的相关内容，供您参考：\n\n"
                f"{context}"
            )
        else:
            answer = (
                f"⚠️ AI 模型暂时不可用（{error}），且政策库中暂无相关内容。\n"
                f"建议您联系HR部门获取帮助。"
            )

    # 5. 保存 AI 回答
    _save_message(session_id, 'assistant', answer)

    # 6. 构建来源引用
    source_list = []
    if sources:
        source_list = [{'title': s['title'], 'category': s['category']} for s in sources]

    return jsonify({
        'success': True,
        'answer': answer,
        'sources': source_list,
        'fallback_mode': fallback_mode
    })


@agent_bp.route('/chat/history', methods=['GET'])
def get_history():
    """获取当前会话的聊天历史"""
    session_id = _get_or_create_session_id()
    messages = ChatHistory.query \
        .filter_by(session_id=session_id) \
        .order_by(ChatHistory.created_at.asc()) \
        .all()
    return jsonify({
        'messages': [{'role': m.role, 'content': m.content} for m in messages]
    })


@agent_bp.route('/chat/clear', methods=['POST'])
def clear_history():
    """清除当前会话聊天历史"""
    session_id = session.get('chat_session_id', '')
    if session_id:
        ChatHistory.query.filter_by(session_id=session_id).delete()
        db.session.commit()
    session.pop('chat_session_id', None)
    return jsonify({'success': True, 'message': '对话历史已清除'})


@agent_bp.route('/chat/stream', methods=['POST'])
def stream_message():
    """流式返回 AI 回答 (SSE)"""
    data = request.get_json()
    query = data.get('message', '').strip()
    if not query:
        return jsonify({'success': False}), 400

    session_id = _get_or_create_session_id()
    _save_message(session_id, 'user', query)

    context, sources = _build_context_prompt(query)
    history = _get_recent_history(session_id)
    system_prompt = _get_system_prompt()
    settings = _get_api_settings()

    def generate():
        api_key = settings.get('api_key', '')
        if not api_key:
            # 降级模式
            fallback_answer = ''
            if context:
                fallback_answer = f"⚠️ API Key 未配置。以下为政策库检索结果：\n\n{context}"
            else:
                fallback_answer = '⚠️ API Key 未配置，且政策库中暂无相关内容。'
            _save_message(session_id, 'assistant', fallback_answer)
            yield f"data: {json.dumps({'content': fallback_answer, 'done': True}, ensure_ascii=False)}\n\n"
            return

        # 构建请求
        api_url = settings.get('api_url', '')
        model_name = settings.get('model_name', 'gpt-3.5-turbo')
        temperature = float(settings.get('temperature', '0.7'))
        max_tokens = int(settings.get('max_tokens', '2000'))

        # 检测 API 类型
        api_config = _detect_api_type(api_url)

        messages = [{'role': 'system', 'content': system_prompt}]
        for h in history[-MAX_HISTORY_ROUNDS * 2:]:
            messages.append({'role': h['role'], 'content': h['content']})

        if context:
            user_message = (
                f"请参考以下招聘政策文档内容回答用户问题。\n\n"
                f"=== 相关政策文档 ===\n{context}\n=== 政策文档结束 ===\n\n"
                f"用户问题：{query}"
            )
        else:
            user_message = f"用户问题：{query}\n\n注意：当前政策库中未检索到相关内容，请告知用户。"

        messages.append({'role': 'user', 'content': user_message})

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        headers.update(api_config['extra_headers'])

        payload = {
            'model': model_name,
            'messages': messages,
            'temperature': temperature,
        }
        if api_config['supports_max_tokens']:
            payload['max_tokens'] = max_tokens
        else:
            payload['max_completion_tokens'] = max_tokens

        if api_config['supports_stream']:
            payload['stream'] = True

        payload.update(api_config['extra_payload'])

        full_answer = ''
        try:
            resp = requests.post(api_url, headers=headers, json=payload,
                                stream=True, timeout=120)
            for line in resp.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk['choices'][0].get('delta', {}).get('content', '')
                            if delta:
                                full_answer += delta
                                yield f"data: {json.dumps({'content': delta, 'done': False}, ensure_ascii=False)}\n\n"
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            error_msg = f'\n\n⚠️ 连接异常: {str(e)}'
            full_answer += error_msg
            yield f"data: {json.dumps({'content': error_msg, 'done': False}, ensure_ascii=False)}\n\n"

        _save_message(session_id, 'assistant', full_answer)
        yield f"data: {json.dumps({'content': '', 'done': True, 'sources': [{'title': s['title'], 'category': s['category']} for s in sources] if sources else []}, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )
