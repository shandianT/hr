import fs from "node:fs";

const prototypePath = new URL("招聘Agent_核心功能2_画像匹配与部门决定Demo.html", import.meta.url);
const source = fs.readFileSync(prototypePath, "utf8");
const scriptMatch = source.match(/<script>([\s\S]*)<\/script>/);

if (!scriptMatch) throw new Error("screening demo script is missing");
new Function(scriptMatch[1]);

for (const requiredToken of [
  "简历筛选",
  "从简历到负责人决定",
  "简历与岗位",
  "筛选卡",
  "用人负责人决定",
  "已接收",
  "开始筛选",
  "中性摘要",
  "关键支持",
  "待核实",
  "风险或证据不足",
  "进入一面",
  "稍后复核",
  "本岗位不推进",
  "提交你的决定",
  "运行详情",
  "Agent Activity",
  "测试其他情况",
  "外部效果均为合成",
  "function escapeHTML",
  "function escapeAttr",
  "function renderScreening()",
  "@media(max-width:720px)",
  ".intake{grid-template-columns:1fr}",
  ".signal-grid,.choices,.runtime-grid{grid-template-columns:1fr}",
  ".decision-form{grid-template-columns:1fr}",
  ".primary-row .btn{width:100%",
  ".surface-actions .btn{width:100%",
  ".step>span:last-child>span{display:none}",
  ".choice input[type=\"radio\"]{width:18px;height:18px",
  "function focusAfterRender",
  "let lastDrawerTrigger=''",
  "role=\"dialog\"",
  " inert aria-hidden=\"true\"",
  "data-panel=\"runtime-details\"",
  "招聘Agent_核心功能3_候选人约面Demo.html",
]) {
  if (!source.includes(requiredToken)) throw new Error(`screening demo token is missing: ${requiredToken}`);
}

for (const forbiddenToken of ["86 分", "AI 推荐通过", "候选人排行", "自动 shortlist", "推荐进入一面", "不满足 / 证据不足"]) {
  if (source.includes(forbiddenToken)) throw new Error(`screening demo contains forbidden decision shorthand: ${forbiddenToken}`);
}

const machineStart = source.indexOf("const ScreeningMachine");
const machineEnd = source.indexOf("let screeningState");
const machineSource = source.slice(machineStart, machineEnd);
if (machineStart < 0 || machineEnd < machineStart) throw new Error("screening state machine boundary is missing");
if (machineSource.includes("document.") || machineSource.includes("getElementById")) {
  throw new Error("screening state machine is coupled to DOM rendering");
}

const primarySurfaceCopy = source.slice(source.indexOf("function intakeSurface"), source.indexOf("function runtimeDetails"));
for (const hiddenDetail of ["versions.manifest", "request.revision", "request.generation", "quietHours", "Agent Activity", "SLA"]) {
  if (primarySurfaceCopy.includes(hiddenDetail)) {
    throw new Error(`internal detail leaked into the default three-step surface: ${hiddenDetail}`);
  }
}
if (!source.includes('<details class="fold"') || !source.includes('<details class="test-panel"')) {
  throw new Error("runtime and scenario controls are not progressively disclosed");
}
if (source.includes('<details class="fold" open') || source.includes('<details class="test-panel" open')) {
  throw new Error("progressive disclosure panels are open by default");
}

const app = { innerHTML: "" };
const toast = { textContent: "", classList: { add() {}, remove() {} }, _t: null };
globalThis.location = { href: "http://localhost/screening" };
globalThis.history = { replaceState() {} };
globalThis.addEventListener = () => {};
globalThis.setTimeout = () => 0;
globalThis.clearTimeout = () => {};
globalThis.document = {
  getElementById(id) { return id === "app" ? app : toast; },
  querySelectorAll() { return []; },
  querySelector() { return null; },
};
new Function(scriptMatch[1])();

const demo = globalThis.__screeningDemoTest;
if (!demo?.Machine || typeof demo.runScreening !== "function") {
  throw new Error("screening demo behavior hook is missing");
}
const { Machine } = demo;

const expectedFixtures = [
  "normal", "lowEvidence", "prohibited", "versionChanged",
  "hold", "overdue", "recipientError", "authority",
];
if (JSON.stringify(Object.keys(Machine.FIXTURES)) !== JSON.stringify(expectedFixtures)) {
  throw new Error("screening demo does not expose the exact eight fixtures");
}
for (const key of expectedFixtures) {
  if (Machine.createInitial(key).externalEffects !== 0) throw new Error(`${key} starts with a real external effect`);
}

if (!app.innerHTML.includes("开始筛选") || (app.innerHTML.match(/class="btn primary"/g) || []).length !== 1) {
  throw new Error("first screen does not have exactly one primary action");
}
if ((app.innerHTML.match(/class="step /g) || []).length !== 3) {
  throw new Error("first screen is not expressed as exactly three product steps");
}
if (app.innerHTML.includes('name="department-decision"')) {
  throw new Error("department controls compete with the first screen");
}
if (app.innerHTML.indexOf('data-action="run-screening"') > app.innerHTML.indexOf('class="surface-body"')) {
  throw new Error("first-screen primary action is buried below the resume cards");
}

demo.runScreening();
if (demo.state.view !== 2 || demo.state.request.status !== "OPEN") {
  throw new Error("default UI path does not stop on the screening card after automatic processing");
}
if (!app.innerHTML.includes("中性摘要") || !app.innerHTML.includes("查看负责人待办")) {
  throw new Error("screening card does not lead with a neutral summary and one next action");
}
if (app.innerHTML.includes('name="department-decision"')) {
  throw new Error("screening card silently skips into the decision form");
}

function advanceToDepartment(key) {
  let state = Machine.createInitial(key);
  state = Machine.transition(state, { type: "ADVANCE" });
  state = Machine.transition(state, { type: "ADVANCE" });
  state = Machine.transition(state, { type: "ADVANCE" });
  return state;
}

let state = advanceToDepartment("normal");
if (state.step !== 3 || state.caseStage !== "AWAITING_DEPARTMENT_DECISION") {
  throw new Error("normal fixture does not reach the department decision gate");
}
if (state.assessment.status !== "READY" || state.request.status !== "OPEN") {
  throw new Error("normal fixture has no ready assessment or unique open request");
}
if (state.selection !== "" || state.decisionHistory.length !== 0) {
  throw new Error("department decision is preselected or already inferred");
}
demo.setState(state);
if (!app.innerHTML.includes("用人负责人决定") || /name="department-decision"[^>]*checked/.test(app.innerHTML)) {
  throw new Error("rendered decision task is missing or has a preselected answer");
}
const normalRequestId = state.request.id;
state = Machine.transition(state, { type: "SELECT_DECISION", value: "INVITE" });
state = Machine.transition(state, { type: "SET_REASON", value: "当前证据足以进入一面继续核验未知项" });
state = Machine.transition(state, { type: "SUBMIT_DECISION", actionId: "decision-normal-1" });
if (state.caseStage !== "INTERVIEWING" || state.request.status !== "CLOSED") {
  throw new Error("authorized INVITE does not move the case to interviewing");
}
if (state.decisionHistory.length !== 1 || state.decisionHistory[0].actorType !== "HUMAN") {
  throw new Error("normal decision has no immutable HUMAN receipt");
}
if (state.request.id !== normalRequestId || state.candidateCommunication !== "NOT_SENT" || state.externalEffects !== 0) {
  throw new Error("decision created another task, a real effect, or implicit candidate communication");
}

state = advanceToDepartment("lowEvidence");
const lowCounts = Machine.dimensionCounts(state);
if (lowCounts.UNKNOWN < 2 || state.caseStage === "CLOSED" || state.request.status !== "OPEN") {
  throw new Error("low-evidence fixture closes or hides the application instead of opening human review");
}
if (state.decisionHistory.length !== 0) throw new Error("low-evidence fixture inferred a hiring decision");
state = Machine.transition(state, { type: "VIEW_STAGE", index: 2 });
demo.setState(state);
if (!app.innerHTML.includes("信息不足不会自动淘汰") || !app.innerHTML.includes("查看负责人待办")) {
  throw new Error("low-evidence UI implies rejection or removes the human-review path");
}

state = advanceToDepartment("prohibited");
if (state.publish.status !== "BLOCKED" || state.request.status !== "NONE" || state.externalEffects !== 0) {
  throw new Error("prohibited feature was published or produced an external effect");
}
state = Machine.transition(state, { type: "RECOVER_PROHIBITED" });
state = Machine.transition(state, { type: "ADVANCE" });
state = Machine.transition(state, { type: "ADVANCE" });
if (state.request.status !== "OPEN" || state.recoveryTrail.length !== 1 || state.externalEffects !== 0) {
  throw new Error("prohibited-feature branch cannot recover with an audit trail");
}

state = advanceToDepartment("versionChanged");
if (!state.stale || state.request.status !== "SUPERSEDED" || state.caseStage !== "SCREENING") {
  throw new Error("version change does not atomically invalidate the old material and task");
}
const staleAttemptCount = state.attempts.length;
state = Machine.transition(state, {
  type: "SUBMIT_DECISION", decision: "INVITE", reason: "旧卡测试",
  requestRevision: 1, actionId: "stale-card-1",
});
if (state.decisionHistory.length || state.attempts.length !== staleAttemptCount + 1 || state.attempts.at(-1).result !== "STALE") {
  throw new Error("old department card can still write the current state");
}
state = Machine.transition(state, { type: "REBUILD_VERSION" });
if (state.stale || state.request.status !== "OPEN" || state.request.revision !== 2 || state.versions.manifest !== "SIM-24081-r2") {
  throw new Error("version-change branch does not produce a current replacement task");
}

state = advanceToDepartment("hold");
state = Machine.transition(state, { type: "SELECT_DECISION", value: "HOLD" });
state = Machine.transition(state, { type: "SET_REASON", value: "等待补充商业结果边界" });
state = Machine.transition(state, { type: "SET_REVISIT", value: "明天 10:00" });
state = Machine.transition(state, { type: "SUBMIT_DECISION", actionId: "hold-1" });
if (state.request.status !== "ON_HOLD" || state.request.revision !== 2 || state.request.generation !== 2 || state.reminders.nextCheck !== "明天 10:00") {
  throw new Error("HOLD does not stop reminders or create the next request revision");
}
state = Machine.transition(state, { type: "REACH_REVISIT" });
if (state.request.status !== "OPEN" || state.request.revision !== 3 || state.request.generation !== 3 || state.selection !== "") {
  throw new Error("HOLD revisit does not reopen exactly one unselected current task");
}

state = advanceToDepartment("overdue");
state = Machine.transition(state, { type: "ADVANCE_REMINDER" });
state = Machine.transition(state, { type: "ADVANCE_REMINDER" });
state = Machine.transition(state, { type: "ADVANCE_REMINDER" });
if (state.reminders.ordinal !== 2 || state.exception?.status !== "OPEN" || state.decisionHistory.length !== 0) {
  throw new Error("reminder exhaustion does not stop at one exception without inferring a decision");
}
const exceptionId = state.exception.id;
state = Machine.transition(state, { type: "ADVANCE_REMINDER" });
if (state.exception.id !== exceptionId || state.reminders.ordinal !== 2) {
  throw new Error("reminder exhaustion creates duplicate exception bundles or infinite reminders");
}

state = advanceToDepartment("recipientError");
if (state.notification.status !== "BLOCKED" || state.externalEffects !== 0 || state.exception?.severity !== "P0") {
  throw new Error("wrong recipient was not blocked before synthetic delivery");
}
const recipientTask = `${state.request.id}:${state.request.revision}`;
state = Machine.transition(state, { type: "REPAIR_RECIPIENT" });
if (state.notification.status !== "DELIVERED_SYNTHETIC" || state.externalEffects !== 0 || `${state.request.id}:${state.request.revision}` !== recipientTask) {
  throw new Error("recipient repair loses the authoritative task or creates a real effect");
}

state = advanceToDepartment("authority");
state = Machine.transition(state, {
  type: "SUBMIT_DECISION", decision: "INVITE", reason: "Agent 越权测试",
  actorType: "AGENT", actorId: "screening-worker", actionId: "agent-attempt-1",
});
if (state.decisionHistory.length || state.attempts.at(-1).result !== "AUTHORITY_DENIED") {
  throw new Error("Agent or Service can submit a department hiring decision");
}
state = Machine.transition(state, {
  type: "SUBMIT_DECISION", decision: "INVITE", reason: "旧卡测试",
  requestRevision: 0, actionId: "old-request-attempt-1",
});
if (state.decisionHistory.length || state.attempts.at(-1).result !== "STALE") {
  throw new Error("stale request revision can submit a decision");
}
const humanAction = {
  type: "SUBMIT_DECISION", decision: "INVITE", reason: "当前授权人确认进入一面",
  actorType: "HUMAN", actorId: "hiring-owner-zhou", actionId: "human-once-1",
};
state = Machine.transition(state, humanAction);
state = Machine.transition(state, humanAction);
if (state.decisionHistory.length !== 1 || state.receipts.filter((item) => item.actionId === "human-once-1").length !== 1) {
  throw new Error("double submit creates duplicate decision effects");
}

let xssDraft = advanceToDepartment("hold");
xssDraft = Machine.transition(xssDraft, { type: "SELECT_DECISION", value: "HOLD" });
xssDraft = Machine.transition(xssDraft, { type: "SET_REASON", value: "</textarea><img data-xss onerror=alert(1)>" });
xssDraft = Machine.transition(xssDraft, { type: "SET_REVISIT", value: "\"><svg data-revisit-xss onload=alert(2)>" });
demo.setState(xssDraft);
if (app.innerHTML.includes("<img data-xss") || app.innerHTML.includes("<svg data-revisit-xss")) {
  throw new Error("malicious reason or revisit value is rendered as active draft HTML");
}
if (!app.innerHTML.includes("&lt;img data-xss") || !app.innerHTML.includes("&quot;&gt;&lt;svg data-revisit-xss")) {
  throw new Error("malicious reason or revisit value is not visibly escaped in the form");
}
xssDraft = Machine.transition(xssDraft, { type: "SUBMIT_DECISION", actionId: "xss-escape-1" });
demo.setState(xssDraft);
if (app.innerHTML.includes("<img data-xss") || app.innerHTML.includes("<svg data-revisit-xss")) {
  throw new Error("malicious reason or revisit value is rendered as active receipt HTML");
}
if (!app.innerHTML.includes("&lt;img data-xss") || !app.innerHTML.includes("&lt;svg data-revisit-xss")) {
  throw new Error("malicious reason or revisit value is not visibly escaped in the receipt");
}

let hostileEvidence = advanceToDepartment("normal");
hostileEvidence.view = 2;
hostileEvidence.dimensions[0].name = "<script data-evidence-xss>";
hostileEvidence.dimensions[0].claim = "<img data-claim-xss onerror=alert(3)>";
demo.setState(hostileEvidence);
if (app.innerHTML.includes("<script data-evidence-xss") || app.innerHTML.includes("<img data-claim-xss")) {
  throw new Error("fixture evidence is rendered as active HTML");
}
if (!app.innerHTML.includes("&lt;script data-evidence-xss") || !app.innerHTML.includes("&lt;img data-claim-xss")) {
  throw new Error("fixture evidence is not escaped through the common HTML boundary");
}

console.log("PASS | recruiting Agent minimal screening demo | 8 fixtures | escaped UI");
