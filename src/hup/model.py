"""기준 모델과 앙상블, 그리고 평가 지표.

정확도는 보고하지 않는다. 사건 비율이 2%면 전부 정상으로 찍어도 98%다.
PR-AUC 와 '정밀도 고정 시 재현율'로 보고하고, 부트스트랩 신뢰구간을 붙인다.
"""
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def baseline():
    """로지스틱 회귀 — 계수 부호가 재무 상식과 맞는지가 1차 검증 기준."""
    return Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def ensemble(**kw):
    """결측을 그대로 먹고 추가 의존성이 없다. LightGBM 은 필요해지면 그때."""
    p = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=15,
             min_samples_leaf=30, l2_regularization=1.0,
             class_weight="balanced", random_state=42)
    p.update(kw)
    return HistGradientBoostingClassifier(**p)


def calibrated(base_fn, method="isotonic", cv=5, **kw):
    """확률 보정. 설명 카드에 '부실확률 37%' 를 쓰려면 그 숫자가 확률이어야 한다.

    class_weight="balanced" 는 소수 클래스 가중을 올려 **예측 확률을 통째로 부풀린다.**
    순위(PR-AUC)는 멀쩡한데 값은 확률이 아니다. 학습 구간 내부 교차검증으로 보정한다
    (cv=5). 검증·평가 구간은 건드리지 않는다.
    """
    from sklearn.calibration import CalibratedClassifierCV
    return CalibratedClassifierCV(base_fn(**kw), method=method, cv=cv)


def calibration_table(y, p, bins=5):
    """예측 확률 구간별 실제 발생률. 보정이 됐는지는 이 표로 본다."""
    import pandas as pd
    d = pd.DataFrame({"p": p, "y": y})
    d["구간"] = pd.qcut(d["p"], bins, duplicates="drop")
    g = d.groupby("구간", observed=True).agg(
        n=("y", "size"), 예측평균=("p", "mean"), 실제발생률=("y", "mean"))
    return g.round(4)


def recall_at_precision(y, p, target=0.30):
    """정밀도 target 이상을 유지하면서 잡을 수 있는 최대 재현율."""
    order = np.argsort(-p)
    y = np.asarray(y)[order]
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    rec = tp / max(y.sum(), 1)
    ok = prec >= target
    return float(rec[ok].max()) if ok.any() else 0.0


def evaluate(y, p, n_boot=1000, seed=0):
    base = {
        "PR-AUC": average_precision_score(y, p),
        "ROC-AUC": roc_auc_score(y, p),
        "재현율@정밀도0.3": recall_at_precision(y, p, 0.30),
        "재현율@정밀도0.5": recall_at_precision(y, p, 0.50),
        "사건수": int(np.sum(y)), "n": len(y),
    }
    # Brier 는 확률에만 정의된다. 고전 모형 점수(Z·O-score)처럼 [0,1] 밖이면 계산하지 않는다 —
    # 순위 지표(PR-AUC·ROC-AUC)는 단조변환에 불변이라 그대로 쓸 수 있다.
    pa = np.asarray(p, dtype=float)
    base["Brier"] = (brier_score_loss(y, pa) if pa.min() >= 0 and pa.max() <= 1
                     else None)
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    boot = {k: [] for k in ("PR-AUC", "ROC-AUC", "재현율@정밀도0.3")}
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if y[i].sum() == 0:
            continue
        boot["PR-AUC"].append(average_precision_score(y[i], p[i]))
        boot["ROC-AUC"].append(roc_auc_score(y[i], p[i]))
        boot["재현율@정밀도0.3"].append(recall_at_precision(y[i], p[i], 0.30))
    for k, v in boot.items():
        base[f"{k}_95CI"] = (round(float(np.percentile(v, 2.5)), 4),
                             round(float(np.percentile(v, 97.5)), 4)) if v else None
    return base


def prevalence_baseline(y_test):
    """항상 사건 비율을 예측하는 모델. PR-AUC 의 바닥선이 이 값이다."""
    return float(np.mean(y_test))


# ─────────────────────────────────────────────────────────────
# 고전 모형 벤치마크 — Altman(1968) · Ohlson(1980)
#
# 1968·1980년 미국 데이터로 만든 계수를 2016~2025 한국 상장사에 그대로 적용한다.
# "고전 모형이 지금 여기서 얼마나 작동하는가"는 그 자체로 결과다.
# 원 논문의 계수를 쓰므로 우리 데이터로 재적합하지 않는다 — 재적합하면 벤치마크가 아니다.

def altman_z(a):
    """Altman(1968) Z-score. 높을수록 안전하므로 위험 점수로 쓰려면 부호를 뒤집는다.

    원식: Z = 1.2·X1 + 1.4·X2 + 3.3·X3 + 0.6·X4 + 1.0·X5
      X1 운전자본/총자산  X2 이익잉여금/총자산  X3 EBIT/총자산
      X4 자기자본시가/총부채  X5 매출/총자산

    **우리 데이터의 한계**: 이익잉여금(X2)과 시가총액(X4)이 없다.
    X2 는 자본잠식률로, X4 는 자기자본/총부채(장부가)로 대체한다.
    원식과 다르므로 **'Altman 형(form)'이라고 부르고 Z 값 자체는 해석하지 않는다.**
    비교에 쓰는 것은 순위(PR-AUC)뿐이다.
    """
    import numpy as np
    wc = (a.get("cur_assets", np.nan) - a.get("cur_liab", np.nan))
    ta = a.get("assets", np.nan)
    x1 = wc / ta
    x2 = -a.get("자본잠식률_proxy", 0.0)
    x3 = a.get("op_income", np.nan) / ta
    x4 = a.get("equity", np.nan) / a.get("liabilities", np.nan)
    x5 = a.get("revenue", np.nan) / ta
    return 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5


def ohlson_o(df):
    """Ohlson(1980) O-score 형. 높을수록 위험.

    원식 9개 변수 중 GNP 물가지수 보정 항과 규모 항은 우리 변수로 대체한다.
    Altman 과 같은 이유로 **'Ohlson 형'이라 부르고 값 자체를 해석하지 않는다.**
    """
    import numpy as np
    z = (-1.32
         - 0.407 * df["로그자산"]
         + 6.03 * (df["liabilities_ratio"] if "liabilities_ratio" in df else
                   1 - df["자기자본비율"])
         - 1.43 * ((df["cur_assets_ratio"] if "cur_assets_ratio" in df
                    else df["유동비율"] * 0.3))
         + 0.076 * df["유동비율"].clip(0, 5)
         - 1.72 * df["완전자본잠식"]
         - 2.37 * df["ROA"]
         - 1.83 * df["영업현금흐름_부채"]
         + 0.285 * df["2년연속영업손실"]
         - 0.521 * df["ΔROA"].fillna(0))
    return z
