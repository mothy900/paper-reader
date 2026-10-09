from functools import cache

import anthropic

from app.config import settings


@cache
def get_llm_client() -> anthropic.AsyncAnthropic:
    # 키를 비워 두면 SDK가 ANTHROPIC_API_KEY 환경 변수나 `ant auth login` 프로필을 쓴다
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
