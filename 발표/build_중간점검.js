// 중간 점검 보고회 — 수치 출처: docs/10 (2026-10-13 판, 라벨 오류 수정 후 재평가). 대표 그림: results/final/대표그림.png
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
pres.addSection({ title: "질문과 결과물" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "질문과 결과물" });
  s.addText("HUFS H-UP 12기 · 중간 점검 보고회", { placeholder: "eyebrow" });
  s.addText("부실 예측 AI는 무엇을 맞히고,\n그 설명은 어디까지 믿을 수 있는가", { placeholder: "title" });
  s.addText("국내 상장기업 재무제표 기반 부실 예측과 설명 검증 — 중간 결과", { placeholder: "sub" });
  s.addText([{ text: "팀 종민재 · 이종민 · 정민재", options: { bold: true, breakLine: true } }, { text: "지도교수 공형우 (Finance&AI 융합학부)", options: { fontSize: 14, color: C.accent6 } }], { placeholder: "team" });
  s.addNotes("[0:00–0:20] 팀 소개. 제목이 곧 질문이다 — 모델은 무엇을 맞히고, 그 설명은 어디까지 믿을 수 있는가.");
}

// ---- 2 question + outputs
{
  const s = content("질문과 결과물", "1 · 질문과 결과물", "두 질문에 답하려고 세 가지를 만들었다",
    "[0:20–1:20] 부실 예측 모델은 실무에서 이미 쓰이고, 규제는 '왜 위험한가'를 문서로 남기라고 요구한다. 그래서 두 질문을 검증 가능한 형태로 묻는다. ① 모델이 맞히는 것이 처음 부실해지는 기업인가, 이미 부실을 겪은 기업인가. ② 설명이 모델의 실제 근거를 반영하고 재무 사실과 맞는가. 이를 위해 만든 것이 세 가지다 — DART 공시로 만든 부실 위험 순위, 사람이 읽는 설명 카드, 그리고 카드를 내보내기 전에 거르는 설명 검사·보류. '실무자가 납득하는가'는 실무자 평가를 제외해 확인하지 않는다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 1.45, "① 무엇을 맞히는가", ["처음 부실해지는 기업인가, 이미 부실을 겪은 기업인가"], { headColor: C.accent2, size: 17 });
  card(s, M + w + 0.4, TOP, w, 1.45, "② 설명을 믿을 수 있는가", ["모델의 실제 근거를 반영하는가 · 재무 사실과 맞는가"], { headColor: C.accent1, size: 17 });
  const y = 3.75, w3 = (CW - 0.8) / 3;
  const steps = [
    ["부실 위험 순위", "상장사 3,412곳 · 기업-연도 23,084행 · DART 공시만 사용"],
    ["설명 카드", "위험을 높인 요인과 낮춘 요인을 실측값과 함께 문장으로"],
    ["설명 검사 · 보류", "사실과 어긋나거나 근거가 불안정하면 설명 대신 보류 사유"],
  ];
  steps.forEach(([h, b], i) => {
    const x = M + i * (w3 + 0.4);
    card(s, x, y, w3, 1.9, h, [b], { size: 15, fill: "E3EAF2" });
    if (i < 2) s.addText("→", { x: x + w3, y: y + 0.6, w: 0.4, h: 0.6, fontSize: 24, bold: true, color: C.accent2, align: "center", isTextBox: true, margin: 0 });
  });
  s.addText("범위 — 2016~2025년 공시 · 감사의견 비적정 또는 회생절차 개시 · 실무자 평가 제외 · 실명 기업 위험도 비공개",
    { x: M, y: 5.95, w: CW, h: 0.45, fontSize: 13, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 3 card example (결과물을 먼저 보여준다)
{
  const s = content("질문과 결과물", "1 · 결과물", "설명 카드 — 숫자 대신 문장으로, 실측값과 함께",
    "[1:20–2:10] 'ROA SHAP +0.34'는 설명이 아니다. 검증 구간 실제 사건 기업의 익명 카드다. 확률은 보정본에서 뽑는다 — 보정 전 평균 예측이 실제의 7.6배였다(두 집단을 합쳐 보정했고 집단별 보정은 확인하지 않았다). 위험을 낮춘 요인이 없으면 '해당 없음'이라고 적는다 — 위험 요인만 나열하면 확증 편향 도구가 된다. 이 카드가 틀리게 말한 적이 있었고, 그것이 두 번째 발견이다.");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: TOP, w: 7.6, h: 4.3, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: H.accent5, width: 1 }, objectName: "설명 카드" });
  s.addText([
    { text: "익명 사례 · 검증 구간 · 실제 사건 기업", options: { fontSize: 13, color: C.text2, breakLine: true, paraSpaceAfter: 6 } },
    { text: "모형 추정 부실확률 55.5%", options: { fontSize: 26, bold: true, color: C.accent1, breakLine: true, paraSpaceAfter: 14 } },
    { text: "위험을 높인 요인 (상위 2개)", options: { fontSize: 15, bold: true, color: C.text2, breakLine: true, paraSpaceAfter: 6 } },
    { text: "자본잠식이 진행되어 있습니다 (실측 94.9%)", options: { fontSize: 21, bullet: true, breakLine: true, paraSpaceAfter: 6 } },
    { text: "자산 규모에 비해 벌어들이는 이익이 적습니다 (실측 −29.0%)", options: { fontSize: 21, bullet: true, breakLine: true, paraSpaceAfter: 14 } },
    { text: "위험을 낮춘 요인", options: { fontSize: 15, bold: true, color: C.text2, breakLine: true, paraSpaceAfter: 6 } },
    { text: "해당 없음 (안정 변수 중 위험을 낮춘 항목이 없습니다)", options: { fontSize: 17, bullet: true } },
  ], { x: M + 0.35, y: TOP + 0.25, w: 6.9, h: 3.8, valign: "top", isTextBox: true, margin: 0, objectName: "카드 문안" });
  const x2 = M + 8.1, w2 = CW - 8.1;
  card(s, x2, TOP, w2, 1.3, "확률은 보정본에서", ["보정 전 평균 예측이 실제의 7.6배였다"], { size: 15, headColor: C.accent2 });
  card(s, x2, TOP + 1.5, w2, 1.3, "낮춘 요인도 적는다", ["없으면 \"해당 없음\" — 확증 편향 방지"], { size: 15, headColor: C.accent2 });
  card(s, x2, TOP + 3.0, w2, 1.3, "검사를 통과해야 나간다", ["못 넘으면 설명 대신 보류 사유"], { size: 15, headColor: C.accent1 });
}

// ---- 4 finding 1: performance
pres.addSection({ title: "핵심 발견" });
{
  const s = content("핵심 발견", "2 · 발견 ① 성능", "높은 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다",
    "[2:10–3:40] ★ 핵심 장. 오른쪽 평가 구간부터. 전체 PR-AUC는 0.227이지만 평가 사건 158건 중 107건(68%)이 이미 부실을 겪은 기업이다. 과거 부실 여부 하나만으로 순위를 매겨도 검증 PR-AUC 0.214가 나온다(왼쪽 검증 구간은 참고). 그래서 '관측 기간 내 첫 부실'을 주 분석으로 바꿨다 — 이 결정은 검증 구간 근거로 먼저 내렸다. 첫 부실 평가 PR-AUC 0.091, 기준선의 8.0배로 순위는 무작위보다 낫지만, 정밀도 30%를 지키면 51건 중 1건만 잡는다. 해석 범위 두 가지를 여기서 밝힌다. 재무 API가 최신 정정본만 줘서 일부 행에 기준시점 이후 정정된 값이 섞였다 — 이 행을 빼면 첫 부실 PR-AUC는 0.065(사건 36건)다. 표본이 달라져 하락을 정정본 하나로 돌릴 수는 없다. 그리고 이 수치는 오류를 고친 뒤 기준을 먼저 고정하고 다시 낸 재평가다.");
  s.addImage({ path: "/Users/john9/Desktop/h-up/project/results/final/대표그림.png", x: 1.65, y: 1.7, w: 10.0, h: 4.36, objectName: "대표 그림" });
  s.addText([
    { text: "첫 부실 평가 PR-AUC 0.091 (기준선의 8.0배) · 정밀도 30%에서 51건 중 1건", options: { bold: true, color: C.accent2, breakLine: true } },
    { text: "해석 범위 — 기준시점 이후 정정된 재무값 행을 빼면 0.065 (사건 36건, 표본이 달라 직접 비교는 어려움) · 오류 수정 후 재평가 수치", options: { fontSize: 13, color: C.text2 } },
  ], { x: M, y: 6.08, w: CW, h: 0.8, fontSize: 16, isTextBox: true, margin: 0, valign: "top" });
}

// ---- 5 finding 2: explanation errors, before/after
{
  const s = content("핵심 발견", "2 · 발견 ② 설명 오류", "틀린 설명을 찾아 고치고, 못 믿을 설명은 보류했다",
    "[3:40–5:10] ★ 두 번째 핵심. 같은 기업의 같은 변수다. 자본잠식률이 −29.6%면 자본잠식이 없다는 뜻인데, 구 카드는 '자본잠식이 진행되어 있습니다'라고 단정했다. 위험 방향 판정이 표본 중앙값 기준이었기 때문이다 — 중앙값보다 나쁘면 사실과 상관없이 단정 문장이 붙었다. 정민재의 카드 문안 검토에서 나온 지적이다. 절대 기준을 넘었을 때만 단정하고, 아니면 '중앙값보다 작습니다'로 쓰도록 고쳤다. 첫 부실 집단 위험 상위 10% 카드 2,128줄 중 307줄(14.4%)이 이런 단정이었고, 같은 검사 기준에서 0이 됐다. 아래는 보류 사례 — 모델의 가장 큰 근거가 안정성 검사를 통과하지 못한 변수여서, 설명을 지어내지 않고 사유를 낸다. 416장 중 9장이 보류됐다. 모두 우리 검사 기준으로 잰 값이고 사람 검증은 없다.");
  const cw = [4.1, 3.4, 4.1], gap = 0.2;
  let x = M;
  const heads = ["수정 전 (2026-10-10 이전)", "확인한 문제", "수정 후 (같은 사례)"];
  const bodies = [
    [{ text: "\"자본잠식이 진행되어 있습니다\"", options: { fontSize: 21, bold: true, color: C.accent1, breakLine: true } }, { text: "(실측 −29.6%)", options: { fontSize: 17, color: C.text2 } }],
    [{ text: "자본잠식률 −29.6% = 잠식 없음.", options: { fontSize: 17, bold: true, breakLine: true, paraSpaceAfter: 6 } }, { text: "중앙값보다 나쁘면 사실과 무관하게 단정 문장이 붙었다", options: { fontSize: 15, color: C.text2 } }],
    [{ text: "\"자본잠식은 없으나 자본 여력이 표본 중앙값보다 작습니다\"", options: { fontSize: 19, bold: true, color: C.accent2, breakLine: true } }, { text: "(실측 −29.6%)", options: { fontSize: 17, color: C.text2 } }],
  ];
  const fills = ["F6E3D8", C.background2, "E3EAF2"];
  cw.forEach((w, i) => {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: TOP, w, h: 2.45, rectRadius: 0.12, fill: { color: fills[i] }, line: { type: "none" }, objectName: `전후 ${i}` });
    s.addText(heads[i], { x: x + 0.25, y: TOP + 0.2, w: w - 0.5, h: 0.35, fontSize: 13, bold: true, color: C.text2, isTextBox: true, margin: 0 });
    s.addText(bodies[i], { x: x + 0.25, y: TOP + 0.65, w: w - 0.5, h: 1.65, valign: "top", isTextBox: true, margin: 0 });
    x += w + gap;
  });
  const w2 = (CW - 0.4) / 2, y2 = 4.6;
  card(s, M, y2, w2, 1.75, "보류 사례 — 설명 대신 사유를 낸다", ["\"설명 보류 — 모델의 가장 큰 근거(이자보상배율)가 카드에 올릴 수 없는 변수입니다\""], { size: 15, headColor: C.accent1, dash: true, fill: C.background1, line: C.accent1 });
  s.addText([
    { text: "14.4% → 0", options: { fontSize: 34, bold: true, color: C.accent1, breakLine: true } },
    { text: "사실과 어긋난 단정 문장 (첫 부실 상위 10% 카드 2,128줄 중 307줄). 보류 416장 중 9장. 같은 검사 기준의 수치이며 사람 검증은 없다.", options: { fontSize: 14, color: C.text2 } },
  ], { x: M + w2 + 0.4, y: y2, w: w2, h: 1.75, valign: "top", isTextBox: true, margin: 0 });
}

// ---- 6 evidence: timing (A-1 leak + 400일)
pres.addSection({ title: "믿을 근거" });
{
  const s = content("믿을 근거", "3 · 근거 ① 시점", "답이 문제 안에 들어가지 않게 했다",
    "[5:10–6:20] 기준시점 T는 결산일이 아니라 DART 최초 접수일이다. 감사의견은 그 사업연도 보고서 안에 있어서, 같은 보고서로 같은 해 의견을 맞히면 동어반복이다. 10-13 점검에서 감사의견 사건일을 '마지막 정정본 날짜'로 잡아 자기 보고서의 비적정 의견이 자기 행의 라벨이 된 것을 찾았다(131행). 최초 접수일로 고치고 전부 다시 돌렸고, 첫 부실 성능은 오히려 낮아졌다 — 누수가 성능을 부풀리고 있었다. 예측 창은 관행인 12개월 대신 400일이다. 사업보고서 제출 간격 중앙값이 364일이라 12개월 창은 다음 해 의견을 3분의 1가량 놓친다. 400일이면 창 밖 비율이 0.3%다. 세부 수치는 부록.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 3.9, "라벨 누수를 찾아 고쳤다", [
    "감사의견 사건일을 '마지막 정정본 날짜'로 잡아, 자기 보고서에 이미 적힌 비적정 의견이 자기 행의 라벨이 됐다 (131행).",
    "→ 사건일 = 그 보고서의 최초 접수일. 전 단계 재실행 후 첫 부실 성능은 더 낮아졌다 — 누수가 부풀리고 있었다.",
  ], { headColor: C.accent1, size: 16 });
  const x2 = M + w + 0.4;
  card(s, x2, TOP, w, 3.9, "예측 창 400일 — 근거 하나", [], { headColor: C.accent2 });
  s.addText("33.7% → 0.3%", { x: x2 + 0.3, y: TOP + 0.8, w: w - 0.6, h: 1.0, fontSize: 44, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
  s.addText("다음 해 감사의견이 예측 창 밖으로 밀려나는 비율 (12개월 → 400일). 제출 간격 중앙값이 364일이라 12개월 창은 분포 한가운데를 자른다.",
    { x: x2 + 0.3, y: TOP + 1.9, w: w - 0.6, h: 1.8, fontSize: 16, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
  s.addText("365·450일은 민감도로 병기 (평가 전체 PR-AUC 0.144 · 0.227 · 0.253). 세부 수치는 부록 A2.", { x: M, y: 6.05, w: CW, h: 0.4, fontSize: 13, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 7 evidence: split
{
  const s = content("믿을 근거", "3 · 근거 ② 분할", "미래를 과거로 맞히지 않게 시점으로 나눴다",
    "[6:20–7:00] 상장사 3,412곳, 기업-연도 23,084행, 사건 548건. 라벨 창 400일이 검증 구간으로 넘어가는 2021년 공시분은 검증 단계 학습에서 뺐다(엠바고). 최종 모델은 학습 구간 전체로 학습하고 그 라벨 창은 평가 시작 전에 끝난다. 기업 단위 분할도 검토했지만 검증 기업의 87%가 학습에도 나와, 새 기업만 남기면 492건·사건 2건이다 — 새 기업 대상 성능은 신뢰성 있게 평가하기 어렵다.");
  table(s, [
    ["구간", "공시 연도", "관측치", "사건", "사건비율"],
    ["학습 (엠바고)", "2016~2020*", "9,273", "204", "2.20%"],
    ["학습 (최종 모델)", "2016~2021", "11,376", "261", "2.29%"],
    ["검증", "2022~2023", "4,406", "120", "2.72%"],
    ["평가", "2024~2025", "4,805", "158", "3.29%"],
  ], M, TOP, 7.4, [2.1, 1.5, 1.3, 1.1, 1.4], { size: 15, rowH: 0.5 });
  s.addText("* 라벨 창(400일)이 검증 시작 전에 끝나는 행만. 공시 단위 오류는 같은 회사의 공시로 확인된 것만 수정(7개사 15행).",
    { x: M, y: 4.85, w: 7.4, h: 0.9, fontSize: 14, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
  const x2 = M + 7.9, w2 = CW - 7.9;
  card(s, x2, TOP, w2, 3.4, "기업 단위 분할은 보조로만", [], { headColor: C.accent1 });
  s.addText("사건 2건", { x: x2 + 0.3, y: TOP + 0.75, w: w2 - 0.6, h: 1.0, fontSize: 48, bold: true, color: C.accent1, isTextBox: true, margin: 0 });
  s.addText("검증 기업의 87%가 학습에도 등장해, 새 기업만 남기면 492건 · 사건 2건. 새 기업 대상 성능은 신뢰성 있게 평가하기 어렵다.",
    { x: x2 + 0.3, y: TOP + 1.85, w: w2 - 0.6, h: 1.4, fontSize: 15, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
}

// ---- 8 evidence: explanation reflects model
{
  const s = content("믿을 근거", "3 · 근거 ③ 설명의 근거", "카드가 말하는 요인은 모델이 실제로 쓰는 것이다",
    "[7:00–8:00] 두 가지로 확인했다. 삭제 검사 — SHAP이 지목한 변수 하나를 중앙값으로 바꾸면 부실확률이 평균 26%p 떨어지고 무작위 변수는 1.3%p다. 모델이 그 근거를 실제로 쓴다는 뜻이지 원인이라는 뜻은 아니다. 교차 검산 — 카드에 오르는 8개 변수는 SHAP 방향과 로지스틱 계수 부호가 모두 맞다. 기여도 1위는 수익성(ROA)이다. 안정성 필터는 처음에 기준을 잘못 만들었다가 고쳤다. 상세 표는 부록.");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.1, w, "20.7배", "삭제 검사 — SHAP 상위 1개를 바꿨을 때 확률 하락 0.263 vs 무작위 변수 0.013 (검증 위험 상위 300건)", C.accent2);
  stat(s, M + w + 0.4, TOP + 0.1, w, "8 / 8", "카드 변수 8개의 SHAP 방향이 로지스틱 계수 부호와 모두 일치", C.accent2);
  stat(s, M + 2 * (w + 0.4), TOP + 0.1, w, "ROA", "평균 |SHAP| 1위 (0.380). 2위 총자산영업이익률 0.362 — 모델이 가장 많이 보는 것은 수익성");
  callout(s, 4.75, [
    { text: "삭제 검사는 '모델이 그 근거를 쓴다'를 보일 뿐 원인을 보이지 않는다. ", options: { bold: true } },
    { text: "안정성 필터: 시드 5개에서 값↔SHAP 상관 부호가 유지되는 12개 변수만 통과, 그중 8개가 카드에 오른다." },
  ], 1.1);
}

// ---- 9 re-evaluation history & scope
pres.addSection({ title: "해석 범위와 다음 단계" });
{
  const s = content("해석 범위와 다음 단계", "4 · 해석 범위", "재평가 이력과 해석 범위",
    "[8:00–8:40] 평가 구간은 최종 1회만 열기로 했지만 개발 중 세 번 더 열었고, 오류를 고친 뒤 두 번 재평가했다. 재평가 때는 기준을 문서에 먼저 고정하고 커밋했다. 모델 선택·하이퍼파라미터·변수 집합을 평가 구간 결과로 정한 적은 없다. 그래서 평가 수치는 독립 검증이 아니라 '오류 수정 후 재평가'로 부른다. 진짜 새 평가 데이터는 2027년 4월에 생긴다. 상세 이력은 부록 A1.");
  const w = (CW - 0.8) / 3;
  card(s, M, TOP, w, 2.4, "평가 수치의 성격", ["오류 수정 후 재평가 (독립 검증 아님). 재평가 기준은 결과를 보기 전에 문서로 고정했다."], { headColor: C.accent2, size: 16 });
  card(s, M + w + 0.4, TOP, w, 2.4, "평가 결과로 정하지 않은 것", ["모델 선택 · 하이퍼파라미터 · 변수 집합. 주 분석 전환은 검증 구간 근거로 먼저 결정."], { headColor: C.accent2, size: 16 });
  card(s, M + 2 * (w + 0.4), TOP, w, 2.4, "남은 한계", ["기준시점 이후 정정된 재무값 (21.4% 행) · 2015년 이전 부실 이력 미관측 · 집단별 확률 보정 미확인"], { headColor: C.accent1, size: 16 });
  s.addText("새 평가 데이터는 FY2025 보고서의 400일 관측이 끝나는 2027년 4월에 생긴다. 평가 구간 개봉 이력은 부록 A1.",
    { x: M, y: 4.65, w: CW, h: 0.6, fontSize: 15, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 10 progress
{
  const s = content("해석 범위와 다음 단계", "4 · 진척", "완료 · 미완료 · 다음 산출물",
    "[8:40–9:20] 계획상 11~14주차 분석(충실도·오분류·담기지 않는 정보·설명 개선)은 앞당겨 했다. 남은 검증은 세 가지다 — 정정본 시점 재무값, 집단별 확률 보정, 사람 검증은 범위 밖이라 한계로 명시. 다음 산출물은 시연 가능한 세 사례, 최종 보고서, 진로 판단이다. 2차 면담에서 주 분석 변경(첫 부실)·매칭 학습 폐기·장학금 계획 변경을 보고한다.");
  const w = (CW - 0.8) / 3;
  card(s, M, TOP, w, 4.2, "완료", ["데이터 · 라벨 · 시점 분할", "예측 모델 + 확률 보정", "설명 카드 · 사실 단정 검사 · 보류", "오류 수정 후 재평가 2회 (기준 사전 고정)"], { headColor: C.accent2, size: 15 });
  card(s, M + w + 0.4, TOP, w, 4.2, "미완료 — 남은 검증", ["정정본 시점 재무값 영향 (원문 수집 필요)", "집단별 확률 보정 확인", "설명의 실무 납득도 — 범위 밖, 한계로 명시"], { headColor: C.accent1, size: 15 });
  card(s, M + 2 * (w + 0.4), TOP, w, 4.2, "다음 산출물", ["세 사례 시연 (정상 · 교정 · 보류)", "최종 보고서 (W15)", "진로 판단 · 성과발표", "2차 면담 보고 (주 분석 변경 · 매칭 폐기 · 장학금 계획)"], { headColor: C.text1, size: 15 });
}

// ---- 11 team & career
{
  const s = content("해석 범위와 다음 단계", "4 · 팀 기여와 진로 탐색", "재무 검토가 결론을 바꿨고, 진로 탐색 방향이 구체화됐다",
    "[9:20–10:10] 정민재의 재무 검토는 결과를 실제로 바꿨다. 카드 문안 검토가 14.4% 단정 오류를 찾게 했고, 계수 검산으로 Δ부채비율 해석을 '공선성'에서 '판별력 부족'으로 고쳤고, 관리종목 1,242건의 사유를 판정해 다른 정의에서의 검증을 가능하게 했다. (진로, 약 25초) 처음에는 예측 성능을 높이는 모델 개발에 관심이 있었습니다. 진행하면서 데이터와 설명을 검증하는 일이 결과의 신뢰성을 크게 바꾼다는 것을 경험했습니다. 현재는 금융 AI 개발과 모델 검증 직무를 함께 검토하고 있습니다. 남은 기간에는 구현과 오류 분석 중 어느 작업에서 더 흥미와 강점을 느끼는지 정리해 진로 방향을 구체화하겠습니다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 4.5, "정민재의 검토가 바꾼 것", [
    "카드 문안 검토 → 사실과 어긋난 단정 14.4% 발견 · 수정",
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
  ], { x: x2 + 0.3, y: TOP + 2.0, w: w - 0.6, h: 2.2, valign: "top", isTextBox: true, margin: 0, objectName: "중간 판단 문안" });
}

// ---- 12 closing
{
  const s = content("해석 범위와 다음 단계", "마무리", "지금까지 확인한 것", 
    "[10:10–10:50] 세 문장으로 마무리. 반복 부실과 신규 부실을 나눠야 성능을 제대로 해석할 수 있었다. 설명에도 사실 오류가 있었고, 이를 검사하고 보류하는 절차를 만들었다. 남은 기간에는 사례 시연과 검증 범위를 정리하고 진로 판단으로 연결한다.", true);
  const items = [
    ["01", "반복 부실과 신규 부실을 구분해야 성능을 제대로 해석할 수 있었다."],
    ["02", "모델 설명에도 사실 오류가 생겨, 이를 검사하고 보류하는 절차를 만들었다."],
    ["03", "남은 기간에는 사례 시연과 검증 범위를 정리하고 진로 판단으로 연결한다."],
  ];
  items.forEach(([n, t], i) => {
    const y = TOP + 0.2 + i * 1.4;
    s.addText(n, { x: M, y, w: 1.2, h: 1.0, fontSize: 40, bold: true, color: C.accent3, isTextBox: true, margin: 0 });
    s.addText(t, { x: M + 1.4, y, w: CW - 1.4, h: 1.0, fontSize: 22, color: C.background1, valign: "middle", isTextBox: true, margin: 0 });
  });
}

// ---- appendix
pres.addSection({ title: "부록" });
{
  const s = content("부록", "부록 A1", "평가 구간 개봉 이력",
    "질문이 나오면 쓴다. 개발 중 세 번(배선 확인·윈저라이즈·결측 더미 실험) 열었고 3번은 잘못이라 검증 구간에서 재실행했다. 재평가 두 번은 기준을 docs/13에 먼저 고정하고 커밋한 뒤 실행했다.");
  table(s, [
    ["#", "시점", "그 결과로 바꾼 것"],
    ["1–3", "개발 중 (배선 확인 · 윈저라이즈 · 결측 더미 실험)", "없음 — 3번은 잘못이라 검증 구간에서 재실행"],
    ["4", "최종 모델 확정 후 (계획된 1회)", "—"],
    ["5", "데이터 오류 수정 후 재평가 (10-11)", "없음 — 기준을 먼저 문서로 고정"],
    ["6", "라벨 오류 수정 후 재평가 2 (10-13)", "없음 — 기준을 먼저 문서로 고정"],
  ], M, TOP, CW, [0.8, 5.6, CW - 6.4], { size: 15, rowH: 0.5, align: "left" });
}
{
  const s = content("부록", "부록 A2", "예측 창 400일의 세부 근거",
    "1차 면담(09-05)에서 확정. 초기 설계 문서(v0.1)의 12개월은 관행을 따른 값이었고 지원서에 적힌 값은 아니다.");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.1, w, "364일", "사업보고서 제출 간격 중앙값 — 12개월 창이 분포 한가운데를 자른다");
  stat(s, M + w + 0.4, TOP + 0.1, w, "2.4배", "제출기한 연장 기업의 창 초과율 79.8% vs 33.1%", C.accent1);
  stat(s, M + 2 * (w + 0.4), TOP + 0.1, w, "62%", "검증 구간 첫 부실 사건 중 T 이후 366~400일에 일어난 비율 (전체 46%)", C.accent2);
  callout(s, 5.0, "400일: 라벨 사건 322건 → 548건, 창 초과 33.7% → 0.3%. 365·450일은 민감도로 병기.");
}
{
  const s = content("부록", "부록 A3", "사건 기업의 궤적 (사후 중앙값)",
    "사건 기업만 골라 거꾸로 본 사후 중앙값이다 — 예측력의 증거가 아니라 궤적 기술이다. 판별력은 사건군과 정상군의 표준화 중앙값 차이.");
  table(s, [
    ["중앙값", "t-3", "t-2", "t-1", "정상군"],
    ["이자보상배율", "−0.30", "−0.80", "−1.02", "+1.94"],
    ["영업이익률", "−8.1%", "−13.8%", "−20.0%", "+3.7%"],
    ["ROA", "−11.1%", "−14.0%", "−18.2%", "+2.0%"],
    ["영업현금흐름/매출", "−5.4%", "−6.6%", "−7.3%", "+5.2%"],
  ], M, TOP, 7.6, [2.8, 1.2, 1.2, 1.2, 1.2], { size: 15, rowH: 0.52 });
  card(s, M + 8.1, TOP, CW - 8.1, 3.4, "수준값이 이미 신호다", [
    "판별력(사건군·정상군의 표준화 중앙값 차이): 수준값 1위 2년연속영업손실 2.64, 변화량·증가율 1위 자산증가율 0.38 — 약 7배. ΔROA(0.16) 대비 약 16배.",
  ], { size: 15 });
}
{
  const s = content("부록", "부록 A4", "SHAP 방향과 로지스틱 계수 대조 (카드 변수 8개)",
    "영업이익률은 VIF 10.17로 ROA와 겹쳐 계수가 반대지만 안정성 필터에서 탈락. Δ부채비율은 정민재 검토로 '공선성'이 아니라 판별력 부족(VIF 1.31)으로 정정. 군집 보정(기업당 4.44년) 후 유의 변수 18 → 12개.");
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
