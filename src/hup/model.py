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
        "Brier": brier_score_loss(y, p),
        "사건수": int(np.sum(y)), "n": len(y),
    }
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
