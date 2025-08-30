# エラーハンドリング用のユーティリティモジュール
import time
from functools import wraps
from flask import session
from translations import get_text, get_user_language
from sqlalchemy.exc import OperationalError
import openai


def get_localized_error_message(error_type, language=None):
    """言語設定に応じたエラーメッセージを取得"""
    if language is None:
        language = get_user_language()
    return get_text(error_type, language)


def handle_openai_errors(func):
    """OpenAI APIのエラーを処理するデコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError:
            return {"error": get_localized_error_message("api_rate_limit_error"), "type": "rate_limit"}
        except openai.APIConnectionError:
            return {"error": get_localized_error_message("api_connection_error"), "type": "connection"}
        except openai.APIError as e:
            if "quota" in str(e).lower() or "billing" in str(e).lower():
                return {"error": get_localized_error_message("openai_quota_exceeded"), "type": "quota"}
            return {"error": get_localized_error_message("general_system_error"), "type": "api_error"}
        except Exception as e:
            print(f"Unexpected OpenAI error: {e}")
            return {"error": get_localized_error_message("general_system_error"), "type": "unknown"}
    return wrapper


def handle_database_errors(func):
    """データベースエラーを処理するデコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except OperationalError as e:
            print(f"Database connection error: {e}")
            return {"error": get_localized_error_message("database_connection_error"), "type": "database"}
        except Exception as e:
            print(f"Unexpected database error: {e}")
            return {"error": get_localized_error_message("general_system_error"), "type": "database_unknown"}
    return wrapper


def retry_with_backoff(max_retries=3, base_delay=1):
    """指数バックオフでリトライするデコレータ"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except openai.RateLimitError:
                    if attempt == max_retries - 1:
                        return {"error": get_localized_error_message("api_rate_limit_error"), "type": "rate_limit"}
                    delay = base_delay * (2 ** attempt)
                    print(f"Rate limit hit, waiting {delay}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(delay)
                except (openai.APIConnectionError, openai.APIError) as e:
                    if attempt == max_retries - 1:
                        if "quota" in str(e).lower():
                            return {"error": get_localized_error_message("openai_quota_exceeded"), "type": "quota"}
                        return {"error": get_localized_error_message("api_connection_error"), "type": "connection"}
                    delay = base_delay * (2 ** attempt)
                    print(f"API error, waiting {delay}s before retry {attempt + 1}/{max_retries}: {e}")
                    time.sleep(delay)
            return {"error": get_localized_error_message("general_system_error"), "type": "max_retries_exceeded"}
        return wrapper
    return decorator


def check_system_load():
    """システム負荷をチェックし、必要に応じてサービス制限を適用"""
    # 簡単な負荷チェック（将来的にはより高度な監視を実装）
    current_time = time.time()
    
    # セッションベースの簡易レート制限
    if 'last_api_request' in session:
        time_since_last = current_time - session['last_api_request']
        if time_since_last < 2:  # 2秒以内の連続リクエストを制限
            return {"error": get_localized_error_message("api_rate_limit_error"), "limited": True}
    
    session['last_api_request'] = current_time
    return {"limited": False}


def format_error_response(error_info, additional_info=None):
    """エラー情報を統一フォーマットで返す"""
    response = {
        "success": False,
        "error_message": error_info.get("error", get_localized_error_message("general_system_error")),
        "error_type": error_info.get("type", "unknown")
    }
    
    if additional_info:
        response.update(additional_info)
    
    return response


def safe_openai_request(api_function):
    """OpenAI APIリクエストを安全に実行する統合関数"""
    @retry_with_backoff(max_retries=3, base_delay=1)
    @handle_openai_errors
    def make_request():
        # システム負荷チェック
        load_check = check_system_load()
        if load_check.get("limited", False):
            return load_check
        
        # API実行
        return api_function()
    
    return make_request()