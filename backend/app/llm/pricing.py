"""모델별 단가 ($ / 100만 토큰). 2026-09 기준 Anthropic 공식 가격."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_read: float
    cache_write_5m: float


# 응답의 model 값에는 날짜가 붙어 올 수 있어(claude-haiku-4-5-20251001) 앞부분으로 찾는다.
# Sonnet 5는 Sonnet 5.5가 거절했을 때 서버가 대신 응답하는 대체 모델이다.
_PRICES: dict[str, Price] = {
    "claude-haiku-4-5": Price(input=1.0, output=5.0, cache_read=0.10, cache_write_5m=1.25),
    "claude-sonnet-5-5": Price(input=2.0, output=10.0, cache_read=0.20, cache_write_5m=2.50),
    "claude-sonnet-5": Price(input=2.0, output=10.0, cache_read=0.20, cache_write_5m=2.50),
}


def price_for(model: str) -> Price | None:
    # 긴 이름부터 비교해야 claude-sonnet-5-5가 claude-sonnet-5로 잘못 잡히지 않는다
    for prefix in sorted(_PRICES, key=len, reverse=True):
        if model.startswith(prefix):
            return _PRICES[prefix]
    return None


def cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int = 0, cache_write: int = 0) -> float:
    price = price_for(model)
    if price is None:
        return 0.0
    total = (
        input_tokens * price.input
        + output_tokens * price.output
        + cache_read * price.cache_read
        + cache_write * price.cache_write_5m
    )
    return round(total / 1_000_000, 6)
