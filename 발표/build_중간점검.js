// 중간 점검 보고회 — W01~W09 범위만. 수치 출처: docs/20 교정본, SHAP 은 results/w09 (2026-09-14) 파일.
const pptxgen = require("pptxgenjs");
const { applyTheme } = require("/Users/john9/.claude/skills/synced/226f124a-bac7-4e5b-8c55-3e3effd29463_db84adaf-78c1-4c69-b7fb-fbb4351a5370/pptx/scripts/apply_theme.js");

const OUT = process.argv[2] || "deck.pptx";
const THEME = {
  name: "HUP Midterm",
  headFontFace: "Malgun Gothic",
  bodyFontFace: "Malgun Gothic",
  colors: {
    dk1: "15202B", lt1: "FFFFFF", dk2: "4A5260", lt2: "F2F0EB",
    accent1: "B5461A", accent2: "2F5D8A", accent3: "F0A06E", accent4: "8FB3D9",
    accent5: "DDD8CD", accent6: "9AA3AE", hlink: "2F5D8A", folHlink: "6B4E8A",
  },
};
const H = THEME.colors;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.title = "중간 점검 보고회";
pres.author = "팀 종민재";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const W = 13.333, M = 0.6, CW = W - 2 * M;
const FOOT = { y: 6.95, h: 0.3 };

pres.defineSlideMaster({
  title: "COVER",
  background: { color: C.text1 },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: M, y: 0.7, w: CW, h: 0.4, fontSize: 14, bold: true, color: C.accent3, charSpacing: 2 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 2.0, w: CW, h: 2.0, fontSize: 48, bold: true, color: C.background1, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "sub", type: "body", x: M, y: 4.1, w: CW, h: 0.5, fontSize: 20, color: C.accent6 }, text: "" } },
    { placeholder: { options: { name: "team", type: "body", x: M, y: 5.8, w: CW, h: 0.9, fontSize: 16, color: C.background1, valign: "top" }, text: "" } },
  ],
});
const contentObjects = (dark) => [
  { placeholder: { options: { name: "eyebrow", type: "body", x: M, y: 0.45, w: CW, h: 0.35, fontSize: 13, bold: true, color: dark ? C.accent3 : C.accent1, charSpacing: 2, margin: 0 }, text: "" } },
  { placeholder: { options: { name: "title", type: "title", x: M, y: 0.85, w: CW, h: 0.85, fontSize: 32, bold: true, color: dark ? C.background1 : C.text1, valign: "top", align: "left", margin: 0 }, text: "" } },
  { text: { text: "H-UP 12기 · 팀 종민재 · 중간 점검", options: { x: M, y: FOOT.y, w: 6, h: FOOT.h, fontSize: 10, color: dark ? C.accent6 : C.text2, margin: 0 } } },
];
pres.defineSlideMaster({ title: "CONTENT", background: { color: C.background1 }, objects: contentObjects(false),
  slideNumber: { x: W - M - 1, y: FOOT.y, w: 1, h: FOOT.h, fontSize: 10, color: H.dk2, align: "right", margin: 0 } });
pres.defineSlideMaster({ title: "CONTENT_DARK", background: { color: C.text1 }, objects: contentObjects(true),
  slideNumber: { x: W - M - 1, y: FOOT.y, w: 1, h: FOOT.h, fontSize: 10, color: H.accent6, align: "right", margin: 0 } });

// ---- helpers
const TOP = 1.95; // 본문 시작
function content(section, eyebrow, title, notes, dark = false) {
  const s = pres.addSlide({ masterName: dark ? "CONTENT_DARK" : "CONTENT", sectionTitle: section });
  s.addText(eyebrow, { placeholder: "eyebrow" });
  s.addText(title, { placeholder: "title" });
  if (notes) s.addNotes(notes);
  return s;
}
function card(s, x, y, w, h, head, body, opt = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12, fill: { color: opt.fill || C.background2 },
    line: opt.dash ? { color: opt.line || C.accent6, width: 1.5, dashType: "dash" } : { type: "none" }, objectName: `card ${head}` });
  const runs = [];
  if (head) runs.push({ text: head, options: { bold: true, fontSize: opt.headSize || 16, color: opt.headColor || C.text1, breakLine: true, paraSpaceAfter: 8 } });
  for (const [i, b] of body.entries()) runs.push({ text: b, options: { fontSize: opt.size || 16, color: opt.bodyColor || C.text1, breakLine: i < body.length - 1, paraSpaceAfter: 6 } });
  s.addText(runs, { x: x + 0.3, y: y + 0.25, w: w - 0.6, h: h - 0.5, valign: "top", isTextBox: true, margin: 0, objectName: `card text ${head}` });
}
function stat(s, x, y, w, big, label, color) {
  s.addText(big, { x, y, w, h: 1.1, fontSize: 54, bold: true, color: color || C.text1, isTextBox: true, margin: 0, fit: "none", objectName: `stat ${big}` });
  s.addText(label, { x, y: y + 1.15, w, h: 1.0, fontSize: 15, color: C.text2, valign: "top", isTextBox: true, margin: 0 });
}
function table(s, rows, x, y, w, colW, opt = {}) {
  const hl = opt.highlight || [];
  const data = rows.map((r, ri) => r.map((cell, ci) => ({
    text: String(cell),
    options: {
      bold: ri === 0 || hl.includes(ri), color: ri === 0 ? C.text2 : C.text1,
      fill: { color: hl.includes(ri) ? (opt.hlColor || "E3EAF2") : (ri === 0 ? H.lt2 : H.lt1) },
      align: ci === 0 ? "left" : (opt.align || "right"), valign: "middle",
    },
  })));
  s.addTable(data, { x, y, w, colW, fontSize: opt.size || 15, rowH: opt.rowH || 0.48,
    border: { type: "solid", pt: 0.75, color: H.accent5 }, margin: [0.04, 0.12, 0.04, 0.12], objectName: opt.name || "table" });
}
function callout(s, y, text, h = 0.9) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: CW, h, rectRadius: 0.1, fill: { color: "F6E3D8" }, line: { type: "none" }, objectName: "callout" });
  s.addText(text, { x: M + 0.3, y, w: CW - 0.6, h, fontSize: 17, color: C.text1, valign: "middle", isTextBox: true, margin: 0 });
}

// ---- 1 cover
pres.addSection({ title: "문제 설정" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "문제 설정" });
  s.addText("HUFS H-UP 12기 · 중간 점검 보고회", { placeholder: "eyebrow" });
  s.addText("재무제표 기반 부실예측과 그 설명", { placeholder: "title" });
  s.addText("1~9주차 진행 보고 — 사건 정의 · 데이터 · 모델 · SHAP", { placeholder: "sub" });
  s.addText([{ text: "팀 종민재 · 이종민 · 정민재", options: { bold: true, breakLine: true } }, { text: "지도교수 공형우 (Finance&AI 융합학부)", options: { fontSize: 14, color: C.accent6 } }], { placeholder: "team" });
  s.addNotes("[0:00–0:20] 팀 소개. 오늘은 9주차까지 한 것만 보고한다. 설명 충실도 검증·오분류 분석은 남은 일정에서 다룬다.");
}

// ---- 2 why
{
  const s = content("문제 설정", "1 · 문제 설정", "정확도가 아니라 수용성",
    "[0:20–1:20] 부실예측 모델은 여신심사·신용평가에서 이미 쓰인다. 채택 기준은 정확도만이 아니다. 한 줄로: 성능을 올리는 프로젝트가 아니라, 모델이 무엇을 보고 무엇을 못 보는지 규명하는 프로젝트.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 1.9, "실무에서 모델이 쓰이려면", ["\"왜 이 기업이 위험한가\"를 사람이 납득해야 심사 의견서에 인용되고, 그래야 실제로 쓰인다."], { headColor: C.accent1, size: 20 });
  card(s, M + w + 0.4, TOP, w, 1.9, "그래서 이 프로젝트는", ["성능을 올리는 것이 아니라 모델이 무엇을 보고 무엇을 못 보는지 규명한다."], { headColor: C.accent2, size: 20 });
  s.addText("범위 — 국내 상장사 · 2016~2025년 공시분 · 감사의견 비적정 또는 회생절차 개시. 실명 기업의 위험도는 공개하지 않는다.",
    { x: M, y: 4.25, w: CW, h: 0.8, fontSize: 15, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 3 definition (A-1)
pres.addSection({ title: "사건 정의와 시점 정합" });
{
  const sec = "사건 정의와 시점 정합";
  const s = content(sec, "2 · 사건 정의 — 함정 A-1", "답이 문제 안에 들어 있으면 안 된다",
    "[1:20–2:20] 은행은 부채비율 1,000%여도 정상 — 고객 예금이 부채라서. 그래서 업종 더미가 아니라 제외. 12월 결산 사업보고서는 이듬해 3월 말에 나오므로 T는 접수일. A-1은 우리가 발견한 게 아니라 Ohlson(1980)을 따라 막은 것이라고 말한다.");
  const w = (CW - 0.6) / 3;
  card(s, M, TOP, w, 2.0, "주 정의", ["감사의견 비적정(의견거절·부적정·한정) 또는 회생절차 개시 신청"]);
  card(s, M + (w + 0.3), TOP, w, 2.0, "제외", ["금융업 · 스팩·리츠 · 비12월결산 — 비율의 의미가 다르다"]);
  card(s, M + 2 * (w + 0.3), TOP, w, 2.0, "기준시점 T", ["결산일이 아니라 DART 접수일자"]);
  callout(s, 4.3, [
    { text: "감사의견은 그 사업연도 보고서 안에 들어 있다. ", options: { bold: true } },
    { text: "같은 보고서의 재무제표로 그 의견을 맞히면 성능은 완벽하고 결과는 무의미하다.", options: { breakLine: true } },
    { text: "→ 라벨 조건 '사건일 > 기준시점'(등호 없음)을 테스트 코드로 고정. Ohlson(1980)이 이미 다룬 함정이다.", options: { color: C.text2, fontSize: 15 } },
  ], 1.6);
}

// ---- 4 window (A-2)
{
  const s = content("사건 정의와 시점 정합", "2 · 시점 정합 — 함정 A-2", "관행인 12개월 창이 사건의 3분의 1을 지운다",
    "[2:20–3:40] ★ 가장 중요한 장. 계획서엔 관행대로 12개월. 실측하니 제출간격 중앙값 364일. 손실도 무작위가 아니다 — 제출기한 연장은 감사가 제때 안 끝났다는 뜻이고 그 자체가 부실 신호인데, 그런 기업이 창 밖으로 2.4배 더 밀려난다. 평가 구간에서도 365일이면 사건 92건, 400일이면 150건. 예상 질문 '자의적이지 않나' → 실측 근거 + 365·450일 민감도 병기.");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.1, w, "364일", "사업보고서 제출간격 중앙값 — 창이 분포 한가운데를 자른다");
  stat(s, M + w + 0.4, TOP + 0.1, w, "33.7%", "12개월 창을 넘는 관측치 — 그 행의 사건은 어디에도 붙지 않는다");
  stat(s, M + 2 * (w + 0.4), TOP + 0.1, w, "2.4배", "제출기한 연장 기업의 창 초과율 79.8% vs 33.2% — 가장 위험한 기업부터 지워진다", C.accent1);
  callout(s, 5.1, [
    { text: "→ 주 분석 창을 400일로 (1차 면담 확정): 라벨 사건 359건 → " },
    { text: "532건 (+48%)", options: { bold: true } },
    { text: ". 365·450일은 민감도로 병기." },
  ]);
}

// ---- 5 data (A-3)
pres.addSection({ title: "데이터와 성능" });
{
  const s = content("데이터와 성능", "3 · 데이터 — 함정 A-3", "시점 분할: 학습 → 검증 → 평가",
    "[3:40–4:40] 상장사 3,412사, 기업-연도 28,314건 수집. 금융업·스팩·비12월 1,881행 제외 후 23,084행, 사건 532건(2.30%). 사건비율이 학습→평가로 오른다. 2026년 공시분은 400일 관측이 끝나지 않아(2027-04) 쓰지 않는다. 라벨 창 400일이 검증 구간으로 넘어가는 2021년 공시분은 검증 단계 학습에서 뺐다(엠바고) — 넘어가면 검증 시점에는 몰랐을 사건으로 학습하게 된다. 최종 모델은 학습 구간 전체. A-3: 기업 단위 그룹 분할을 하고 싶었지만, 검증 구간 기업의 87%가 학습에도 나온다. 새 기업만 남기면 492건, 사건 2건 — 측정 자체가 불가능.");
  table(s, [
    ["구간", "공시 연도", "관측치", "사건", "사건비율"],
    ["학습 (엠바고)", "2016~2020*", "9,273", "188", "2.03%"],
    ["학습 (최종 모델)", "2016~2021", "11,376", "241", "2.12%"],
    ["검증", "2022~2023", "4,406", "112", "2.54%"],
    ["평가", "2024~2025", "4,805", "150", "3.12%"],
  ], M, TOP, 7.4, [2.1, 1.5, 1.3, 1.1, 1.4], { size: 15, rowH: 0.5 });
  s.addText("* 라벨 창(400일)이 검증 시작 전에 끝나는 행만. 수집 3,412사 · 28,314건 → 최종 23,084행 · 사건 532건 (2.30%).",
    { x: M, y: 4.85, w: 7.4, h: 0.9, fontSize: 14, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
  const x2 = M + 7.9, w2 = CW - 7.9;
  card(s, x2, TOP, w2, 3.1, "기업 단위 분할은 측정 불가", [], { headColor: C.accent1 });
  s.addText("87%", { x: x2 + 0.3, y: TOP + 0.75, w: w2 - 0.6, h: 1.0, fontSize: 54, bold: true, color: C.accent1, isTextBox: true, margin: 0 });
  s.addText("검증 구간 기업 중 학습에도 등장하는 비율. 새 기업만 남기면 492건 · 사건 2건이다.",
    { x: x2 + 0.3, y: TOP + 1.85, w: w2 - 0.6, h: 1.8, fontSize: 16, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
}

// ---- 6 perf
{
  const s = content("데이터와 성능", "3 · 성능", "처음 부실해지는 기업 — 평가 구간 PR-AUC 0.115",
    "[4:40–5:40] 주 분석은 '관측 기간 내 첫 부실' — 예측 시점까지 관측된 부실 이력이 없는 기업. 이유: 평가 구간 사건 150건 중 89건(59%)이 이미 부실을 겪은 기업이라, 전체 성능의 상당 부분이 '아는 위험 기업 다시 찾기'다. 첫 부실 PR-AUC 0.115는 기준선 0.0135의 8.5배 — 순위는 분명하다. 그러나 정밀도 30%를 지키면 61건 중 3건만 잡는다. 전체 표본으로 하면 0.226(7.2배). 정확도는 보고하지 않는다(전부 정상으로 찍어도 96.9%). 이 숫자는 공시 단위 오류를 고친 뒤 기준을 먼저 고정하고 다시 낸 '재평가' 값이다 — 평가 구간을 이미 한 번 열었으므로 독립 검증이 아니다. 2015년 이전 이력은 모른다.");
  s.addText("평가 구간 2024~2025 · 관측 기간 내 첫 부실 4,502건 · 사건 61건 · 데이터 오류 수정 후 재평가", { x: M, y: TOP, w: CW, h: 0.45, fontSize: 14, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
  s.addText("0.115", { x: M, y: TOP + 0.6, w: 5, h: 1.5, fontSize: 88, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
  s.addText("PR-AUC · 95% CI 0.068–0.196 · 기준선의 8.5배", { x: M, y: TOP + 2.15, w: 5.8, h: 0.4, fontSize: 15, color: C.text2, isTextBox: true, margin: 0 });
  s.addChart(pres.charts.BAR, [{ name: "PR-AUC", labels: ["사건비율 기준선", "첫 부실 (주 분석)", "전체 (보조)"], values: [0.0135, 0.115, 0.226] }], {
    x: 6.6, y: TOP, w: CW - 6.0, h: 3.0, barDir: "bar", chartColors: [H.accent6, H.accent2, H.accent5],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 14, dataLabelFontFace: "+mn-lt", dataLabelColor: H.dk1,
    catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 13, catAxisLabelColor: H.dk2, valAxisHidden: true, valAxisMaxVal: 0.28,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, showTitle: false, objectName: "PR-AUC 기준선 대비",
  });
  callout(s, 5.2, "순위는 무작위보다 확실히 낫지만, 정밀도 30%를 지키면 첫 부실 61건 중 3건만 잡는다. 평가 사건의 59%는 이미 부실을 겪은 기업이었다.");
}

// ---- 7 cannot-say
{
  const s = content("데이터와 성능", "3 · 성능 — 설계 비교", "다섯 설계의 우열은 말할 수 없다",
    "[5:40–6:40] ★ 이 장을 빼지 말 것. 검증 구간에서 다섯 설계를 비교했다. 점추정 차이는 있지만 같은 관측치에서 설계 간 차이를 검정하지 않았다 — 신뢰구간이 겹친다는 것만으로는 유의성을 판단할 수 없다. 그래서 우열을 말하지 않는다. 계획서의 매칭 학습은 점추정이 현행보다 낮다(0.313 vs 0.373). 차이 검정을 하지 않았으므로 '나쁘다'고 단정하지 않고 '이득이 확인되지 않았다'로 말한다. 예상 질문 '작은 회사만 찍는 것 아닌가' → 규모 5분위 사건비율 14배 차이, 그래서 매칭을 시도했으나 이득이 없었다.");
  table(s, [
    ["설계 (검증 구간)", "PR-AUC", "95% CI"],
    ["전수 학습 (현행)", "0.373", "0.295–0.476"],
    ["매칭 학습 → 전수 평가 (계획서 설계)", "0.313", "0.231–0.412"],
    ["클래스 가중 없음", "0.268", "0.201–0.368"],
    ["언더샘플링 10:1", "0.378", "0.304–0.483"],
    ["격년 학습", "0.300", "0.235–0.390"],
  ], M, TOP, 7.6, [4.2, 1.4, 2.0], { highlight: [1], size: 15, rowH: 0.5 });
  card(s, M + 8.1, TOP, CW - 8.1, 2.0, "차이 검정은 하지 않았다", ["검증 사건 112건. 점추정 차이만으로 \"A가 B보다 낫다\"고 쓰지 않는다."], { headColor: C.accent1 });
  callout(s, 5.3, "계획서의 매칭 학습은 점추정이 현행보다 낮다 (0.313 vs 0.373) — 이득은 확인되지 않았다. 차이 검정은 하지 않았다.");
}

// ---- 8 trajectory
{
  const s = content("데이터와 성능", "3 · 탐색적 분석", "부실은 3년 전에 이미 보인다",
    "[6:40–7:40] 사건 3년 전에 이미 정상군과 크게 벌어져 있다. 이자보상배율은 3년 전부터 음수 — 영업이익으로 이자를 못 내는 상태가 3년째. 함의 둘: 12개월 예측은 조기 경보라기보다 '이미 나빠진 기업 찾기'에 가깝고, 반대로 그래서 성능이 나온다. 부수 결과: 2주차에 넣은 변화량 변수의 판별력이 수준값의 약 1/50 — 사건 기업은 이미 나쁘고 크게 변하지 않는다.");
  table(s, [
    ["중앙값", "t-3", "t-2", "t-1", "정상군"],
    ["이자보상배율", "−0.30", "−0.80", "−1.14", "+1.94"],
    ["영업이익률", "−8.7%", "−14.8%", "−22.1%", "+3.7%"],
    ["ROA", "−11.7%", "−14.8%", "−19.1%", "+2.0%"],
    ["영업현금흐름/매출", "−6.1%", "−6.6%", "−7.8%", "+5.2%"],
  ], M, TOP, 7.6, [2.8, 1.2, 1.2, 1.2, 1.2], { highlight: [1], hlColor: "F6E3D8", size: 15, rowH: 0.52 });
  const x2 = M + 8.1, w2 = CW - 8.1;
  s.addText("약 50배", { x: x2, y: TOP, w: w2, h: 1.1, fontSize: 54, bold: true, color: C.accent1, isTextBox: true, margin: 0 });
  s.addText("수준값 판별력 ÷ 변화량 판별력 (2년연속영업손실 2.635 vs ΔROA 0.054). 변화가 신호가 아니라 수준이 이미 신호다.",
    { x: x2, y: TOP + 1.15, w: w2, h: 1.6, fontSize: 15, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
  callout(s, 5.2, "12개월 예측은 사실상 \"이미 나빠진 기업 찾기\"다 — 조기 경보로서는 제한적이지만, 재무제표로 성능이 나오는 이유이기도 하다.");
}

// ---- 9 shap-global
pres.addSection({ title: "SHAP과 설명 카드" });
{
  const s = content("SHAP과 설명 카드", "4 · SHAP 전역 기여도", "모델이 가장 많이 보는 것은 수익성과 자본잠식",
    "[7:40–8:40] 평균 |SHAP| 상위 8개. 수익성(ROA·총자산영업이익률)과 자본잠식률이 위. 안정성 필터: 사건 532건이라 시드에 따라 SHAP이 흔들린다. 처음엔 SHAP 평균의 부호가 시드 5개에서 유지되는지 봤는데, 기여도 1위 ROA와 3위 자본잠식률이 탈락했다. SHAP 평균은 기업마다 +/−가 상쇄돼 0 근처 잡음이었다(ROA 평균이 크기의 4%). 카드가 주장하는 건 방향이므로 값↔SHAP 상관의 부호로 바꿨다. 현재 10개 변수가 통과.");
  const vars = ["ROA", "총자산영업이익률", "자본잠식률", "유동비율", "총자산회전율", "자기자본비율", "로그자산", "순이익률"];
  const vals = [0.414, 0.252, 0.223, 0.147, 0.113, 0.076, 0.075, 0.066];
  s.addChart(pres.charts.BAR, [{ name: "평균 |SHAP|", labels: vars.slice().reverse(), values: vals.slice().reverse() }], {
    x: M, y: TOP - 0.1, w: 7.4, h: 4.7, barDir: "bar", chartColors: [H.accent2],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt", dataLabelColor: H.dk1,
    catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 13, catAxisLabelColor: H.dk2, valAxisHidden: true, valAxisMaxVal: 0.5,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "평균 |SHAP| 상위 8개", titleFontFace: "+mn-lt", titleFontSize: 14, titleColor: H.dk2, objectName: "SHAP 전역 기여도",
  });
  card(s, M + 7.9, TOP, CW - 7.9, 4.5, "안정성 필터 — 기준을 한 번 잘못 만들었다", [
    "처음 기준(SHAP 평균의 부호)으로는 기여도 1위 ROA와 3위 자본잠식률이 탈락했다.",
    "SHAP 평균은 기업마다 +/−가 상쇄된 잡음이었다. 카드가 말하는 것은 방향이므로 값↔SHAP 상관의 부호로 바꿨다.",
    "→ 시드 5개에서 방향이 유지되는 10개 변수만 카드에 쓴다.",
  ], { headColor: C.accent1, size: 15 });
}

// ---- 10 shap-check
{
  const s = content("SHAP과 설명 카드", "4 · SHAP 검산", "로지스틱 계수와 방향이 맞는가",
    "[8:40–9:30] 안정 변수 10개 중 9개는 SHAP 방향과 로지스틱 계수 부호가 일치. 어긋난 하나는 Δ부채비율 — 처음엔 '공선성'이라 적었는데 정민재 검토로 틀린 게 드러났다: VIF 1.31로 가장 낮고, 판별력 자체가 없어(0.012) 추정이 불안정한 것. 군집 보정 후 유의하지 않으므로 부호를 논하는 것 자체가 부적절하다. 영업이익률은 VIF 10.21로 ROA와 겹쳐 로지스틱 계수가 반대로 나오는데, 안정성 필터에서도 탈락해 카드에 오르지 않는다. (Shumway 군집 보정: 기업당 4.44년, 유의 변수 20 → 11개)");
  table(s, [
    ["변수", "SHAP 방향", "로지스틱 계수", "일치"],
    ["ROA", "−0.78", "−0.40", "일치"],
    ["총자산영업이익률", "−0.45", "−0.13", "일치"],
    ["자본잠식률", "+0.38", "+0.31", "일치"],
    ["유동비율", "−0.52", "−0.37", "일치"],
    ["총자산회전율", "−0.73", "−0.68", "일치"],
    ["자기자본비율", "−0.75", "−0.53", "일치"],
    ["Δ부채비율", "+0.37", "−0.11", "불일치"],
  ], M, TOP, 7.6, [2.8, 1.6, 1.9, 1.3], { highlight: [7], hlColor: "F6E3D8", size: 14, rowH: 0.47 });
  s.addText("SHAP 방향 = 값과 SHAP의 상관 · 안정 변수 10개 중 일부", { x: M, y: 5.85, w: 7.6, h: 0.35, fontSize: 11, color: C.text2, isTextBox: true, margin: 0 });
  const x2 = M + 8.1, w2 = CW - 8.1;
  s.addText("10개 중 9개 일치", { x: x2, y: TOP, w: w2, h: 0.8, fontSize: 28, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
  card(s, x2, TOP + 1.0, w2, 1.75, "Δ부채비율 (정민재 검토)", ["공선성이 아니라 판별력 부재(0.012). 군집 보정 후 유의하지 않다."], { size: 14 });
  card(s, x2, TOP + 2.95, w2, 1.5, "영업이익률", ["VIF 10.21 — 로지스틱 계수가 반대지만 안정성 필터에서 탈락"], { size: 14 });
}

// ---- 11 card
{
  const s = content("SHAP과 설명 카드", "4 · 설명 카드", "사람이 읽는 문서로 — 설명 카드 예시",
    "[9:30–10:30] 'ROA SHAP +0.34'는 설명이 아니다. 실제 사건 기업(익명, 검증 구간)의 카드. 확률은 isotonic 보정본에서 뽑는다 — 보정 전 모델의 평균 예측이 실제 사건비율의 8.6배였기 때문. 순위는 비보정, 표시 확률은 보정본으로 나눠 쓴다. 위험을 낮춘 요인 칸이 없으면 '해당 없음'이라고 적는다 — 위험 요인만 나열하면 확증 편향 도구가 된다.");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: TOP, w: 7.4, h: 3.7, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: H.accent5, width: 1 }, objectName: "설명 카드" });
  s.addText([
    { text: "익명 사례 · 검증 구간 · 실제 사건 기업", options: { fontSize: 12, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "모형 추정 부실확률 42.0%", options: { fontSize: 22, bold: true, color: C.accent1, breakLine: true, paraSpaceAfter: 10 } },
    { text: "위험을 높인 요인", options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "자본잠식이 진행되어 있습니다 (실측 94.9%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "자산 규모에 비해 벌어들이는 이익이 적습니다 (실측 −29.0%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "순손실 상태입니다 (실측 −72.4%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "1년 내 갚아야 할 돈에 비해 현금화 가능한 자산이 부족합니다 (실측 22.7%)", options: { fontSize: 14, bullet: true, breakLine: true, paraSpaceAfter: 10 } },
    { text: "위험을 낮춘 요인", options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "자산 규모가 표본 중앙값보다 작습니다 (자산 약 251억원)", options: { fontSize: 14, bullet: true } },
  ], { x: M + 0.35, y: TOP + 0.25, w: 6.7, h: 3.2, valign: "top", isTextBox: true, margin: 0, objectName: "카드 문안" });
  const x2 = M + 7.9, w2 = CW - 7.9;
  card(s, x2, TOP, w2, 1.7, "확률은 보정본에서", ["보정 전 평균 예측이 실제 사건비율의 8.6배였다. isotonic 보정으로 Brier 0.089 → 0.020 (검증)."], { size: 14, headColor: C.accent2 });
  card(s, x2, TOP + 2.0, w2, 1.7, "낮춘 요인도 보여준다", ["\"자산이 작다\"가 낮춘 요인에 있다 — 모델이 관측값과 반대로 판단한 지점을 감추지 않는다."], { size: 14, headColor: C.accent2 });
}

// ---- 12 scope
pres.addSection({ title: "남은 일정과 검증 범위" });
{
  const s = content("남은 일정과 검증 범위", "5 · 남은 일정과 검증 범위", "실무자 인터뷰 제외로 확인 범위가 좁아졌다",
    "[10:30–11:30] 지원서의 핵심이던 실무자 6명 블라인드 평가를 진행에서 제외했다. 그래서 '설명이 실무자에게 납득되는가'에는 답할 수 없고, 남은 주차는 '설명이 모델을 정직하게 반영하는가'를 정량으로 검증하는 데 쓴다. 이건 한계가 아니라 하지 않은 일로 보고서에 적는다. 2차 면담 안건: 이 설계 변경이 타당한가.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 1.4, "확인 가능", ["설명이 모델을 정직하게 반영하는가 (충실도)"], { headColor: C.accent2, size: 17 });
  card(s, M + w + 0.4, TOP, w, 1.4, "확인 불가", ["설명이 실무자에게 납득되는가"], { headColor: C.accent1, size: 17, dash: true, fill: C.background1, line: C.accent1 });
  const steps = [["W11", "설명 충실도 정량 검증"], ["W12", "오분류 사례 분석"], ["W13", "재무제표에 담기지 않는 정보"], ["W14", "설명 개선 · 리포트"], ["W15", "성과발표 · 진로 정리"]];
  const sw = (CW - 4 * 0.25) / 5, sy = 4.4;
  steps.forEach(([wk, txt], i) => {
    const x = M + i * (sw + 0.25);
    s.addShape(pres.shapes.OVAL, { x, y: sy, w: 0.7, h: 0.7, fill: { color: C.accent2 }, line: { type: "none" }, objectName: `step ${wk}` });
    s.addText(wk, { x, y: sy, w: 0.7, h: 0.7, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", isTextBox: true, margin: 0 });
    s.addText(txt, { x, y: sy + 0.85, w: sw, h: 0.9, fontSize: 15, color: C.text1, valign: "top", isTextBox: true, margin: 0 });
  });
  s.addText("남은 일정", { x: M, y: 3.9, w: 3, h: 0.35, fontSize: 14, bold: true, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 13 rule-break
{
  const s = content("남은 일정과 검증 범위", "5 · 규칙 위반 신고", "평가 구간을 계획보다 여러 번 열었다",
    "[11:30–12:00] ★ 빼지 말 것. '평가 구간은 최종 1회만 연다'고 정해두고 개발 중 3회 더 열었고, 공시 단위 오류를 고친 뒤 한 번 더 재평가했다(기준을 docs/13에 먼저 고정). 모델 선택·하이퍼파라미터·변수 집합을 평가 구간 결과로 정한 적은 없다. 그래도 본 것은 사실이고, 개봉 기록표를 최종보고서에 그대로 싣는다. 이후 모든 진단·비교는 검증 구간에서만 한다.", true);
  const rows = [
    ["#", "시점", "그 결과로 바꾼 것"],
    ["1", "첫 학습 직후", "없음 (배선 확인)"],
    ["2", "윈저라이즈 수정 후", "없음 — 수정 근거는 학습 구간 진단"],
    ["3", "결측 더미 절제 실험", "없음 — 잘못이므로 검증 구간에서 재실행"],
    ["4", "최종 모델 확정 후 (계획된 1회)", "—"],
    ["5", "데이터 오류 수정 후 재평가", "없음 — 기준을 먼저 문서로 고정"],
  ].map((r, ri) => r.map((cell, ci) => ({ text: cell, options: { bold: ri === 0, color: ri === 0 ? H.accent6 : H.lt1, fill: { color: ri === 0 ? "1F2C3A" : H.dk1 }, align: "left", valign: "middle" } })));
  s.addTable(rows, { x: M, y: TOP, w: CW, colW: [0.8, 4.2, CW - 5.0], fontSize: 15, rowH: 0.45,
    border: { type: "solid", pt: 0.75, color: "3A4757" }, margin: [0.04, 0.12, 0.04, 0.12], objectName: "개봉 기록" });
  s.addText("감추면 위반이고, 밝히면 한계 기술이다.", { x: M, y: 5.0, w: CW, h: 0.8, fontSize: 28, bold: true, color: C.accent3, isTextBox: true, margin: 0 });
  s.addText("모델 선택·하이퍼파라미터·변수 집합을 평가 구간 결과로 정한 적은 없다. 이후 모든 비교는 검증 구간에서만 한다.",
    { x: M, y: 5.8, w: CW, h: 0.7, fontSize: 15, color: C.accent6, isTextBox: true, margin: 0 });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
