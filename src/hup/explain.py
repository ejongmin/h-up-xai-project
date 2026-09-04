"""SHAP 기여도 → 사람이 읽는 설명 카드.

프로젝트의 목적은 성능이 아니라 '이 설명이 실무자에게 납득되는가'다.
그래서 여기 나가는 문장은 변수명과 숫자가 아니라 재무적 서술이어야 한다.

안정성 규칙: 사건 표본이 적어 SHAP 값이 시드에 따라 흔들린다.
여러 시드로 반복해 부호가 뒤집히지 않는 변수만 카드에 올린다(stable_features).
"""
import numpy as np
import pandas as pd

# 변수 → (위험 쪽 서술, 안전 쪽 서술, 단위)
# 순서가 값의 크기가 아니라 **위험 방향**을 기준으로 고정돼 있다는 점이 중요하다.
# SHAP 기여가 +면 위험 쪽, -면 안전 쪽 문장을 쓴다. 변수마다 "높으면 위험"인지
# "낮으면 위험"인지가 달라서, 값의 부호로 문장을 고르면 반드시 뒤집힌다.
PHRASE = {
    "부채비율":        ("부채비율이 높습니다", "부채비율이 낮은 편입니다", "배"),
    "자기자본비율":     ("자기자본이 얇아 손실 흡수 여력이 작습니다", "자기자본이 두텁습니다", ""),
    "유동비율":        ("1년 내 갚을 돈에 비해 현금화 가능한 자산이 부족합니다", "단기 지급능력에 여유가 있습니다", "배"),
    "이자보상배율":     ("영업이익으로 이자비용을 감당하지 못하고 있습니다", "영업이익으로 이자를 충분히 감당합니다", "배"),
    "영업이익률":       ("본업에서 이익이 나지 않고 있습니다", "본업에서 이익이 납니다", ""),
    "순이익률":        ("순손실 구간입니다", "순이익이 안정적입니다", ""),
    "ROA":            ("자산을 굴려 벌어들이는 이익이 적습니다", "자산 대비 수익성이 양호합니다", ""),
    "총자산영업이익률":  ("자산 대비 영업이익이 부족합니다", "자산 대비 영업이익이 양호합니다", ""),
    "영업현금흐름_매출": ("매출은 있으나 현금이 들어오지 않고 있습니다", "매출이 현금으로 잘 회수됩니다", ""),
    "영업현금흐름_부채": ("영업현금으로는 차입금 상환이 어렵습니다", "영업현금으로 차입금을 감당할 수 있습니다", ""),
    "이익의현금전환":    ("장부상 이익과 실제 현금흐름이 벌어져 있습니다", "장부이익이 현금으로 뒷받침됩니다", ""),
    "매출채권회전율":    ("대금 회수가 느려 매출채권이 쌓이고 있습니다", "대금 회수가 빠릅니다", "회"),
    "재고자산회전율":    ("재고가 소진되지 않고 누적되고 있습니다", "재고가 정상적으로 회전합니다", "회"),
    "총자산회전율":     ("자산 규모에 비해 매출이 작습니다", "자산이 효율적으로 쓰입니다", "회"),
    "자본잠식":        ("자본금 대비 자본총계가 미달합니다(부분 자본잠식)", "자본잠식 상태가 아닙니다", ""),
    "완전자본잠식":     ("자본총계가 음(-)입니다(완전 자본잠식)", "자본총계가 양(+)입니다", ""),
    "자본잠식률":       ("자본잠식 정도가 큽니다", "자본잠식이 없습니다", ""),
    "영업손실":        ("당기 영업손실이 발생했습니다", "당기 영업이익이 발생했습니다", ""),
    "2년연속영업손실":   ("2년 연속 영업손실입니다", "연속 영업손실은 아닙니다", ""),
    "Δ부채비율":       ("부채비율이 전년 대비 뚜렷하게 올랐습니다", "부채비율이 전년 대비 개선되었습니다", ""),
    "Δ영업이익률":      ("수익성이 전년 대비 나빠졌습니다", "수익성이 전년 대비 개선되었습니다", ""),
    "ΔROA":          ("자산수익성이 전년 대비 나빠졌습니다", "자산수익성이 전년 대비 개선되었습니다", ""),
    "Δ유동비율":       ("단기 유동성이 전년 대비 나빠졌습니다", "단기 유동성이 전년 대비 개선되었습니다", ""),
    "Δ총자산회전율":    ("자산 효율이 전년 대비 나빠졌습니다", "자산 효율이 전년 대비 개선되었습니다", ""),
    "Δ영업현금흐름_매출": ("현금 회수가 전년 대비 나빠졌습니다", "현금 회수가 전년 대비 개선되었습니다", ""),
    "매출증가율":       ("매출이 줄었습니다", "매출이 늘었습니다", ""),
    "자산증가율":       ("자산이 줄었습니다", "자산이 늘었습니다", ""),
    "로그자산":        ("규모가 작은 편입니다", "규모가 큰 편입니다", ""),
}

# 0/1 지표는 "(실측 1.00)"이 오히려 읽는 데 방해가 된다
FLAGS = {"자본잠식", "완전자본잠식", "영업손실", "2년연속영업손실"}

# 값이 높을 때 위험한 변수. 나머지는 전부 낮을 때 위험하다.
# W07 계수 부호 점검표와 같은 정보다 — 어긋나면 둘 중 하나가 틀린 것이다.
HIGH_IS_RISKY = {"부채비율", "자본잠식", "완전자본잠식", "자본잠식률",
                 "영업손실", "2년연속영업손실", "Δ부채비율"}


def _risky_side(name, v, ref):
    """관측값이 위험 쪽에 있는가. 판단 불가면 None."""
    if v is None or pd.isna(v):
        return None
    if name.startswith("Δ") or name.endswith("증가율") or name in FLAGS:
        base = 0.0
    elif ref is None or name not in ref or pd.isna(ref[name]):
        return None
    else:
        base = ref[name]
    return v > base if name in HIGH_IS_RISKY else v < base


def shap_values(model, X, background=None):
    """HistGB 는 TreeExplainer, 로지스틱은 선형 기여도로 계산한다."""
    import shap
    try:
        return shap.TreeExplainer(model).shap_values(X)
    except Exception:
        ex = shap.LinearExplainer(model, background if background is not None else X)
        return ex.shap_values(X)


def stable_features(model_fn, X, y, seeds=(0, 1, 2, 3, 4), top=10):
    """시드를 바꿔 재학습해도 평균 기여 부호가 유지되는 변수만 남긴다."""
    signs, mags = [], []
    for s in seeds:
        m = model_fn(random_state=s).fit(X, y)
        sv = shap_values(m, X)
        signs.append(np.sign(sv.mean(0)))
        mags.append(np.abs(sv).mean(0))
    signs = np.array(signs)
    keep = (np.abs(signs.sum(0)) == len(seeds))          # 부호가 한 번도 안 뒤집힘
    rank = np.array(mags).mean(0)
    idx = [i for i in np.argsort(-rank) if keep[i]][:top]
    return [X.columns[i] for i in idx]


def card(row, sv, cols, allow=None, top_k=4, prob=None, ref=None):
    """한 기업-연도에 대한 설명 카드(문자열).

    묶음(위험을 높인/낮춘)은 SHAP 부호로 정하고, 문장은 **관측값**으로 정한다.
    둘을 같은 근거로 정하면 모델이 이상하게 판단한 경우가 카드에서 지워진다.
    "매출이 줄었는데 위험을 낮춘 요인"으로 나오면 그게 봐야 할 지점이다.
    """
    s = pd.Series(sv, index=cols)
    if allow:
        s = s[[c for c in s.index if c in allow]]
    s = s[[c for c in s.index if not c.endswith("_결측")]]

    def line(name, contrib):
        risky, safe, unit = PHRASE.get(name, (f"{name}이(가) 위험 쪽입니다",
                                              f"{name}이(가) 안전 쪽입니다", ""))
        v = row.get(name)
        side = _risky_side(name, v, ref)
        txt = (risky if side else safe) if side is not None else (risky if contrib > 0 else safe)
        num = "" if (name in FLAGS or v is None or pd.isna(v)) else f" (실측 {v:,.2f}{unit})"
        return f"  - {txt}{num}"

    up = s[s > 0].sort_values(ascending=False).head(top_k)
    down = s[s < 0].sort_values().head(2)
    out = [f"모형 추정 부실확률 {prob:.1%}"] if prob is not None else []
    if len(up):
        out += ["위험을 높인 요인", *[line(n, c) for n, c in up.items()]]
    if len(down):
        out += ["위험을 낮춘 요인", *[line(n, c) for n, c in down.items()]]
    return "\n".join(out)
