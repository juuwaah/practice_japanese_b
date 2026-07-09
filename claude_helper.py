# Claude API 共通ヘルパーモジュール
import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5")

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _extract_text(response):
    """レスポンスのcontentブロックからテキスト部分を連結して返す"""
    return "".join(block.text for block in response.content if block.type == "text")


def ask_claude(prompt, max_tokens=1024):
    """Claudeにプロンプトを送り、テキスト応答を返す"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": str(prompt)}],
    )
    return _extract_text(response).strip()


def ask_claude_json(prompt, schema, max_tokens=1024):
    """構造化出力（JSONスキーマ）でClaudeを呼び、dictを返す"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": str(prompt)}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    return json.loads(_extract_text(response))
