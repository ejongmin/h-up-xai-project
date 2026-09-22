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
    "자기자본비율":     ("자기자본이 얇아 손실을 흡수할 여력이 작습니다", "자기자본이 두텁습니다", "%"),
    "유동비율":        ("1년 내 갚아야 할 돈에 비해 현금화 가능한 자산이 부족합니다",
                       "단기 지급능력에 여유가 있습니다", "%"),
    "이자보상배율":     ("영업이익으로 이자비용을 감당하지 못하고 있습니다",
                       "영업이익으로 이자비용을 충분히 감당합니다", "배"),
    "영업이익률":       ("본업에서 이익이 나지 않고 있습니다", "본업에서 이익이 납니다", "%"),
    "순이익률":        ("순손실 상태입니다", "순이익이 유지되고 있습니다", "%"),
    "ROA":            ("자산 규모에 비해 벌어들이는 이익이 적습니다",
                       "자산 대비 수익성이 양호합니다", "%"),
    "총자산영업이익률":  ("자산 대비 영업이익이 부족합니다", "자산 대비 영업이익이 양호합니다", "%"),
    "영업현금흐름_매출": ("매출은 있으나 현금이 들어오지 않고 있습니다",
                       "매출이 현금으로 회수되고 있습니다", "%"),
    "영업현금흐름_부채": ("영업활동 현금으로는 차입금 상환이 어렵습니다",
                       "영업활동 현금으로 차입금을 감당할 수 있습니다", "%"),
    "이익의현금전환":    ("장부상 이익과 실제 현금흐름이 벌어져 있습니다",
                       "장부이익이 현금으로 뒷받침됩니다", "배"),
    "매출채권회전율":    ("대금 회수가 느려 매출채권이 쌓이고 있습니다", "대금 회수가 빠른 편입니다", "회"),
    "재고자산회전율":    ("재고가 소진되지 않고 누적되고 있습니다", "재고가 정상적으로 회전합니다", "회"),
    "총자산회전율":     ("보유 자산 규모에 비해 매출이 작습니다", "자산이 효율적으로 쓰이고 있습니다", "회"),
    "자본잠식":        ("자본총계가 자본금에 미달합니다(부분 자본잠식)", "자본잠식 상태가 아닙니다", ""),
    "완전자본잠식":     ("자본총계가 음(-)입니다(완전 자본잠식)", "자본총계가 양(+)입니다", ""),
    "자본잠식률":       ("자본잠식이 진행되어 있습니다", "자본잠식이 없습니다", "%"),
    "영업손실":        ("당기 영업손실이 발생했습니다", "당기 영업이익이 발생했습니다", ""),
    "2년연속영업손실":   ("2년 연속 영업손실입니다", "연속 영업손실은 아닙니다", ""),
    "Δ부채비율":       ("부채비율이 전년 대비 올랐습니다", "부채비율이 전년 대비 개선되었습니다", "%p"),
    "Δ영업이익률":      ("수익성이 전년 대비 나빠졌습니다", "수익성이 전년 대비 개선되었습니다", "%p"),
    "ΔROA":          ("자산수익성이 전년 대비 나빠졌습니다", "자산수익성이 전년 대비 개선되었습니다", "%p"),
    "Δ유동비율":       ("단기 유동성이 전년 대비 나빠졌습니다", "단기 유동성이 전년 대비 개선되었습니다", "%p"),
    "Δ총자산회전율":    ("자산 효율이 전년 대비 나빠졌습니다", "자산 효율이 전년 대비 개선되었습니다", "회"),
    "Δ영업현금흐름_매출": ("현금 회수가 전년 대비 나빠졌습니다", "현금 회수가 전년 대비 개선되었습니다", "%p"),
    "매출증가율":       ("매출이 전년 대비 줄었습니다", "매출이 전년 대비 늘었습니다", "%"),
    "자산증가율":       ("자산이 전년 대비 줄었습니다", "자산이 전년 대비 늘었습니다", "%"),
    # 로그값을 그대로 보여주면 실무 문서에 쓸 수 없다. 자산총계(억원)로 환산해 적는다.
    "로그자산":        ("자산 규모가 작아 외부 충격이나 자금경색에 견딜 여력이 작습니다",
                       "자산 규모가 커서 완충 여력이 있습니다", "억원"),
}

# 비율로 표시할 변수 — 소수(0.52)가 아니라 퍼센트(52.0%)로 적는다.
# "자본잠식 정도가 큽니다 (실측 0.52)" 는 재무 문서로 읽히지 않는다.
PCT = {"자기자본비율", "유동비율", "영업이익률", "순이익률", "ROA", "총자산영업이익률",
       "영업현금흐름_매출", "영업현금흐름_부채", "자본잠식률",
       "Δ부채비율", "Δ영업이익률", "ΔROA", "Δ유동비율", "Δ영업현금흐름_매출",
       "매출증가율", "자산증가율"}


def format_value(name, v, unit):
    """실측값을 실무 표기로. 로그자산은 억원으로 환산한다."""
    if v is None or pd.isna(v):
        return ""
    if name == "로그자산":
        return f" (자산 약 {np.exp(v)/1e8:,.0f}억원)"
    if name in PCT:
        return f" (실측 {v*100:,.1f}{unit})"
    return f" (실측 {v:,.2f}{unit})"


# 0/1 지표는 "(실측 1.00)"이 오히려 읽는 데 방해가 된다
FLAGS = {"자본잠식", "완전자본잠식", "영업손실", "2년연속영업손실"}

# 값이 높을 때 위험한 변수. 나머지는 전부 낮을 때 위험하다.
# W07 계수 부호 점검표와 같은 정보다 — 어긋나면 둘 중 하나가 틀린 것이다.
HIGH_IS_RISKY = {"부채비율", "자본잠식", "완전자본잠식", "자본잠식률",
                 "영업손실", "2년연속영업손실", "Δ부채비율"}


# 자본총계를 분모로 쓰는 비율. 자본이 음(-)이면 값의 부호가 뒤집혀 해석이 불가능하다.
# 2026-09-22: 완전자본잠식 기업의 부채비율 −2.52 를 보고 카드가
# "부채비율이 낮은 편입니다"라고 썼다. 가장 심한 부실 신호를 안전 신호로 뒤집어 읽은 것이다.
EQUITY_BASED = {"부채비율", "자기자본비율", "자본잠식률"}


def _equity_wiped(row):
    """완전자본잠식 여부. 자본 기반 비율이 음수면 자본총계가 음(-)이다."""
    if row.get("완전자본잠식") == 1:
        return True
    for c in ("부채비율", "자기자본비율"):
        v = row.get(c)
        if v is not None and not pd.isna(v) and v < 0:
            return True
    return False


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


def direction(X, sv):
    """변수마다 `값 ↔ SHAP` 상관. 카드가 주장하는 '높으면 위험'의 방향 그 자체다."""
    out = {}
    for j, c in enumerate(X.columns):
        x = X.iloc[:, j].to_numpy(dtype=float)
        y = sv[:, j]
        if x.std() == 0 or y.std() == 0:
            out[c] = 0.0
        else:
            out[c] = float(np.corrcoef(x, y)[0, 1])
    return pd.Series(out)


def stable_features(model_fn, X, y, seeds=(0, 1, 2, 3, 4), top=10, min_corr=0.2):
    """시드를 바꿔 재학습해도 **방향이 유지되는** 변수만 남긴다.

    2026-09-08 수정: 이전에는 SHAP 값의 **평균 부호**를 봤다. 그런데 SHAP 평균은
    기업마다 +/− 가 상쇄돼 0 근처의 잡음이다(ROA 는 평균 −0.014, 크기 0.311 — 4%).
    잡음의 부호는 시드마다 당연히 뒤집히고, 그래서 기여도 1·3위가 탈락했다.
    **측정 대상이 틀렸다.**

    카드가 주장하는 것은 "이 변수가 높으면 위험하다"는 방향이므로,
    `값 ↔ SHAP` 상관의 부호가 모든 시드에서 같고 크기가 min_corr 이상인 변수만 남긴다.
    """
    dirs, mags = [], []
    for s in seeds:
        m = model_fn(random_state=s).fit(X, y)
        sv = shap_values(m, X)
        dirs.append(direction(X, sv))
        mags.append(np.abs(sv).mean(0))
    D = pd.DataFrame(dirs)                      # 시드 × 변수
    same_sign = (np.sign(D).nunique() == 1)     # 부호가 한 번도 안 뒤집힘
    strong = (D.abs().min() >= min_corr)        # 모든 시드에서 방향이 뚜렷함
    keep = same_sign & strong
    rank = pd.Series(np.array(mags).mean(0), index=X.columns)
    return [c for c in rank.sort_values(ascending=False).index if keep.get(c, False)][:top]


# 카드에 올리지 않는 변수. **모델에서 빼는 것이 아니라 문장으로 만들지 않는 것**이다.
# 근거 셋 (2026-09-08):
#   1. 판별력이 수준값의 1/50 (6주차 EDA)
#   2. 사건 기업은 3년 전부터 이미 나쁘고 크게 변하지 않는다 (6주차 궤적)
#   3. 카드 문장–관측값 모순의 51% 를 만든다. 빼면 23.8% → 14.1% (11주차 충실도)
def _card_excluded(name):
    return name.endswith("_결측") or name.startswith("Δ") or name.endswith("증가율")


def counterfactual(model, X_row, cols, names, ref, n=3, min_drop=0.05, skip=()):
    """"이 항목이 표본 중앙값 수준이면 확률이 얼마가 되는가"

    카드는 왜 위험한지만 말하고 **무엇을 보면 되는지**는 말하지 않는다.
    여신심사에서 쓰이려면 이쪽이 필요하다. 삭제 검사와 같은 기계를 쓰되
    지우는 게 아니라 **정상 수준으로 되돌린다**.

    규칙 셋 (2026-09-22 실측에서 고침)
      - `model` 은 **카드에 찍는 확률과 같은 모형**이어야 한다. 보정본과 비보정을
        섞으면 카드 머리의 57.7% 와 반사실의 89.8% 가 따로 논다.
      - 자본이 음(-)인 기업의 자본 기반 비율은 제외한다(`skip`). 위에서 제외해놓고
        반사실로 다시 꺼내면 모순이다.
      - 하락폭이 min_drop 미만이면 싣지 않는다. 1.9%p 차이는 보여줄 값이 없다.

    주의: 인과 효과가 아니라 **모형이 그렇게 반응한다**는 서술이다.
    """
    base = float(model.predict_proba(X_row.to_frame().T[cols])[0, 1])
    out = []
    for nm in names:
        if nm in skip or nm not in cols:
            continue
        target, phrase = cf_target(nm, ref)
        if target is None:
            continue
        z = X_row.copy()
        z[nm] = target
        p = float(model.predict_proba(z.to_frame().T[cols])[0, 1])
        if base - p >= min_drop:
            out.append((nm, base, p, target, phrase))
    out.sort(key=lambda r: r[2])
    return base, out[:n]


# 변수마다 '정상 수준'의 뜻이 다르다. 자본잠식은 중앙값이 아니라 **해소(0%)** 가 기준이고,
# 중앙값 −829.7% 를 목표로 제시하면 실무 문장이 되지 않는다.
CF_TARGET = {
    "자본잠식률": (0.0, "자본잠식이 해소되면"),
    "영업손실": (0.0, "영업이익으로 돌아서면"),
    "2년연속영업손실": (0.0, "연속 영업손실에서 벗어나면"),
    "자본잠식": (0.0, "자본잠식이 해소되면"),
    "완전자본잠식": (0.0, "자본총계가 양(+)으로 돌아서면"),
}


def cf_target(name, ref):
    """반사실 목표값과 문구. 지정이 없으면 표본 중앙값."""
    if name in CF_TARGET:
        v, phrase = CF_TARGET[name]
        return v, phrase
    if name in ref and not pd.isna(ref[name]):
        _, _, unit = PHRASE.get(name, ("", "", ""))
        tv = format_value(name, ref[name], unit).strip(" ()").replace("실측 ", "")
        return float(ref[name]), f"{name}이(가) 표본 중앙값({tv}) 수준이면"
    return None, None


def counterfactual_lines(base, items):
    """반사실 결과를 카드 문장으로."""
    if not items:
        return []
    lines = ["무엇이 달라지면 (모형 기준 — 인과 효과가 아닙니다)"]
    for nm, b, p, _target, phrase in items:
        lines.append(f"  - {phrase} 부실확률 {b:.1%} → {p:.1%}")
    return lines


def card(row, sv, cols, allow=None, top_k=4, prob=None, ref=None, cf=None):
    """한 기업-연도에 대한 설명 카드(문자열).

    묶음(위험을 높인/낮춘)은 SHAP 부호로 정하고, 문장은 **관측값**으로 정한다.
    둘을 같은 근거로 정하면 모델이 이상하게 판단한 경우가 카드에서 지워진다.
    "매출이 줄었는데 위험을 낮춘 요인"으로 나오면 그게 봐야 할 지점이다.
    """
    s = pd.Series(sv, index=cols)
    if allow:
        s = s[[c for c in s.index if c in allow]]
    s = s[[c for c in s.index if not _card_excluded(c)]]

    def line(name, contrib):
        risky, safe, unit = PHRASE.get(name, (f"{name}이(가) 위험 쪽입니다",
                                              f"{name}이(가) 안전 쪽입니다", ""))
        v = row.get(name)
        side = _risky_side(name, v, ref)
        txt = (risky if side else safe) if side is not None else (risky if contrib > 0 else safe)
        num = "" if name in FLAGS else format_value(name, v, unit)
        return f"  - {txt}{num}"

    wiped = _equity_wiped(row)
    if wiped:
        # 자본이 음(-)이면 자본 기반 비율은 문장으로 만들지 않는다. 대신 사실을 직접 적는다.
        s = s[[c for c in s.index if c not in EQUITY_BASED]]

    up = s[s > 0].sort_values(ascending=False).head(top_k)
    down = s[s < 0].sort_values().head(2)
    out = [f"모형 추정 부실확률 {prob:.1%}"] if prob is not None else []
    if wiped:
        out.append("※ 자본총계가 음(-)입니다(완전 자본잠식). "
                   "부채비율·자기자본비율은 해석할 수 없어 아래에서 제외했습니다.")
    if len(up):
        out += ["위험을 높인 요인", *[line(n, c) for n, c in up.items()]]
    # 위험 요인만 나열하면 카드가 확증 편향을 유도하는 도구가 된다.
    # 낮춘 요인이 없으면 **없다고 적는다** — 조용히 빼면 한쪽만 보여주는 게 된다.
    out += (["위험을 낮춘 요인", *[line(n, c) for n, c in down.items()]] if len(down)
            else ["위험을 낮춘 요인", "  - 해당 없음 (안정 변수 중 위험을 낮춘 항목이 없습니다)"])
    if cf:
        out += cf
    return "\n".join(out)
