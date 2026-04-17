"""
SM-2 間隔重複演算法
===================
根據使用者回答的正確率，計算下一次應複習的間隔天數與難易係數。

參考：https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-of-learning
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass
class SM2Result:
    ease_factor: float      # 難易係數（≥ 1.3）
    interval_days: int      # 下次複習間隔天數
    repetitions: int        # 累計連續答對次數
    next_review: datetime.datetime


def calculate_next_review(
    score: float,           # 0.0 ~ 1.0  (1.0 = 完全正確)
    ease_factor: float,     # 目前 EF，初始 2.5
    interval_days: int,     # 目前間隔天數
    repetitions: int,       # 目前連續答對次數
) -> SM2Result:
    """
    score 對應 SM-2 的 q 值（0–5）：
      ≥ 0.6 (q≥3) → 答對，進入正常排程
      < 0.6 (q<3) → 答錯，重置為第 1 天
    """
    q = round(score * 5)        # 映射至 SM-2 的 0–5 量表

    if q < 3:
        # 答錯 → 重置
        new_repetitions = 0
        new_interval = 1
    else:
        # 答對 → 計算新間隔
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval_days * ease_factor)
        new_repetitions = repetitions + 1

    # 更新難易係數（EF 下限 1.3）
    new_ef = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    new_ef = max(1.3, round(new_ef, 4))

    next_review = datetime.datetime.utcnow() + datetime.timedelta(days=new_interval)

    return SM2Result(
        ease_factor=new_ef,
        interval_days=new_interval,
        repetitions=new_repetitions,
        next_review=next_review,
    )
