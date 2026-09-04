"""DART Open API 클라이언트.

일 20,000건 한도가 있어서 이 파일의 본체는 API 호출이 아니라 캐시다.
같은 요청은 두 번 나가지 않고, 결과가 없는 응답('013')도 캐시한다.
한도를 넘기면 QuotaExceeded 로 즉시 멈춘다 — 조용히 빈 값을 돌려주면
며칠 뒤에 구멍 난 데이터셋을 발견하게 된다.
"""
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

from . import config

BASE = "https://opendart.fss.or.kr/api/"
SLEEP = 0.05
TRIES = 6

# 실제로 나간 호출 수. 진행 로그의 '호출'은 순회 횟수라 캐시 적중분까지 세서
# 일일 한도(20,000)와 맞지 않는다. 한도까지 얼마나 남았는지는 이 값으로 본다.
CALLS = 0


def _open(url, timeout=30):
    """일시적 네트워크 오류는 물러섰다가 다시 친다.

    2026-09-03 두 번 데였다.
      1. 재시도가 없어서 타임아웃 한 번에 수집 프로세스 두 개가 모두 죽었다.
      2. 응답이 전송 중 잘려서 JSONDecodeError 로 죽었다 — read() 는 부분 데이터를
         조용히 돌려준다. 그래서 **JSON 파싱 실패도 네트워크 실패로 취급**한다.
    3일짜리 수집에서 한 번의 실패로 전부 멈추면 안 된다.
    한도 초과(status 020)는 정상 응답 본문에 담겨 오므로 여기서 걸리지 않는다.
    """
    import http.client
    for i in range(TRIES):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as e:
            if i == TRIES - 1:
                raise DartError(f"{TRIES}회 재시도 실패: {type(e).__name__} {e}") from e
            time.sleep(2 ** i)          # 1,2,4,8,16초


def _open_json(url, timeout=30):
    """_open + JSON 파싱. 잘린 응답은 다시 받는다."""
    for i in range(TRIES):
        try:
            return json.loads(_open(url, timeout).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            if i == TRIES - 1:
                raise DartError(f"응답이 계속 잘린다: {e}") from e
            time.sleep(2 ** i)


def _write_cache(path, obj):
    """원자적 쓰기. 프로세스가 중간에 죽어도 반쯤 쓰인 캐시가 남지 않는다."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False))
    tmp.replace(path)


def _read_cache(path):
    """깨진 캐시는 지우고 없는 셈 친다. 안 그러면 그 항목은 영원히 실패한다."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        path.unlink(missing_ok=True)
        return None


class DartError(RuntimeError):
    pass


class QuotaExceeded(DartError):
    pass


def _cache_file(path, params):
    key = path + "?" + urllib.parse.urlencode(sorted(params.items()))
    safe = key.replace("/", "_").replace("?", "__").replace("&", "_").replace("=", "-")
    return config.CACHE / (safe[:180] + ".json")


def get(path, **params):
    """JSON 엔드포인트 호출. 결과 없음은 빈 리스트를 돌려준다."""
    if not config.DART_KEY:
        raise DartError("DART_API_KEY 가 비어 있다. .env 를 확인할 것")
    cf = _cache_file(path, params)
    if cf.exists():
        hit = _read_cache(cf)
        if hit is not None:
            return hit

    global CALLS
    url = BASE + path + "?" + urllib.parse.urlencode({"crtfc_key": config.DART_KEY, **params})
    body = _open_json(url)
    CALLS += 1
    time.sleep(SLEEP)

    status = body.get("status")
    if status == "020":
        raise QuotaExceeded("일일 호출 한도 초과. 내일 이어서 수집할 것 (캐시는 남아 있다)")
    if status == "800":
        raise DartError("DART 시스템 점검 중")
    if status not in ("000", "013"):
        raise DartError(f"{path} status={status} {body.get('message')}")

    out = body.get("list", []) if status == "000" else []
    _write_cache(cf, out)
    return out


def corp_codes():
    """전체 고유번호 목록. zip(xml) 한 번만 받아서 캐시한다."""
    cf = config.RAW / "corp_codes.json"
    if cf.exists():
        hit = _read_cache(cf)
        if hit is not None:
            return hit
    url = BASE + "corpCode.xml?" + urllib.parse.urlencode({"crtfc_key": config.DART_KEY})
    blob = _open(url, timeout=120)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        xml = z.read(z.namelist()[0])
    rows = [{c.tag: (c.text or "").strip() for c in el}
            for el in ET.fromstring(xml).findall("list")]
    rows = [r for r in rows if r.get("stock_code")]   # 상장 이력이 있는 건만
    _write_cache(cf, rows)
    return rows


def company(corp_code):
    """기업개황 — 업종코드(induty_code)가 금융업 제외에 필요하다."""
    if not config.DART_KEY:
        raise DartError("DART_API_KEY 가 비어 있다")
    global CALLS
    cf = _cache_file("company.json", {"corp_code": corp_code})
    if cf.exists():
        hit = _read_cache(cf)
        if hit is not None:
            return hit
    url = BASE + "company.json?" + urllib.parse.urlencode(
        {"crtfc_key": config.DART_KEY, "corp_code": corp_code})
    body = _open_json(url)
    CALLS += 1
    time.sleep(SLEEP)
    if body.get("status") == "020":
        raise QuotaExceeded("일일 호출 한도 초과")
    out = body if body.get("status") == "000" else {}
    _write_cache(cf, out)
    return out


def financials(corp_code, year, fs_div=None):
    """단일회사 전체 재무제표 (사업보고서 기준). 반환: (rows, 기준)

    연결(CFS) 이 비면 별도(OFS) 로 다시 받는다.

    2026-09-03 실측: CFS 응답의 **25.1%가 비어 있다**(12,080건 중 3,030건, 490개사).
    연결 대상이 없어 별도만 제출하는 기업들이다. 폴백이 없으면 이들이 패널에서
    통째로 사라지는데, 이 누락은 무작위가 아니다 — 자회사가 없는 기업은 대체로 소형이고
    부실이 몰려 있는 쪽이다. 표본이 조용히 대형주 쪽으로 치우친다.

    연결과 별도를 섞으므로 어느 기준인지 컬럼으로 남기고 보고서에 명시한다.
    """
    if fs_div:
        return get("fnlttSinglAcntAll.json", corp_code=corp_code, bsns_year=str(year),
                   reprt_code=config.REPRT_ANNUAL, fs_div=fs_div), fs_div
    for div in (config.FS_DIV, "OFS"):
        rows = get("fnlttSinglAcntAll.json", corp_code=corp_code, bsns_year=str(year),
                   reprt_code=config.REPRT_ANNUAL, fs_div=div)
        if rows:
            return rows, div
    return [], None


def audit_opinion(corp_code, year):
    """회계감사인의 명칭 및 감사의견.

    당기·전기·전전기 3개 행이 **같은 rcept_no 로** 온다. 당기만 써야 한다
    (labels.current_period). 강조사항·핵심감사사항도 이 응답에 함께 들어 있다.
    """
    return get("accnutAdtorNmNdAdtOpinion.json", corp_code=corp_code,
               bsns_year=str(year), reprt_code=config.REPRT_ANNUAL)


def _list_body(params):
    """list.json 전용. `total_page` 가 필요해서 응답 **전체**를 캐시한다.

    2026-09-03 실측: DART 는 total_page 를 넘겨도 오류를 주지 않고
    **마지막 페이지를 계속 돌려준다.** page 50 과 page 200 의 첫 행이 같다.
    그래서 'rows < 100 이면 끝'이라는 종료 조건은 영원히 참이 되지 않는다.
    같은 행을 중복으로 쌓으면서 호출만 태운다.
    """
    global CALLS
    cf = _cache_file("list_full.json", params)
    if cf.exists():
        hit = _read_cache(cf)
        if hit is not None:
            return hit
    url = BASE + "list.json?" + urllib.parse.urlencode({"crtfc_key": config.DART_KEY, **params})
    body = _open_json(url)
    CALLS += 1
    time.sleep(SLEEP)
    status = body.get("status")
    if status == "020":
        raise QuotaExceeded("일일 호출 한도 초과. 내일 이어서 수집할 것 (캐시는 남아 있다)")
    if status not in ("000", "013"):
        raise DartError(f"list.json status={status} {body.get('message')}")
    out = {"list": body.get("list", []) if status == "000" else [],
           "total_page": int(body.get("total_page") or 0),
           "total_count": int(body.get("total_count") or 0)}
    _write_cache(cf, out)
    return out


def disclosures(bgn_de, end_de, corp_code=None, pblntf_ty=None,
                page_no=1, page_count=100, last_reprt_at="N", **kw):
    """공시검색.

    last_reprt_at 기본값이 "N"(전체 보고서)인 이유 — 2026-09-03 실측:

      2023년 1분기 주요사항보고  Y: 864건 중 회생절차 5건
                                N: 1,526건 중 회생절차 **6건**

    Y(최종보고서만)로 조회하면 디엘팜의 2023-03-16 회생절차개시신청이 통째로 사라진다.
    한 분기에 6건 중 1건이다. 주 사건 유형에서 이 비율로 새면 라벨이 무너진다.

    같은 이유로 사업보고서 기준시점도 N 으로 받아야 한다. Y 는 정정·첨부추가본만 남겨서
    '최초 접수일'을 구하면 정정본 날짜가 나온다 — 정보가 실제로 공개된 날보다 늦다.
    중복은 호출부에서 min(rcept_dt) 로 정리한다.
    """
    p = dict(bgn_de=bgn_de, end_de=end_de, page_no=str(page_no),
             page_count=str(page_count), last_reprt_at=last_reprt_at)
    if corp_code:
        p["corp_code"] = corp_code
    if pblntf_ty:
        p["pblntf_ty"] = pblntf_ty
    p.update({k: v for k, v in kw.items() if v is not None})
    return _list_body(p)


def _quarters(bgn_de, end_de):
    """corp_code 없이 공시검색을 하면 검색기간이 3개월로 제한된다(status 100).
    긴 구간은 분기로 잘라 준다."""
    import datetime as dt
    b = dt.date(int(bgn_de[:4]), int(bgn_de[4:6]), int(bgn_de[6:]))
    e = dt.date(int(end_de[:4]), int(end_de[4:6]), int(end_de[6:]))
    while b <= e:
        m = b.month + 3
        y, m = b.year + (m - 1) // 12, (m - 1) % 12 + 1
        nxt = dt.date(y, m, 1) - dt.timedelta(days=1)
        yield b.strftime("%Y%m%d"), min(nxt, e).strftime("%Y%m%d")
        b = min(nxt, e) + dt.timedelta(days=1)


def disclosures_all(bgn_de, end_de, corp_code=None, **kw):
    """페이지를 끝까지 넘긴다. corp_code 가 없으면 분기로 잘라 돈다."""
    spans = [(bgn_de, end_de)] if corp_code else list(_quarters(bgn_de, end_de))
    out = []
    for b, e in spans:
        first = disclosures(b, e, corp_code=corp_code, page_no=1, **kw)
        out += first["list"]
        for page in range(2, first["total_page"] + 1):     # total_page 를 넘기면 안 된다
            out += disclosures(b, e, corp_code=corp_code, page_no=page, **kw)["list"]
    return out


_FY = re.compile(r"사업보고서\s*\((\d{4})\.(\d{2})\)")


def annual_filers(filing_years):
    """{corp_code: [(사업연도, 결산월, 접수일자), ...]}

    report_nm 에서 사업연도를 뽑는다 — '[첨부추가]사업보고서 (2023.12)' → (2023, 12).
    접수연도로 대신하면 데이터가 한 해씩 밀린다.
    """
    out, skipped = {}, 0
    for y in filing_years:
        for d in disclosures_all(f"{y}0101", f"{y}1231", pblntf_detail_ty="A001"):
            m = _FY.search(d.get("report_nm", ""))
            if not m:
                skipped += 1
                continue
            out.setdefault(d["corp_code"], []).append(
                (int(m.group(1)), int(m.group(2)), d["rcept_dt"]))
    if skipped:
        print(f"  report_nm 형식 불일치로 건너뜀: {skipped}건", flush=True)
    return out


def universe(years=None):
    """상장사 × 실제 사업보고서 제출 사업연도.

    반환: {corp_code: {bsns_year: {"rcept_dt": "YYYYMMDD", "fy_month": 12}}}

    2026-09-03 실측 두 가지가 여기 반영돼 있다.
      1. corp_codes 는 3,988개(폐지 종목 포함)인데 2024년 실제 제출 상장사는 2,769개다.
         필터 없이 돌면 호출의 절반이 빈 응답에 쓰인다.
      2. **접수연도 ≠ 사업연도.** 2024년 3월 접수분은 FY2023 이다.
    """
    years = list(years or config.YEARS)
    cf = config.RAW / f"universe_{years[0]}_{years[-1]}.json"
    if cf.exists():
        hit = _read_cache(cf)
        if hit is not None:
            return hit
    listed = {r["corp_code"] for r in corp_codes()}
    # FY t 사업보고서는 t+1 년에 접수된다. 결산월 변경분까지 보려고 +2 까지 훑는다.
    filed = annual_filers(range(years[0], years[-1] + 3))
    out = {}
    for cc, recs in filed.items():
        if cc not in listed:
            continue
        for fy, mm, rcept in recs:
            if fy not in years:
                continue
            slot = out.setdefault(cc, {})
            cur = slot.get(fy)
            # 정정·첨부추가본이 여러 건 온다. 정보가 처음 공개된 날이 기준시점이다.
            if cur is None or rcept < cur["rcept_dt"]:
                slot[fy] = {"rcept_dt": rcept, "fy_month": mm}
    _write_cache(cf, out)
    return out


_EXT = re.compile(r"사업보고서제출기한연장신고서\s*\((\d{4})\.(\d{2})\)")


def extension_filers(filing_years):
    """사업보고서 제출기한 연장신고 이력.  {(corp_code, 사업연도): 최초 신고일}

    2026-09-03: `annual_filers` 가 report_nm 형식 불일치로 버린 395건 중 394건이
    이것이었다. 버려도 되는 잡음인 줄 알았는데 아니다.

    제출기한을 연장한다는 것은 감사가 예정대로 끝나지 않았다는 뜻이다.
    그리고 이건 재무비율에 전혀 안 잡힌다 — 13주차 '담기지 않는 정보' 후보다.

    A-2 와도 직접 연결된다. 연장한 기업은 다음 보고서까지 간격이 365일을 넘어
    12개월 창에서 사건이 통째로 누락되는 바로 그 집단일 가능성이 크다.
    즉 우리가 놓치는 사건이 무작위가 아니라는 증거가 될 수 있다.
    """
    out = {}
    for y in filing_years:
        for d in disclosures_all(f"{y}0101", f"{y}1231", pblntf_detail_ty="A001"):
            m = _EXT.search(d.get("report_nm", ""))
            if not m:
                continue
            k = (d["corp_code"], int(m.group(1)))
            if k not in out or d["rcept_dt"] < out[k]:
                out[k] = d["rcept_dt"]
    return out
