// 중간 점검 보고회 (설계 → 진행 → 남은 계획, 10분) — 수치 출처: docs/10 (2026-10-13 판, 라벨 오류 수정 후 재평가). 대표 그림: results/final/대표그림.png
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
pres.addSection({ title: "연구 설계" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "연구 설계" });
  s.addText("HUFS H-UP 12기 · 중간 점검 보고회", { placeholder: "eyebrow" });
  s.addText("부실 예측 AI는 무엇을 맞히고,\n그 설명은 어디까지 믿을 수 있는가", { placeholder: "title" });
  s.addText("국내 상장기업 재무제표 기반 부실 예측과 설명 검증 — 설계 · 진행 · 남은 계획", { placeholder: "sub" });
  s.addText([{ text: "팀 종민재 · 이종민 · 정민재", options: { bold: true, breakLine: true } }, { text: "지도교수 공형우 (Finance&AI 융합학부)", options: { fontSize: 14, color: C.accent6 } }], { placeholder: "team" });
  s.addNotes("[0:00–0:15] 팀 소개. 오늘은 처음에 어떻게 설계했고, 중간 점검 시점까지 어디까지 했고, 남은 기간에 무엇을 도출할지 순서로 말씀드린다.");
}

// ---- 2 question
{
  const s = content("연구 설계", "1 · 연구 질문", "성능보다 '무엇을 맞히고, 왜 그렇게 판단했는가'",
    "[0:15–1:05] 부실 예측 모델은 여신심사·신용평가에서 이미 쓰이고, 실무와 규제는 '왜 이 기업이 위험한가'를 설명하라고 요구한다. 그래서 두 질문을 세웠다. ① 모델이 실제로 맞히는 것이 무엇인가 — 처음 부실해지는 기업인가, 이미 부실을 겪은 기업인가. ② 모델이 내놓은 설명을 믿을 수 있는가 — 모델의 실제 근거를 반영하는가, 재무 사실과 맞는가. 최종 산출물은 부실 위험 순위와, 사람이 읽는 설명 카드다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 2.3, "① 무엇을 맞히는가", ["모델이 잡아내는 것은 처음 부실해지는 기업인가, 이미 부실을 겪은 기업인가"], { headColor: C.accent2, size: 18 });
  card(s, M + w + 0.4, TOP, w, 2.3, "② 설명을 믿을 수 있는가", ["설명이 모델의 실제 근거를 반영하는가, 재무 사실과 맞는가"], { headColor: C.accent1, size: 18 });
  callout(s, 4.6, [
    { text: "최종 산출물 — ", options: { bold: true } },
    { text: "DART 공시만으로 만든 부실 위험 순위 + 위험 요인을 실측값과 함께 문장으로 설명하는 '설명 카드'" },
  ], 1.0);
  s.addText("범위 — 국내 상장사 · 2016~2025년 공시 · 부실 = 감사의견 비적정 또는 회생절차 개시", { x: M, y: 5.85, w: CW, h: 0.4, fontSize: 13, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 3 roadmap
{
  const s = content("연구 설계", "1 · 처음 설계", "15주 계획 — 지금은 10주차 중간 점검",
    "[1:05–2:00] 15주를 다섯 단계로 짰다. 1~4주차 사건 정의와 데이터 수집, 5~6주차 변수와 탐색 분석, 7~8주차 모델, 9~10주차 SHAP과 설명 카드 설계, 11~15주차는 설명 검증과 개선, 그리고 정리. 지금은 10주차 중간 점검이다. 계획한 1~10주차 항목은 모두 진행했고, 남은 것은 11~15주차의 검증·개선·정리다.");
  const phases = [
    ["W1–4", "사건 정의 · 수집", "부실 정의 확정, DART 재무제표·감사의견 수집, 라벨링"],
    ["W5–6", "변수 · 탐색", "재무비율 27개, 사건 전 3년 궤적"],
    ["W7–8", "모델", "로지스틱 기준 모델 → 앙상블, 시점 분할"],
    ["W9–10", "SHAP · 설명 카드", "변수 기여도, 설명 카드 설계"],
    ["W11–15", "검증 · 개선 · 정리", "설명 충실도, 오분류, 담기지 않는 정보, 성과발표"],
  ];
  const n = phases.length, gap = 0.15, w = (CW - gap * (n - 1)) / n, y = TOP + 0.35;
  phases.forEach(([wk, h, b], i) => {
    const x = M + i * (w + gap), done = i < 4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 2.6, rectRadius: 0.1, fill: { color: done ? "E3EAF2" : C.background1 },
      line: done ? { type: "none" } : { color: H.accent1, width: 1.5, dashType: "dash" }, objectName: `단계 ${wk}` });
    s.addText([
      { text: wk, options: { fontSize: 14, bold: true, color: done ? C.accent2 : C.accent1, breakLine: true, paraSpaceAfter: 4 } },
      { text: h, options: { fontSize: 16, bold: true, color: C.text1, breakLine: true, paraSpaceAfter: 10 } },
      { text: b, options: { fontSize: 14, color: C.text2 } },
    ], { x: x + 0.2, y: y + 0.2, w: w - 0.4, h: 2.6, valign: "top", isTextBox: true, margin: 0 });
  });
  const mx = M + 4 * (w + gap) - gap / 2;
  s.addShape(pres.shapes.LINE, { x: mx, y: y - 0.3, w: 0, h: 3.2, line: { color: H.accent1, width: 2.5 }, objectName: "현재 위치" });
  s.addText("지금 (중간 점검)", { x: mx - 1.6, y: y - 0.62, w: 3.2, h: 0.3, fontSize: 13, bold: true, color: C.accent1, align: "center", isTextBox: true, margin: 0 });
  s.addText("■ 완료    ┅ 남은 단계", { x: M, y: 5.5, w: CW, h: 0.4, fontSize: 13, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 4 design principles
{
  const s = content("연구 설계", "1 · 설계 원칙", "미래 정보를 쓰지 않도록 시점부터 고정했다",
    "[2:00–3:00] 설계에서 가장 신경 쓴 것은 시점이다. 기준시점 T는 결산일이 아니라 사업보고서 최초 접수일 — 그날 실제로 볼 수 있던 정보만 쓴다. 감사의견은 그 보고서 안에 있으니, 같은 보고서로 같은 해 의견을 맞히면 동어반복이다. 그래서 라벨은 T 이후 400일 안의 사건이다. 관행인 12개월 대신 400일을 쓴 이유는 하나 — 제출 간격 중앙값이 364일이라 12개월이면 다음 해 감사의견의 3분의 1이 창 밖으로 밀린다(400일이면 0.3%). 데이터는 연도 순으로 학습·검증·평가로 나눴고, 평가 구간은 마지막에만 본다. 지표는 정확도가 아니라 PR-AUC — 사건비율이 2~3%라 전부 정상이라고 찍어도 정확도가 97%다.");
  const w = (CW - 0.8) / 3;
  card(s, M, TOP, w, 2.6, "기준시점 = 최초 접수일", ["그날 실제로 볼 수 있던 정보만 쓴다. 라벨은 T 이후 400일 안의 부실 사건"], { headColor: C.accent2, size: 16 });
  card(s, M + w + 0.4, TOP, w, 2.6, "예측 창 400일", ["12개월이면 다음 해 감사의견의 33.7%가 창 밖으로 밀린다 → 400일이면 0.3%"], { headColor: C.accent2, size: 16 });
  card(s, M + 2 * (w + 0.4), TOP, w, 2.6, "지표는 PR-AUC", ["사건비율 2~3% — 전부 정상이라 찍어도 정확도 97%. 정확도는 보고하지 않는다"], { headColor: C.accent2, size: 16 });
  table(s, [
    ["구간", "공시 연도", "관측치", "사건", "사건비율"],
    ["학습", "2016~2021", "11,376", "261", "2.29%"],
    ["검증", "2022~2023", "4,406", "120", "2.72%"],
    ["평가 (마지막에만)", "2024~2025", "4,805", "158", "3.29%"],
  ], M, 4.75, CW, [3.4, 2.4, 2.1, 2.0, 2.2], { size: 14, rowH: 0.4 });
}

// ---- 5 progress: data
pres.addSection({ title: "중간 점검까지 진행" });
{
  const s = content("중간 점검까지 진행", "2 · 진행 ① 데이터 · 탐색 (W1–6)", "상장사 10년치 공시로 분석용 데이터를 만들었다",
    "[3:00–3:50] DART에서 상장사 3,412곳, 기업-연도 28,314건을 모았다. 금융업·스팩·비12월결산을 빼고 23,084행, 부실 사건 548건(2.37%)이다. 재무비율 27개를 만들었다. 탐색 분석에서 본 것 하나 — 부실 기업은 사건 3년 전부터 이미 나빴다. 이자보상배율 중앙값이 3년 전부터 음수다(정상 기업 +1.94). 사후 기술이라 예측력의 증거는 아니지만, 1년 남짓한 예측은 '이미 나빠진 기업 찾기'에 가깝다는 뜻이다.");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.05, w, "3,412곳", "DART 상장사 · 기업-연도 28,314건 수집 (2016~2025 공시)", C.accent2);
  stat(s, M + w + 0.4, TOP + 0.05, w, "23,084행", "금융업·스팩·비12월결산 제외 후 분석 표본 · 재무비율 27개", C.accent2);
  stat(s, M + 2 * (w + 0.4), TOP + 0.05, w, "548건", "부실 사건 (2.37%) — 감사의견 비적정 또는 회생절차 개시", C.accent1);
  callout(s, 4.55, [
    { text: "탐색 결과 — 부실 기업은 사건 3년 전부터 이미 나빴다. ", options: { bold: true } },
    { text: "이자보상배율 중앙값 t-3 −0.30 · t-1 −1.02 (정상 기업 +1.94). 사후 중앙값이라 예측력의 증거는 아니다." },
  ], 1.2);
}

// ---- 6 progress: model
{
  const s = content("중간 점검까지 진행", "2 · 진행 ② 모델 (W7–8)", "모델 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다",
    "[3:50–5:20] ★ 핵심. 로지스틱 기준 모델에서 앙상블로 갔다. 오른쪽 평가 구간 — 전체 PR-AUC 0.227, 무작위의 6.9배다. 그런데 평가 사건 158건 중 107건(68%)이 이미 부실을 겪은 기업이다. 과거 부실 여부 하나만으로도 꽤 맞힌다. 그래서 '관측 기간 안에서 처음 부실해지는 기업'을 주 분석으로 정했다(검증 구간 근거로 결정). 처음 부실해지는 기업에서는 PR-AUC 0.091, 무작위의 8.0배 — 순위는 낫지만 정밀도 30%를 지키면 51건 중 1건만 잡는다. 이게 첫 질문 '무엇을 맞히는가'에 대한 중간 답이다. 평가 수치는 데이터 오류를 고친 뒤 기준을 먼저 고정하고 다시 낸 값이라 독립 검증은 아니다(부록 A1).");
  s.addImage({ path: "/Users/john9/Desktop/h-up/project/results/final/대표그림.png", x: 1.65, y: 1.7, w: 10.0, h: 4.36, objectName: "대표 그림" });
  s.addText([
    { text: "중간 답 — 처음 부실해지는 기업: PR-AUC 0.091 (무작위의 8.0배), 정밀도 30%에서 51건 중 1건", options: { bold: true, color: C.accent2, breakLine: true } },
    { text: "평가 수치는 오류 수정 후 재평가 값 (독립 검증 아님 · 부록 A1)", options: { fontSize: 13, color: C.text2 } },
  ], { x: M, y: 6.08, w: CW, h: 0.8, fontSize: 16, isTextBox: true, margin: 0, valign: "top" });
}

// ---- 7 progress: SHAP + card
{
  const s = content("중간 점검까지 진행", "2 · 진행 ③ SHAP · 설명 카드 (W9–10)", "모델의 근거를 사람이 읽는 문장으로 옮겼다",
    "[5:20–6:40] SHAP으로 모델이 무엇을 보는지 쟀다. 1위는 ROA, 2위 총자산영업이익률 — 수익성이다. 시드를 바꿔도 방향이 유지되는 12개 변수만 남기고, 그중 8개를 문장으로 만든다. 카드 변수 8개는 로지스틱 계수와 방향이 모두 맞다. 오른쪽이 설명 카드다. 실측값을 함께 적고, 위험을 낮춘 요인이 없으면 '해당 없음'이라고 적는다. 카드를 설계하면서 검사 규칙도 넣었다 — 실측값이 절대 기준을 넘을 때만 '자본잠식이 진행' 같은 단정을 쓰고, 근거가 불안정하면 설명 대신 보류 사유를 낸다.");
  const vars = ["ROA", "총자산영업이익률", "유동비율", "자본잠식률", "로그자산", "순이익률"];
  const vals = [0.380, 0.362, 0.167, 0.165, 0.156, 0.146];
  s.addChart(pres.charts.BAR, [{ name: "평균 |SHAP|", labels: vars.slice().reverse(), values: vals.slice().reverse() }], {
    x: M, y: TOP - 0.1, w: 5.4, h: 3.9, barDir: "bar", chartColors: [H.accent2],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt", dataLabelColor: H.dk1,
    catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 13, catAxisLabelColor: H.dk2, valAxisHidden: true, valAxisMaxVal: 0.48,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "모델이 많이 보는 변수 (평균 |SHAP|)", titleFontFace: "+mn-lt", titleFontSize: 14, titleColor: H.dk2, objectName: "SHAP 전역 기여도",
  });
  s.addText("안정 변수 12개 중 8개를 카드 문장으로 · 카드 변수 8개 모두 로지스틱 계수와 방향 일치", { x: M, y: 5.85, w: 5.4, h: 0.6, fontSize: 13, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
  const x2 = M + 5.8, w2 = CW - 5.8;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x2, y: TOP, w: w2, h: 4.4, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: H.accent5, width: 1 }, objectName: "설명 카드" });
  s.addText([
    { text: "설명 카드 · 익명 사례 · 검증 구간 실제 사건 기업", options: { fontSize: 12, color: C.text2, breakLine: true, paraSpaceAfter: 6 } },
    { text: "모형 추정 부실확률 55.5%", options: { fontSize: 24, bold: true, color: C.accent1, breakLine: true, paraSpaceAfter: 12 } },
    { text: "위험을 높인 요인", options: { fontSize: 14, bold: true, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "자본잠식이 진행되어 있습니다 (실측 94.9%)", options: { fontSize: 19, bullet: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "자산 규모에 비해 벌어들이는 이익이 적습니다 (실측 −29.0%)", options: { fontSize: 19, bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "위험을 낮춘 요인", options: { fontSize: 14, bold: true, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "해당 없음", options: { fontSize: 17, bullet: true, breakLine: true, paraSpaceAfter: 12 } },
    { text: "검사 규칙 — 실측값이 기준을 넘을 때만 단정 · 근거가 불안정하면 설명 대신 보류 사유", options: { fontSize: 13, color: C.accent2, bold: true } },
  ], { x: x2 + 0.3, y: TOP + 0.25, w: w2 - 0.6, h: 4.0, valign: "top", isTextBox: true, margin: 0, objectName: "카드 문안" });
}

// ---- 8 checkpoint vs plan
{
  const s = content("중간 점검까지 진행", "2 · 계획 대비 진척", "계획한 10주차까지는 모두 진행했다",
    "[6:40–7:30] 계획 대비로 보면 1~10주차 항목은 모두 진행했다. 진행하면서 계획에서 바뀐 것이 셋 있다. 실무자 인터뷰를 제외해 '실무자가 납득하는가'는 확인하지 않고, '설명이 모델과 사실에 충실한가'로 검증 범위를 좁혔다. 주 분석을 처음 부실해지는 기업으로 정했다. 계획서의 매칭 학습은 검증 구간에서 이득을 확인하지 못해 전수 학습으로 갔다. 2차 면담에서 이 세 가지를 보고한다.");
  table(s, [
    ["주차", "계획", "상태"],
    ["W1–4", "사건 정의 · DART 수집 · 라벨링", "완료"],
    ["W5–6", "재무비율 27개 · 탐색 분석", "완료"],
    ["W7–8", "기준 모델 · 앙상블 · 시점 분할", "완료"],
    ["W9–10", "SHAP 기여도 · 설명 카드 설계", "완료 (2차 면담 예정)"],
  ], M, TOP, 7.4, [1.2, 3.7, 2.5], { size: 15, rowH: 0.52, align: "left" });
  const x2 = M + 7.8, w2 = CW - 7.8;
  card(s, x2, TOP, w2, 3.4, "계획에서 바뀐 것", [
    "실무자 인터뷰 제외 → 검증 범위를 '설명이 모델과 재무 사실에 충실한가'로 한정",
    "주 분석 = 처음 부실해지는 기업 (반복 부실은 보조)",
    "매칭 학습 → 전수 학습 (검증 구간에서 이득 미확인)",
  ], { headColor: C.accent1, size: 15 });
}

// ---- 9 remaining + expected results
pres.addSection({ title: "남은 계획" });
{
  const s = content("남은 계획", "3 · 남은 단계와 도출할 결과", "11~15주차 — 설명을 검증하고, 개선하고, 정리한다",
    "[7:30–8:50] 남은 다섯 주의 계획이다. 11주차 설명 충실도 — 카드가 짚은 변수를 지우면 위험이 실제로 떨어지는지, 무작위 변수와 비교해 수치로 보인다. 12주차 오분류 — 모델이 놓친 기업과 잘못 짚은 기업이 어떤 유형인지 정리한다. 13주차 담기지 않는 정보 — 계속기업 불확실성이나 제출기한 연장 같은 공시 신호가 재무비율 위에 정보를 더하는지 본다. 14주차 설명 개선 — 검증 결과로 카드 문안과 보류 규칙을 고치고 전후를 비교한다. 15주차에는 정상·교정·보류 세 사례 시연과 최종보고서, 진로 판단으로 마무리한다. 함께 확인할 한계는 정정된 재무값의 영향과 집단별 확률 보정이다.");
  table(s, [
    ["주차", "할 일", "도출할 결과"],
    ["W11", "설명 충실도 검증", "카드가 짚은 변수를 지우면 위험이 실제로 떨어지는가 — 무작위 대비 수치"],
    ["W12", "오분류 사례 분석", "모델이 놓친 기업 · 잘못 짚은 기업의 유형"],
    ["W13", "재무제표에 담기지 않는 정보", "공시 신호(계속기업 불확실성 · 제출기한 연장)가 재무비율에 더하는 정보"],
    ["W14", "설명 개선 · 리포트", "검증 결과를 반영한 카드 문안 · 보류 규칙, 개정 전후 비교"],
    ["W15", "정리 · 성과발표", "세 사례 시연 (정상 · 교정 · 보류) · 최종보고서 · 진로 판단"],
  ], M, TOP, CW, [1.1, 3.6, CW - 4.7], { size: 15, rowH: 0.56, align: "left" });
  s.addText("함께 확인할 한계 — 기준시점 이후 정정된 재무값의 영향 · 집단별 확률 보정 · 실무자 납득도(범위 밖)",
    { x: M, y: 5.6, w: CW, h: 0.5, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 10 team & career
{
  const s = content("남은 계획", "3 · 팀 기여와 진로 탐색", "재무 검토가 결론을 바꿨고, 진로 탐색 방향이 구체화됐다",
    "[8:50–9:35] 정민재의 재무 검토는 결과를 실제로 바꿨다 — 카드 문안 검토, 계수 부호 검산, 관리종목 사유 판정, 산업 평균 대조. (진로, 약 25초) 처음에는 예측 성능을 높이는 모델 개발에 관심이 있었습니다. 진행하면서 데이터와 설명을 검증하는 일이 결과의 신뢰성을 크게 바꾼다는 것을 경험했습니다. 현재는 금융 AI 개발과 모델 검증 직무를 함께 검토하고 있습니다. 남은 기간에는 구현과 오류 분석 중 어느 작업에서 더 흥미와 강점을 느끼는지 정리해 진로 방향을 구체화하겠습니다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 4.5, "재무 검토가 바꾼 것", [
    "카드 문안 검토 → 사실과 어긋난 단정 문장을 찾아 수정",
    "계수 부호 검산 → Δ부채비율: '공선성'이 아니라 판별력 부족으로 정정",
    "관리종목 1,242건 사유 판정 → 다른 부실 정의에서도 검증",
    "산업 평균 대조 → 결측 대치 전 원본값으로 비교 교정",
  ], { headColor: C.accent2, size: 15 });
  const x2 = M + w + 0.4;
  card(s, x2, TOP, w, 1.65, "진로 판단의 재료 (경험)", [
    "시간 대부분은 모델링이 아니라 데이터가 맞다는 증명에 들었다",
    "같은 결과를 실무 언어로 옮기는 것이 별도의 역량이었다",
  ], { size: 14 });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x2, y: TOP + 1.85, w, h: 2.65, rectRadius: 0.12, fill: { color: "E3EAF2" }, line: { type: "none" }, objectName: "중간 판단" });
  const row = (k, v, last) => [
    { text: k, options: { fontSize: 12, bold: true, color: C.accent2, breakLine: true } },
    { text: v, options: { fontSize: 14, color: C.text1, breakLine: !last, paraSpaceAfter: last ? 0 : 8 } },
  ];
  s.addText([
    ...row("검토 중인 진로", "금융 데이터를 이해하고 모델의 신뢰성을 검증하는 금융 AI 개발·검증 직무"),
    ...row("확인한 강점", "데이터 수집부터 모델·설명 구현까지 연결하고, 재무 검토 의견을 코드와 검증 절차에 반영한 경험"),
    ...row("남은 기간에 확인할 것", "모델 구현과 오류 원인 분석 중 어느 쪽에 더 흥미와 강점이 있는지 비교 · 재무 해석 역량의 보완 방향 구체화", true),
  ], { x: x2 + 0.3, y: TOP + 2.0, w: w - 0.6, h: 2.4, valign: "top", isTextBox: true, margin: 0, objectName: "중간 판단 문안" });
}

// ---- 11 closing
{
  const s = content("남은 계획", "마무리", "설계 · 현재 · 목표", 
    "[9:35–10:00] 정리한다. 시점을 고정한 설계 위에서 10주차까지 데이터·모델·설명 카드를 만들었다. 중간 답은 '전체 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다'는 것이다. 남은 기간에는 설명이 믿을 만한지 검증하고 개선해, 시연 가능한 설명 카드와 진로 판단으로 마무리하겠다.", true);
  const items = [
    ["설계", "기준시점 · 400일 창 · 연도순 분할 — 미래 정보를 쓰지 않는 부실 예측과 설명 카드"],
    ["현재", "10주차까지 완료. 중간 답: 전체 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다"],
    ["목표", "설명의 충실도를 검증 · 개선하고, 세 사례 시연과 진로 판단으로 마무리"],
  ];
  items.forEach(([n, t], i) => {
    const y = TOP + 0.2 + i * 1.4;
    s.addText(n, { x: M, y, w: 1.4, h: 1.0, fontSize: 30, bold: true, color: C.accent3, isTextBox: true, margin: 0, valign: "middle" });
    s.addText(t, { x: M + 1.6, y, w: CW - 1.6, h: 1.0, fontSize: 21, color: C.background1, valign: "middle", isTextBox: true, margin: 0 });
  });
}

// ---- appendix
pres.addSection({ title: "부록" });
{
  const s = content("부록", "부록 A1", "평가 구간 개봉 이력과 해석 범위",
    "질문이 나오면 쓴다. 평가 구간은 최종 1회만 열기로 했지만 개발 중 세 번 더 열었고, 데이터·라벨 오류를 고친 뒤 두 번 재평가했다. 재평가 기준은 결과를 보기 전에 docs/13에 고정·커밋했다. 모델 선택·하이퍼파라미터·변수 집합을 평가 결과로 정한 적은 없다. 그래서 평가 수치는 '오류 수정 후 재평가'로 부른다. 새 평가 데이터는 2027년 4월에 생긴다.");
  table(s, [
    ["#", "시점", "그 결과로 바꾼 것"],
    ["1–3", "개발 중 (배선 확인 · 윈저라이즈 · 결측 더미 실험)", "없음 — 3번은 잘못이라 검증 구간에서 재실행"],
    ["4", "최종 모델 확정 후 (계획된 1회)", "—"],
    ["5", "데이터 오류 수정 후 재평가 (10-11)", "없음 — 기준을 먼저 문서로 고정"],
    ["6", "라벨 오류 수정 후 재평가 2 (10-13)", "없음 — 기준을 먼저 문서로 고정"],
  ], M, TOP, CW, [0.8, 5.6, CW - 6.4], { size: 15, rowH: 0.5, align: "left" });
  s.addText("정정본 재무값(21.4% 행)을 빼면 처음 부실 PR-AUC 0.065 (사건 36건, 표본이 달라 직접 비교는 어려움) · 2015년 이전 부실 이력 미관측",
    { x: M, y: 4.75, w: CW, h: 0.6, fontSize: 14, color: C.text2, isTextBox: true, margin: 0 });
}
{
  const s = content("부록", "부록 A2", "예측 창 400일의 세부 근거",
    "1차 면담(09-05)에서 확정. 초기 설계 문서(v0.1)의 12개월은 관행을 따른 값이었다. 365·450일은 민감도로 병기(평가 전체 PR-AUC 0.144 · 0.227 · 0.253).");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.1, w, "364일", "사업보고서 제출 간격 중앙값 — 12개월 창이 분포 한가운데를 자른다");
  stat(s, M + w + 0.4, TOP + 0.1, w, "2.4배", "제출기한 연장 기업의 창 초과율 79.8% vs 33.1%", C.accent1);
  stat(s, M + 2 * (w + 0.4), TOP + 0.1, w, "62%", "검증 구간 첫 부실 사건 중 T 이후 366~400일에 일어난 비율 (전체 46%)", C.accent2);
  callout(s, 5.0, "400일: 라벨 사건 322건 → 548건, 창 초과 33.7% → 0.3%. 365·450일은 민감도로 병기.");
}
{
  const s = content("부록", "부록 A3", "설명 카드 검사 — 같은 사례의 수정 전후",
    "카드 설계 중 사실 단정 검사를 넣은 이유. 위험 방향 판정이 표본 중앙값 기준이라, 자본잠식이 없는 기업에도 '자본잠식이 진행'이 붙을 수 있었다. 첫 부실 집단 위험 상위 10% 카드 2,128줄 중 307줄(14.4%)이 그랬고, 같은 검사 기준에서 0이 됐다. 416장 중 9장은 보류. 사람 검증은 없다.");
  const cw = [4.1, 3.4, 4.1], gap = 0.2;
  let x = M;
  const heads = ["수정 전", "확인한 문제", "수정 후 (같은 사례)"];
  const bodies = [
    [{ text: "\"자본잠식이 진행되어 있습니다\"", options: { fontSize: 20, bold: true, color: C.accent1, breakLine: true } }, { text: "(실측 −29.6%)", options: { fontSize: 16, color: C.text2 } }],
    [{ text: "자본잠식률 −29.6% = 잠식 없음.", options: { fontSize: 17, bold: true, breakLine: true, paraSpaceAfter: 6 } }, { text: "중앙값보다 나쁘면 사실과 무관하게 단정 문장이 붙었다", options: { fontSize: 15, color: C.text2 } }],
    [{ text: "\"자본잠식은 없으나 자본 여력이 표본 중앙값보다 작습니다\"", options: { fontSize: 18, bold: true, color: C.accent2 } }],
  ];
  const fills = ["F6E3D8", C.background2, "E3EAF2"];
  cw.forEach((w, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP, w, h: 2.45, rectRadius: 0.12, fill: { color: fills[i] }, line: { type: "none" }, objectName: `전후 ${i}` });
    s.addText(heads[i], { x: x + 0.25, y: TOP + 0.2, w: w - 0.5, h: 0.35, fontSize: 13, bold: true, color: C.text2, isTextBox: true, margin: 0 });
    s.addText(bodies[i], { x: x + 0.25, y: TOP + 0.65, w: w - 0.5, h: 1.65, valign: "top", isTextBox: true, margin: 0 });
    x += w + gap;
  });
  callout(s, 4.65, "사실과 어긋난 단정 14.4% → 0 (같은 검사 기준) · 보류 416장 중 9장 · 사람 검증 없음", 0.9);
}
{
  const s = content("부록", "부록 A4", "SHAP 방향과 로지스틱 계수 대조 (카드 변수 8개)",
    "삭제 검사(검증 위험 상위 300건): SHAP 상위 1개 치환 시 확률 하락 0.263 vs 무작위 0.013 (20.7배) — 모델이 그 근거를 쓴다는 뜻이지 원인은 아니다. 영업이익률은 VIF 10.17로 ROA와 겹쳐 계수가 반대지만 안정성 필터에서 탈락. 군집 보정(기업당 4.44년) 후 유의 변수 18 → 12개.");
  table(s, [
    ["변수", "평균 |SHAP|", "SHAP 방향", "로지스틱 계수", "일치"],
    ["ROA", "0.380", "−0.78", "−0.32", "일치"],
    ["총자산영업이익률", "0.362", "−0.60", "−0.24", "일치"],
    ["유동비율", "0.167", "−0.40", "−0.25", "일치"],
    ["자본잠식률", "0.165", "+0.29", "+0.25", "일치"],
    ["로그자산", "0.156", "−0.72", "−0.66", "일치"],
    ["순이익률", "0.146", "−0.53", "−0.19", "일치"],
    ["총자산회전율", "0.128", "−0.78", "−0.64", "일치"],
    ["자기자본비율", "—", "−0.75", "−0.48", "일치"],
  ], M, TOP, 9.0, [2.8, 1.6, 1.5, 1.9, 1.2], { size: 14, rowH: 0.43 });
  s.addText("SHAP 방향 = 값과 SHAP의 상관 · 로지스틱 계수는 결측 더미 포함 적합(W09) · 자기자본비율은 평균 |SHAP| 상위 8개 밖", { x: M, y: 5.95, w: 10, h: 0.35, fontSize: 11, color: C.text2, isTextBox: true, margin: 0 });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
