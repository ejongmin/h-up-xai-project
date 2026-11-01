"""최초 공시 원문(XBRL)의 재무값 — 2차 연구의 데이터 원천 (docs/15 §3).

1차 연구는 fnlttSinglAcntAll 을 썼는데, 이 API 는 **가장 최근 정정본**의 값을 준다.
기준시점 T(최초 접수일)에 시장이 실제로 볼 수 있던 값이 아니다(1차에서 21.4% 행).
fnlttXbrl 은 접수번호(rcept_no)별 원본 XBRL 을 주므로, 최초 접수번호를 넣으면 그날의 값이 나온다.

2026-10-31 확인: 상장사 사업보고서(2019-03 접수분) 3건 모두 zip 으로 받았다.
비상장사는 status 014(파일 없음)가 온다 — 이 경우도 '없음'으로 캐시한다.

원본 zip 을 그대로 캐시한다. 계정을 더 뽑을 일이 생겨도 다시 받지 않는다.
"""
import io
import json
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile

from . import config, dart

DIR = config.CACHE / "xbrl"
AXIS = "ConsolidatedAndSeparateFinancialStatementsAxis"


def fetch(rcept_no):
    """원본 XBRL zip 바이트. 원본이 없으면 None. 한도 초과는 QuotaExceeded."""
    DIR.mkdir(parents=True, exist_ok=True)
    f, miss = DIR / f"{rcept_no}.zip", DIR / f"{rcept_no}.none"
    if f.exists():
        return f.read_bytes()
    if miss.exists():
        return None
    if not config.DART_KEY:
        raise dart.DartError("DART_API_KEY 가 비어 있다. .env 를 확인할 것")
    url = dart.BASE + "fnlttXbrl.xml?" + urllib.parse.urlencode(
        {"crtfc_key": config.DART_KEY, "rcept_no": rcept_no, "reprt_code": config.REPRT_ANNUAL})
    b = dart._open(url, timeout=60)
    dart.CALLS += 1
    time.sleep(dart.SLEEP)
    if b[:2] == b"PK":
        try:
            zipfile.ZipFile(io.BytesIO(b)).testzip()
        except zipfile.BadZipFile:               # 전송 중 잘림 — 캐시하지 않고 다음에 다시
            raise dart.DartError(f"{rcept_no} zip 손상")
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(b)
        tmp.replace(f)
        return b
    status = re.search(rb"<status>(\d+)</status>", b)
    status = status.group(1).decode() if status else "?"
    if status == "020":
        raise dart.QuotaExceeded("일일 호출 한도 초과 (fnlttXbrl)")
    if status in ("013", "014"):
        miss.write_text(status)
        return None
    raise dart.DartError(f"fnlttXbrl {rcept_no} status={status}")


def _prefix(uri):
    if "iasb.org" in uri or "ifrs.org" in uri:
        return "ifrs-full"
    if "dart.fss.or.kr" in uri:
        tail = uri.rstrip("/").rsplit("/", 1)[-1]
        if tail.startswith("entity"):            # 회사가 직접 만든 확장 계정 — 코드로는 못 찾고 이름(라벨)으로만 찾는다
            return "ext"
        return "dart-gcd" if tail == "dart-gcd" else "dart"
    return None


def _labels(z):
    """{계정 로컬명: 한글 표준 라벨}. API 의 account_nm 에 해당한다.

    2026-10-31: 1차는 표준 코드가 없는 계정('-표준계정코드 미사용-')을 이름으로 찾았다(자본금·매출채권 등).
    라벨 없이 코드로만 뽑으니 2차에서 자본잠식률 2,158행·매출채권회전율 1,369행이 새로 비었다.
    """
    out = {}
    for n in z.namelist():
        # 2026-11-01 (v2.1): 2024 년 이후 파일은 'entity…_2023-12-31_lab-ko.xml' 형식이다. 옛 형식 'labels\\lab_…-ko_….xml' 만 찾다가
        # 2024+ 공시의 라벨을 하나도 못 읽었다 — 평가 구간에서만 결측이 늘었다 (docs/15 §10)
        base = n.replace("\\", "/").rsplit("/", 1)[-1].lower()
        if not (base.endswith(".xml") and "lab" in base and "-ko" in base):
            continue
        root = ET.fromstring(z.read(n))
        loc, lab, arcs = {}, {}, []
        for e in root.iter():
            t = e.tag.split("}")[-1]
            g = lambda a: e.get("{http://www.w3.org/1999/xlink}" + a)
            if t == "loc":
                loc[g("label")] = (g("href") or "").split("#")[-1]
            elif t == "label" and (g("role") or "").endswith("/role/label"):
                lab[g("label")] = (e.text or "").strip()
            elif t == "labelArc":
                arcs.append((g("from"), g("to")))
        for f, to in arcs:
            if f in loc and to in lab and "_" in loc[f]:
                out.setdefault(loc[f].split("_", 1)[1], lab[to])
    return out


def _contexts(root):
    """{context id: (기준 'CFS'|'OFS'|'ND', 'I'|'D', 종료연도, 기간일수)} — 연결/별도 축 외 차원이 붙은 것은 버린다."""
    import datetime as dt
    out = {}
    for c in root.iter():
        if not c.tag.endswith("}context"):
            continue
        dims = [(m.get("dimension", ""), (m.text or "").strip()) for m in c.iter() if m.tag.endswith("}explicitMember")]
        if any(AXIS not in d for d, _ in dims) or len(dims) > 1:
            continue
        fs = "ND"
        if dims:
            fs = "CFS" if dims[0][1].endswith("ConsolidatedMember") else "OFS" if dims[0][1].endswith("SeparateMember") else None
        if fs is None:
            continue
        p = {e.tag.split("}")[1]: (e.text or "").strip() for e in c.iter() if e.tag.split("}")[-1] in ("instant", "startDate", "endDate")}
        try:
            if "instant" in p:
                out[c.get("id")] = (fs, "I", int(p["instant"][:4]), 0)
            else:
                s, e = dt.date.fromisoformat(p["startDate"]), dt.date.fromisoformat(p["endDate"])
                out[c.get("id")] = (fs, "D", e.year, (e - s).days)
        except (KeyError, ValueError):
            continue
    return out


def parse(blob, fy):
    """zip → ({'CFS'|'OFS'|'ND': [fnlttSinglAcntAll 모양의 행]}, 메타).

    행 모양을 API 응답에 맞춰 features.extract 를 그대로 쓴다.
      시점(instant) 값 → sj_div 'BS', 기간 값 → 'IS' 와 'CF' 둘 다 (계정 코드가 표마다 달라 섞이지 않는다)
      당기 = 종료연도 fy, 전기 = fy-1. 기간 값은 1년(350~380일)짜리만 — 분기 누적 값을 막는다.
    """
    z = zipfile.ZipFile(io.BytesIO(blob))
    inst = [n for n in z.namelist() if n.endswith(".xbrl")]
    if not inst:
        return {}, {"오류": "xbrl 인스턴스 없음"}
    root = ET.fromstring(z.read(inst[0]))
    ctx = _contexts(root)
    names = _labels(z)
    units = {u.get("id"): " ".join((m.text or "").strip() for m in u.iter() if m.tag.endswith("}measure"))
             for u in root.iter() if u.tag.endswith("}unit")}
    cur = set()
    vals = {}   # (fs, kind, account_id) → {'thstrm_amount': v, 'frmtrm_amount': v}
    for el in root:
        ref = el.get("contextRef")
        if ref not in ctx or "}" not in el.tag:
            continue
        uri, name = el.tag[1:].split("}")
        pre = _prefix(uri)
        fs, kind, year, days = ctx[ref]
        if pre is None or (kind == "D" and not 350 <= days <= 380):
            continue
        col = {fy: "thstrm_amount", fy - 1: "frmtrm_amount"}.get(year)
        if col is None:
            continue
        txt = (el.text or "").strip()
        if not re.fullmatch(r"-?\d+(\.\d+)?", txt):
            continue
        vals.setdefault((fs, kind, f"{pre}_{name}", names.get(name, "")), {}).setdefault(col, txt)
        # 재무제표 통화 = 자산총계가 적힌 통화 (주석의 외화 금액은 보지 않는다 — 처음엔 모든 사실의 통화를 모아 원화 공시 508행을 잘못 걸었다)
        m = re.search(r"iso4217:([A-Z]{3})", units.get(el.get("unitRef"), ""))
        if m and name == "Assets" and col == "thstrm_amount":
            cur.add(m.group(1))
    out = {}
    for (fs, kind, aid, nm), v in vals.items():
        # 현금흐름표 성격 계정은 손익 계정 후보에서 뺀다 (v2.1 — '이자비용' 라벨의 현금흐름 조정 항목이 금융원가로 잡혔다)
        cf_only = any(k in aid for k in ("CashFlow", "Adjustments", "_CF_"))
        for sj in (("BS",) if kind == "I" else ("CF",) if cf_only else ("IS", "CF")):
            out.setdefault(fs, []).append({"sj_div": sj, "account_id": aid, "account_nm": nm, **v})
    return out, {"인스턴스": inst[0], "기준": sorted(out), "통화": sorted(cur)}


def pick(by_fs):
    """연결 → 별도 → 축 없음 순 (1차의 CFS→OFS 폴백과 같은 원칙). 반환: (행, 기준)."""
    # 자산총계가 있는 기준만 고른다 (v2.1 — 연결 블록에 자산총계가 없어 재무 변수 전체가 비던 행)
    has = lambda rows: any(r["sj_div"] == "BS" and r.get("thstrm_amount") and
                           (r["account_id"] == "ifrs-full_Assets" or r.get("account_nm", "").replace(" ", "") == "자산총계") for r in rows)
    for fs in ("CFS", "OFS", "ND"):
        if by_fs.get(fs) and has(by_fs[fs]):
            return by_fs[fs], fs
    for fs in ("CFS", "OFS", "ND"):
        if by_fs.get(fs):
            return by_fs[fs], fs
    return [], None


if __name__ == "__main__":
    import sys
    rows, meta = parse(open(sys.argv[1], "rb").read(), int(sys.argv[2]))
    print(json.dumps(meta, ensure_ascii=False), {k: len(v) for k, v in rows.items()})
