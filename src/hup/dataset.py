"""패널 조립 · 시점 정합 · 정제 · 분할.

이 파일에 프로젝트의 정직성이 걸려 있다. 규칙은 셋뿐이다.
  1. 기준시점 T = 사업보고서 접수일자(rcept_dt). 결산일이 아니다.
  2. 라벨 = T < 사건일 <= T + horizon.  T 이하의 사건은 이미 알려진 정보라 제외한다.
  3. 윈저라이즈·결측 대치의 기준값은 학습 구간에서만 계산해 검증·평가에 적용한다.
"""
import numpy as np
import pandas as pd

from . import config, features


def attach_labels(panel, events, horizon_days=None):
    """panel: corp_code, bsns_year, rcept_dt(datetime), 피처들"""
    # pandas 2.3 + numpy 2.5 에서 Timedelta(days=n) 은 DeprecationWarning 을 내고
    # 장래에 에러가 된다. 단위를 명시한 Timedelta(n, "D") 를 쓴다.
    h = pd.Timedelta(horizon_days or config.HORIZON_DAYS, "D")
    ev = events[["corp_code", "event_date", "event_type"]]
    m = panel.merge(ev, on="corp_code", how="left")
    hit = (m["event_date"] > m["rcept_dt"]) & (m["event_date"] <= m["rcept_dt"] + h)
    m["hit"] = hit.fillna(False)
    # 창 안에 든 사건만 event_type 으로 남긴다. 이 마스킹이 없으면
    # '이 기업에 언젠가 사건이 있었다'가 되어 y=0 행에도 유형이 붙는다.
    m["event_type"] = m["event_type"].where(m["hit"])
    lab = (m.groupby(["corp_code", "bsns_year"], as_index=False)
             .agg(y=("hit", "max"),
                  event_type=("event_type", lambda s: next(iter(s.dropna()), None))))
    out = panel.merge(lab, on=["corp_code", "bsns_year"], how="left")
    out["y"] = out["y"].fillna(False).astype(int)
    return out


def apply_exclusions(panel, meta):
    """meta: corp_code, corp_name, induty_code, acc_mt"""
    m = panel.merge(meta, on="corp_code", how="left")
    nm = m["corp_name"].fillna("")
    ind = m["induty_code"].astype(str).str[:2]
    drop_nm = (nm.str.contains("|".join(config.EXCLUDE_NAME_CONTAINS))
               | nm.str.endswith(config.EXCLUDE_NAME_SUFFIX))
    drop_fin = ind.isin(config.EXCLUDE_INDUSTRY_PREFIX)
    drop_acc = m["acc_mt"].astype(str).str.zfill(2) != "12"
    # 순서가 사유 표를 바꾼다. 스팩은 업종코드가 661(금융지원서비스)이라 금융업을 먼저 보면
    # 전부 '금융업'으로 기록된다. 제외는 어차피 되지만 보고서에 실릴 사유가 틀린다.
    m["_excl"] = np.select(
        [drop_nm, drop_fin, drop_acc], ["스팩/리츠", "금융업", "비12월결산"], default="")
    return m[m["_excl"] == ""].drop(columns=["_excl"]), m[m["_excl"] != ""][["corp_code", "bsns_year", "_excl"]]


def split(df, spec=None):
    """T 의 연도로 자른다. 무작위 분할은 쓰지 않는다."""
    spec = spec or config.SPLIT
    y = df["rcept_dt"].dt.year
    return {k: df[(y >= a) & (y <= b)].copy() for k, (a, b) in spec.items()}


def fit_clean(train, cols=None, lo=0.01, hi=0.99):
    """윈저라이즈 경계와 대치값을 학습 구간에서만 계산한다.

    이진 변수는 윈저라이즈에서 뺀다. 2026-09-04: `완전자본잠식` 은 발생률이 0.53%라
    99분위가 0 이 되고, 클리핑하면 **전 행이 0 이 되어 변수가 사라진다.**
    자본총계가 음수라는 부실의 가장 직접적인 신호가 희소하다는 이유로 지워졌다.
    이상치를 누르려던 처리가 희귀 사건 지표를 죽이면 안 된다.
    """
    cols = cols or [c for c in features.FEATURE_COLS if c in train.columns]
    binary = [c for c in cols if train[c].dropna().isin((0, 1)).all()]
    clip = [c for c in cols if c not in binary]
    return {"cols": cols, "binary": binary, "clip": clip,
            # 결측 더미를 만들 열도 여기서 못 박는다. 각 구간에서 따로 정하면
            # 학습에만 있는 열이 생겨서 검증·평가에서 KeyError 가 난다.
            "flags": [c for c in cols if train[c].isna().any()],
            "lo": train[clip].quantile(lo),
            "hi": train[clip].quantile(hi),
            "med": train[cols].median()}


def apply_clean(df, st, add_missing_flags=True):
    cols = st["cols"]
    out = df.copy()
    if add_missing_flags:
        for c in st["flags"]:
            out[f"{c}_결측"] = out[c].isna().astype(int)
    out[st["clip"]] = out[st["clip"]].clip(st["lo"], st["hi"], axis=1)
    out[cols] = out[cols].fillna(st["med"])
    return out


def sanity(splits):
    """분할이 실제로 시점 순인지 확인. 어기면 성능이 비현실적으로 좋아진다."""
    tr, va, te = splits["train"], splits["valid"], splits["test"]
    assert tr["rcept_dt"].max() < va["rcept_dt"].min(), "학습이 검증보다 늦다"
    assert va["rcept_dt"].max() < te["rcept_dt"].min(), "검증이 평가보다 늦다"
    return {k: {"n": len(v), "사건": int(v["y"].sum()),
                "사건비율": round(float(v["y"].mean()), 4)} for k, v in splits.items()}
