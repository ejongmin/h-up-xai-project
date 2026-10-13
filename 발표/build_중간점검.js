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
pres.addSection({ title: "문제 설정" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "문제 설정" });
  s.addText("HUFS H-UP 12기 · 중간 점검 보고회", { placeholder: "eyebrow" });
  s.addText("부실 예측 AI는 무엇을 맞히고, 그 설명은 어디까지 믿을 수 있는가", { placeholder: "title" });
  s.addText("국내 상장기업 재무제표 기반 부실예측과 설명 검증 — 현재까지의 진행 (10-13 재평가 포함)", { placeholder: "sub" });
  s.addText([{ text: "팀 종민재 · 이종민 · 정민재", options: { bold: true, breakLine: true } }, { text: "지도교수 공형우 (Finance&AI 융합학부)", options: { fontSize: 14, color: C.accent6 } }], { placeholder: "team" });
  s.addNotes("[0:00–0:20] 팀 소개. 제목이 곧 질문이다 — 모델은 무엇을 맞히고, 그 설명은 어디까지 믿을 수 있는가. 계획상 9주차 범위지만, 그 사이 찾은 오류와 재평가까지 포함해 보고한다.");
}

// ---- 2 question
{
  const s = content("문제 설정", "1 · 문제 설정", "무엇을 맞히고, 설명은 어디까지 믿을 수 있는가",
    "[0:20–1:10] 부실예측 모델은 실무에서 이미 쓰인다. 규제는 '왜 위험한가'를 문서로 남길 것을 요구한다(2025 CFPB 등). 그래서 두 질문을 검증 가능한 형태로 묻는다. ① 모델이 맞히는 것이 '처음 부실해지는 기업'인가, '이미 부실했던 기업'인가. ② 설명이 모델의 실제 근거를 반영하고, 재무 사실과 맞는가(충실도). '실무자가 납득하는가'는 실무자 평가를 제외해 확인하지 않는다 — 처음부터 범위를 밝힌다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 2.2, "① 무엇을 맞히는가", ["처음 부실해지는 기업(관측 기간 내 첫 부실)인가, 이미 부실을 겪은 기업인가 — 둘을 나눠서 본다."], { headColor: C.accent2, size: 18 });
  card(s, M + w + 0.4, TOP, w, 2.2, "② 설명을 믿을 수 있는가", ["설명이 모델의 실제 근거를 반영하는가(삭제 검사), 문장이 재무 사실과 맞는가(사실 단정 검사)."], { headColor: C.accent1, size: 18 });
  s.addText("범위 — 국내 상장사 · 2016~2025년 공시 · 감사의견 비적정 또는 회생절차 개시. '실무자가 납득하는가'는 확인하지 않았다(실무자 평가 제외). 실명 기업의 위험도는 공개하지 않는다.",
    { x: M, y: 4.45, w: CW, h: 0.9, fontSize: 15, color: C.text2, isTextBox: true, margin: 0 });
}

// ---- 3 definition (A-1) + leak
pres.addSection({ title: "사건 정의와 시점 정합" });
{
  const s = content("사건 정의와 시점 정합", "2 · 사건 정의 — 함정 A-1", "답이 문제 안에 들어 있으면 안 된다",
    "[1:10–2:20] 기준시점 T는 결산일이 아니라 DART 접수일. 감사의견은 그 사업연도 보고서 안에 있으니, 같은 보고서로 같은 해 의견을 맞히면 동어반복이다. 우리는 '사건일 > T'를 테스트로 고정했다. 그런데 10-13 코드 감사에서, 감사의견 사건일을 API가 주는 '마지막 정정본 날짜'로 잡고 있었다는 게 드러났다. 그래서 자기 보고서에 이미 적힌 비적정이 T 이후 사건이 되어 자기 행의 라벨이 됐다(131행). 반대로 다음 해 의견 80건은 정정본 날짜 때문에 창 밖으로 밀려 빠져 있었다. 사건일을 '그 보고서의 최초 접수일'로 고치고 전부 다시 돌렸다. 고치자 첫 부실 성능이 더 낮아졌다 — 누수가 성능을 부풀리고 있었다.");
  const w = (CW - 0.6) / 3;
  card(s, M, TOP, w, 1.75, "주 정의", ["감사의견 비적정 또는 회생절차 개시 신청"]);
  card(s, M + (w + 0.3), TOP, w, 1.75, "제외", ["금융업 · 스팩·리츠 · 비12월결산"]);
  card(s, M + 2 * (w + 0.3), TOP, w, 1.75, "기준시점 T", ["결산일이 아니라 DART 최초 접수일"]);
  callout(s, 3.95, [
    { text: "막았다고 생각한 함정이 다른 경로로 뚫려 있었다. ", options: { bold: true } },
    { text: "감사의견 사건일을 '마지막 정정본 날짜'로 잡아, 자기 보고서에 이미 적힌 비적정 의견이 자기 행의 라벨이 됐다(131행).", options: { breakLine: true } },
    { text: "→ 사건일 = 그 보고서의 최초 접수일로 고치고 전 단계를 다시 실행. 첫 부실 성능이 더 낮아졌다(누수가 부풀리고 있었다).", options: { color: C.text2, fontSize: 15 } },
  ], 1.9);
}

// ---- 4 window (A-2)
{
  const s = content("사건 정의와 시점 정합", "2 · 시점 정합 — 함정 A-2", "관행인 12개월 창은 사건을 크게 놓친다",
    "[2:20–3:20] 초기 설계 문서(v0.1)에선 관행대로 12개월로 정했다 — 지원서에 적힌 값은 아니다. 실측하니 제출간격 중앙값 364일, 창이 분포 한가운데를 자른다. 제출기한을 연장한 기업은 창을 넘는 비율이 79.8% vs 33.1%로 2.4배 — 더 많이 지워진다. 400일로 올리면 창 초과가 0.3%로 떨어지고 사건이 322건에서 548건이 된다. 검증 구간 사건의 46%, 첫 부실만 보면 62%가 T 이후 366~400일에 일어났다. 1차 면담(09-05)에서 확정했고 365·450일은 민감도로 함께 본다.");
  const w = (CW - 0.8) / 3;
  stat(s, M, TOP + 0.1, w, "364일", "사업보고서 제출간격 중앙값 — 12개월 창이 분포 한가운데를 자른다");
  stat(s, M + w + 0.4, TOP + 0.1, w, "2.4배", "제출기한 연장 기업의 창 초과율 79.8% vs 33.1% — 이 기업들의 사건이 더 많이 지워진다", C.accent1);
  stat(s, M + 2 * (w + 0.4), TOP + 0.1, w, "62%", "검증 구간 첫 부실 사건 중 T 이후 366~400일에 일어난 비율 (전체 46%)", C.accent2);
  callout(s, 5.0, [
    { text: "→ 주 분석 창 400일 (1차 면담 확정): 라벨 사건 322건 → " },
    { text: "548건", options: { bold: true } },
    { text: ", 창 초과 33.7% → 0.3%. 365·450일은 민감도로 병기." },
  ]);
}

// ---- 5 data split (A-3)
pres.addSection({ title: "데이터와 성능" });
{
  const s = content("데이터와 성능", "3 · 데이터 — 함정 A-3", "시점 분할: 학습 → 검증 → 평가",
    "[3:20–4:10] 상장사 3,412사, 기업-연도 23,084행, 사건 548건(2.37%). 라벨 창 400일이 검증 구간으로 넘어가는 2021년 공시분은 검증 단계 학습에서 뺐다(엠바고). 최종 모델은 학습 구간 전체로 학습하고, 그 라벨 창은 평가 시작 전에 끝난다. 공시 단위 오류(자산 5경 원 등)는 같은 회사의 공시로 확인된 것만 고쳤다. A-3: 기업 단위 분할은 검증 기업의 87%가 학습에도 나와 측정 불가(새 기업만 492건·사건 2건).");
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
  card(s, x2, TOP, w2, 3.1, "기업 단위 분할은 측정 불가", [], { headColor: C.accent1 });
  s.addText("87%", { x: x2 + 0.3, y: TOP + 0.75, w: w2 - 0.6, h: 1.0, fontSize: 54, bold: true, color: C.accent1, isTextBox: true, margin: 0 });
  s.addText("검증 구간 기업 중 학습에도 등장하는 비율. 새 기업만 남기면 492건 · 사건 2건이다.",
    { x: x2 + 0.3, y: TOP + 1.85, w: w2 - 0.6, h: 1.0, fontSize: 16, color: C.text1, isTextBox: true, margin: 0, valign: "top" });
}

// ---- 6 perf (대표 그림)
{
  const s = content("데이터와 성능", "3 · 성능", "높은 성능의 상당 부분은 이미 부실을 겪은 기업에서 나온다",
    "[4:10–5:40] ★ 핵심 장. 전체 표본 PR-AUC는 0.227(평가)이지만 평가 사건 158건 중 107건(68%)이 이미 부실을 겪은 기업이다. 과거 부실 여부 하나만으로 순위를 매겨도 검증 PR-AUC 0.214가 나온다. 그래서 '관측 기간 내 첫 부실'을 주 분석으로 바꿨다 — 이 결정은 검증 구간 근거로 내렸다. 첫 부실 평가 PR-AUC는 0.091, 기준선의 8.0배로 순위는 무작위보다 낫지만, 정밀도 30%를 지키면 51건 중 1건만 잡는다. 이 값은 라벨·데이터 오류를 고친 뒤 기준을 먼저 고정하고 다시 낸 '재평가'다 — 평가 구간을 이미 여러 번 열었으므로 독립 검증이 아니다. 2015년 이전 이력은 모른다.");
  s.addImage({ path: "/Users/john9/Desktop/h-up/project/results/final/대표그림.png", x: 1.2, y: 1.75, w: 10.9, h: 4.76, objectName: "대표 그림" });
  s.addText("첫 부실 평가 PR-AUC 0.091 (기준선의 8.0배) · 정밀도 30%에서 51건 중 1건 · 과거 부실 여부 하나만으로도 검증 PR-AUC 0.214",
    { x: M, y: 6.5, w: CW, h: 0.4, fontSize: 14, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
}

// ---- 7 explanation audit
{
  const s = content("데이터와 성능", "3 · 설명 감사", "설명은 모델을 반영하는가, 재무 사실과 맞는가",
    "[5:40–6:50] ★ 두 번째 핵심. ① 삭제 검사: SHAP이 지목한 변수 하나를 중앙값으로 바꾸면 부실확률이 평균 26%p 떨어지고 무작위는 1.3%p — 모델이 그 근거를 실제로 쓴다(원인이라는 뜻은 아님). ② 사실 단정 검사: 위험 쪽 판정이 표본 중앙값 기준이라 '순손실 상태입니다'가 흑자 기업에도 붙을 수 있었다. 첫 부실 집단 위험 상위 10% 카드 2,128줄 중 307줄(14.4%)이 그랬다 — 반복 부실 집단은 0%. 절대 기준선을 넘었을 때만 단정하도록 고쳐 같은 기준에서 0. 정민재의 카드 문안 검토에서 나온 지적이다. ③ 보류: 단위 의심·핵심값 결측·설명 불안정·방향 충돌이면 설명 대신 사유를 낸다. 모두 우리 기준으로 다시 잰 것이고 사람 검증은 없다. 설계 비교(매칭·가중 등)는 점추정 차이만 있고 차이 검정을 하지 않아 우열을 말하지 않는다.");
  const w = (CW - 0.6) / 3;
  stat(s, M, TOP + 0.05, w, "20.7배", "삭제 검사 — SHAP 상위 1개 치환 시 확률 하락 0.263 vs 무작위 0.013 (검증 위험 상위 300건)", C.accent2);
  stat(s, M + w + 0.3, TOP + 0.05, w, "14.4%", "사실 단정 오류 → 고친 뒤 같은 기준에서 0. 첫 부실 집단 위험 상위 10% 카드 2,128줄 중 307줄 (반복 부실 집단 0%)", C.accent1);
  stat(s, M + 2 * (w + 0.3), TOP + 0.05, w, "2.2%", "설명 보류율 — 같은 카드 416장 중 9장 (설명 불안정 8 · 단위 의심 1 · 핵심값 결측 1)");
  callout(s, 4.7, [
    { text: "모두 우리 검사 기준으로 다시 잰 값이다 — ", options: { bold: true } },
    { text: "'→ 0'은 같은 기준에서의 수치이고 사람 검증은 없다. 인위적 오류 4종은 433건 모두 보류됐지만 이는 규칙 연결 확인일 뿐 실효성 증거가 아니다." },
  ], 1.1);
}

// ---- 8 trajectory
{
  const s = content("데이터와 성능", "3 · 탐색적 분석", "사건 기업은 3년 전부터 나빴다 (사후 중앙값)",
    "[6:50–7:30] 사건 기업만 골라 사건 시점에서 거꾸로 본 중앙값이다 — 예측력의 증거가 아니라 궤적 기술이고, 사건 기업에는 반복 부실이 많이 섞여 있다. 이자보상배율이 3년 전부터 음수다. 그래서 1년 남짓한 창의 예측은 조기 경보라기보다 '이미 나빠진 기업 찾기'에 가깝다. 2주차에 넣은 변화량 변수의 판별력은 수준값보다 훨씬 약하다 — 수준값 1위가 변화량·증가율 1위의 약 7배, ΔROA의 약 16배. (초판의 '약 50배'는 결과 파일과 맞지 않아 정정했다.)");
  table(s, [
    ["중앙값", "t-3", "t-2", "t-1", "정상군"],
    ["이자보상배율", "−0.30", "−0.80", "−1.02", "+1.94"],
    ["영업이익률", "−8.1%", "−13.8%", "−20.0%", "+3.7%"],
    ["ROA", "−11.1%", "−14.0%", "−18.2%", "+2.0%"],
    ["영업현금흐름/매출", "−5.4%", "−6.6%", "−7.3%", "+5.2%"],
  ], M, TOP, 7.6, [2.8, 1.2, 1.2, 1.2, 1.2], { highlight: [1], hlColor: "F6E3D8", size: 15, rowH: 0.52 });
  const x2 = M + 8.1, w2 = CW - 8.1;
  s.addText("약 7배", { x: x2, y: TOP, w: w2, h: 1.1, fontSize: 54, bold: true, color: C.accent1, isTextBox: true, margin: 0 });
  s.addText("수준값 1위(2년연속영업손실 2.64) ÷ 변화량·증가율 1위(자산증가율 0.38). ΔROA(0.16)와 비교하면 약 16배. 변화가 아니라 수준이 이미 신호다.",
    { x: x2, y: TOP + 1.15, w: w2, h: 1.7, fontSize: 15, color: C.text2, isTextBox: true, margin: 0, valign: "top" });
  callout(s, 5.2, "사건 기업만 골라 거꾸로 본 사후 중앙값이다 — 예측력의 증거가 아니라, '이미 나빠진 기업 찾기'에 가깝다는 궤적 기술이다.");
}

// ---- 9 shap-global
pres.addSection({ title: "SHAP과 설명 카드" });
{
  const s = content("SHAP과 설명 카드", "4 · SHAP 전역 기여도", "모델이 가장 많이 보는 것은 수익성",
    "[7:30–8:20] 평균 |SHAP| 상위 8개. ROA와 총자산영업이익률이 압도적이고, 유동성·자본잠식·규모가 뒤를 잇는다. SHAP은 엠바고 학습 표본(9,273행·사건 204건)으로 계산했다. 사건이 적어 시드에 따라 SHAP이 흔들린다. 처음엔 SHAP 평균의 부호가 시드 5개에서 유지되는지 봤는데 기여도 상위 변수가 탈락했다 — SHAP 평균은 기업마다 +/−가 상쇄된 잡음이었다. 카드가 말하는 건 방향이므로 값↔SHAP 상관의 부호로 바꿨다. 12개가 통과했고 그중 카드에 오르는 건 8개(변화량 2개·결측 더미 2개는 문장으로 만들지 않는다).");
  const vars = ["ROA", "총자산영업이익률", "유동비율", "자본잠식률", "로그자산", "순이익률", "총자산회전율", "이자보상배율"];
  const vals = [0.380, 0.362, 0.167, 0.165, 0.156, 0.146, 0.128, 0.121];
  s.addChart(pres.charts.BAR, [{ name: "평균 |SHAP|", labels: vars.slice().reverse(), values: vals.slice().reverse() }], {
    x: M, y: TOP - 0.1, w: 7.4, h: 4.7, barDir: "bar", chartColors: [H.accent2],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 12, dataLabelFontFace: "+mn-lt", dataLabelColor: H.dk1,
    catAxisLabelFontFace: "+mn-lt", catAxisLabelFontSize: 13, catAxisLabelColor: H.dk2, valAxisHidden: true, valAxisMaxVal: 0.47,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false,
    showTitle: true, title: "평균 |SHAP| 상위 8개 (학습 구간)", titleFontFace: "+mn-lt", titleFontSize: 14, titleColor: H.dk2, objectName: "SHAP 전역 기여도",
  });
  card(s, M + 7.9, TOP, CW - 7.9, 4.5, "안정성 필터 — 기준을 한 번 잘못 만들었다", [
    "처음 기준(SHAP 평균의 부호)으로는 기여도 상위 변수가 탈락했다.",
    "SHAP 평균은 기업마다 +/−가 상쇄된 잡음이었다. 카드가 말하는 것은 방향이므로 값↔SHAP 상관의 부호로 바꿨다.",
    "→ 12개 통과, 그중 카드에 오르는 8개만 문장으로 쓴다.",
  ], { headColor: C.accent1, size: 15 });
}

// ---- 10 shap-check
{
  const s = content("SHAP과 설명 카드", "4 · SHAP 검산", "카드 변수 8개는 로지스틱 계수와 방향이 모두 맞다",
    "[8:20–9:00] 카드에 오르는 8개 변수는 SHAP 방향(값과 SHAP의 상관)과 로지스틱 계수 부호가 모두 일치한다. 이 계수는 결측 더미를 포함한 W09 적합 기준이다. 영업이익률은 VIF 10.17로 ROA와 겹쳐 로지스틱 계수가 반대로 나오지만 안정성 필터에서 탈락해 카드에 오르지 않는다. Δ부채비율은 처음에 '공선성 때문'이라 적었는데 정민재 검토로 틀린 게 드러났다 — VIF 1.31로 가장 낮고 판별력이 약한 것. 군집 보정(기업당 4.44년) 후 유의 변수는 18개에서 12개로 줄었다.");
  table(s, [
    ["변수", "SHAP 방향", "로지스틱 계수", "일치"],
    ["ROA", "−0.78", "−0.32", "일치"],
    ["총자산영업이익률", "−0.60", "−0.24", "일치"],
    ["유동비율", "−0.40", "−0.25", "일치"],
    ["자본잠식률", "+0.29", "+0.25", "일치"],
    ["로그자산", "−0.72", "−0.66", "일치"],
    ["순이익률", "−0.53", "−0.19", "일치"],
    ["총자산회전율", "−0.78", "−0.64", "일치"],
    ["자기자본비율", "−0.75", "−0.48", "일치"],
  ], M, TOP, 7.6, [2.8, 1.6, 1.9, 1.3], { size: 14, rowH: 0.43 });
  s.addText("SHAP 방향 = 값과 SHAP의 상관 · 로지스틱 계수는 결측 더미 포함 적합(W09)", { x: M, y: 5.95, w: 7.6, h: 0.35, fontSize: 11, color: C.text2, isTextBox: true, margin: 0 });
  const x2 = M + 8.1, w2 = CW - 8.1;
  s.addText("8개 중 8개 일치", { x: x2, y: TOP, w: w2, h: 0.8, fontSize: 28, bold: true, color: C.accent2, isTextBox: true, margin: 0 });
  card(s, x2, TOP + 1.0, w2, 1.5, "영업이익률", ["VIF 10.17 — 로지스틱 계수가 반대지만 안정성 필터에서 탈락"], { size: 14 });
  card(s, x2, TOP + 2.7, w2, 1.75, "Δ부채비율 (정민재 검토)", ["공선성이 아니라 판별력이 약한 것(VIF 1.31). 군집 보정 후 유의하지 않다."], { size: 14 });
}

// ---- 11 card
{
  const s = content("SHAP과 설명 카드", "4 · 설명 카드", "사람이 읽는 문서로 — 설명 카드 예시",
    "[9:00–9:50] 'ROA SHAP +0.34'는 설명이 아니다. 검증 구간 실제 사건 기업의 익명 카드다. 확률은 isotonic 보정본에서 뽑는다 — 보정 전 평균 예측이 실제의 7.6배였다. 보정은 두 집단을 합쳐 맞췄고 집단별 보정은 확인하지 않았다. 위험을 낮춘 요인이 없으면 '해당 없음'이라 적는다 — 위험 요인만 나열하면 확증 편향 도구가 된다. 시연 문서(results/demo/세_사례.md)에 정상·교정·보류 세 사례가 있다.");
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: TOP, w: 7.4, h: 3.7, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: H.accent5, width: 1 }, objectName: "설명 카드" });
  s.addText([
    { text: "익명 사례 · 검증 구간 · 실제 사건 기업", options: { fontSize: 12, color: C.text2, breakLine: true, paraSpaceAfter: 4 } },
    { text: "모형 추정 부실확률 55.5%", options: { fontSize: 22, bold: true, color: C.accent1, breakLine: true, paraSpaceAfter: 10 } },
    { text: "위험을 높인 요인", options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "자본잠식이 진행되어 있습니다 (실측 94.9%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "자산 규모에 비해 벌어들이는 이익이 적습니다 (실측 −29.0%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "자산 대비 영업이익이 부족합니다 (실측 −15.9%)", options: { fontSize: 14, bullet: true, breakLine: true } },
    { text: "자기자본이 얇아 손실을 흡수할 여력이 작습니다 (실측 1.3%)", options: { fontSize: 14, bullet: true, breakLine: true, paraSpaceAfter: 10 } },
    { text: "위험을 낮춘 요인", options: { fontSize: 15, bold: true, breakLine: true, paraSpaceAfter: 4 } },
    { text: "해당 없음 (안정 변수 중 위험을 낮춘 항목이 없습니다)", options: { fontSize: 14, bullet: true } },
  ], { x: M + 0.35, y: TOP + 0.25, w: 6.7, h: 3.2, valign: "top", isTextBox: true, margin: 0, objectName: "카드 문안" });
  const x2 = M + 7.9, w2 = CW - 7.9;
  card(s, x2, TOP, w2, 1.7, "확률은 보정본에서", ["보정 전 평균 예측이 실제의 7.6배였다. 보정은 두 집단을 합쳐 맞췄다(집단별 보정 미확인)."], { size: 14, headColor: C.accent2 });
  card(s, x2, TOP + 2.0, w2, 1.7, "낮춘 요인도 적는다", ["없으면 \"해당 없음\"이라고 적는다. 위험 요인만 나열하면 확증 편향을 부른다."], { size: 14, headColor: C.accent2 });
}

// ---- 12 scope & progress
pres.addSection({ title: "진척과 검증 범위" });
{
  const s = content("진척과 검증 범위", "5 · 진척과 검증 범위", "분석은 앞당겨 끝냈고, 남은 것은 정리와 한계 확인이다",
    "[9:50–11:00] 실무자 인터뷰를 제외해 '설명이 실무자에게 납득되는가'는 확인할 수 없다 — 확인 범위는 '설명이 모델을 정직하게 반영하는가'까지다. 계획상 11~14주차 분석(충실도·오분류·담기지 않는 정보·설명 개선)은 앞당겨 했다. 남은 것은 보고서·진로 정리·성과발표, 그리고 한계 확인 — 재무 API가 최신 정정본만 줘서 21.4% 행이 T 이후 정정본 값이다(민감도에서 첫 부실 성능이 더 낮다), 2015년 이전 부실 이력은 보이지 않는다. 2차 면담에서 주 분석 변경(첫 부실)·매칭 학습 폐기·장학금 계획 변경을 보고한다.");
  const w = (CW - 0.4) / 2;
  card(s, M, TOP, w, 1.4, "확인 가능", ["설명이 모델을 정직하게 반영하는가 (충실도)"], { headColor: C.accent2, size: 17 });
  card(s, M + w + 0.4, TOP, w, 1.4, "확인 불가", ["설명이 실무자에게 납득되는가 — 실무자 평가를 제외했다"], { headColor: C.accent1, size: 17, dash: true, fill: C.background1, line: C.accent1 });
  card(s, M, 3.65, w, 2.6, "앞당겨 끝낸 것 (W11~W14 분석)", ["설명 충실도 · 사실 단정 검사 · 보류 기능", "오분류 사례 · 공시 신호(담기지 않는 정보)", "오류 수정 후 재평가 2회 (기준 사전 고정)"], { size: 15 });
  card(s, M + w + 0.4, 3.65, w, 2.6, "남은 것", ["보고서 · 진로 판단 · 성과발표 (W15)", "한계: 정정본 재무(21.4% 행) · 2015년 이전 이력", "2차 면담: 주 분석 변경 · 매칭 폐기 · 장학금 계획 보고"], { size: 15 });
}

// ---- 13 rule-break
{
  const s = content("진척과 검증 범위", "5 · 규칙 위반 신고", "평가 구간을 계획보다 여러 번 열었다",
    "[11:00–12:00] ★ 빼지 말 것. '평가 구간은 최종 1회만 연다'고 정해두고 개발 중 3번 더 열었고, 오류를 고친 뒤 두 번 재평가했다(데이터 오류 10-11, 라벨 오류 10-13). 재평가 때는 기준을 문서(docs/13)에 먼저 고정하고 커밋했다. 주 분석을 첫 부실로 바꾼 결정은 검증 구간 근거로 먼저 내렸고, 평가 구간의 반복 부실 비중은 그 뒤에 처음 봤다. 모델 선택·하이퍼파라미터·변수 집합을 평가 구간 결과로 정한 적은 없다. 그래도 여러 번 본 것은 사실이라, 평가 구간 수치는 독립 검증이 아니라 '오류 수정 후 재평가'로 부른다. 진짜 새 평가 데이터는 2027년 4월에 생긴다.", true);
  const rows = [
    ["#", "시점", "그 결과로 바꾼 것"],
    ["1–3", "개발 중 (배선 확인 · 윈저라이즈 · 결측 더미 실험)", "없음 — 3번은 잘못이라 검증 구간에서 재실행"],
    ["4", "최종 모델 확정 후 (계획된 1회)", "—"],
    ["5", "데이터 오류 수정 후 재평가 (10-11)", "없음 — 기준을 먼저 문서로 고정"],
    ["6", "라벨 오류 수정 후 재평가 2 (10-13)", "없음 — 기준을 먼저 문서로 고정"],
  ].map((r, ri) => r.map((cell, ci) => ({ text: cell, options: { bold: ri === 0, color: ri === 0 ? H.accent6 : H.lt1, fill: { color: ri === 0 ? "1F2C3A" : H.dk1 }, align: "left", valign: "middle" } })));
  s.addTable(rows, { x: M, y: TOP, w: CW, colW: [0.8, 5.6, CW - 6.4], fontSize: 15, rowH: 0.47,
    border: { type: "solid", pt: 0.75, color: "3A4757" }, margin: [0.04, 0.12, 0.04, 0.12], objectName: "개봉 기록" });
  s.addText("평가 구간 수치는 독립 검증이 아니라 '오류 수정 후 재평가'다.", { x: M, y: 4.75, w: CW, h: 0.8, fontSize: 26, bold: true, color: C.accent3, isTextBox: true, margin: 0 });
  s.addText("모델 선택·하이퍼파라미터·변수 집합을 평가 구간 결과로 정한 적은 없다. 주 분석 전환은 검증 구간 근거로 먼저 결정했다.",
    { x: M, y: 5.6, w: CW, h: 0.7, fontSize: 15, color: C.accent6, isTextBox: true, margin: 0 });
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
