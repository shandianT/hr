import fs from "node:fs";

const prototypePath = new URL("招聘Agent_核心功能3_候选人约面Demo.html", import.meta.url);
const source = fs.readFileSync(prototypePath, "utf8");
const scriptMatch = source.match(/<script>([\s\S]*)<\/script>/);

if (!scriptMatch) throw new Error("scheduling demo script is missing");
new Function(scriptMatch[1]);

for (const requiredToken of [
  "候选人约面",
  "选择时间，确认后才算安排好",
  "选择时间",
  "正在确认",
  "面试已安排",
  "提交这个时间",
  "现在还不是已预定",
  "日历、会议和邀请三项当前回执都已确认",
  "录制说明",
  "已送达",
  "尚未选择，录制保持关闭",
  "查看或更改录制选择",
  "预约不依赖这项选择",
  "同意本次面试录制",
  "不录制",
  "告知送达不等于同意",
  "接受会议邀请、打开会议链接或参加面试，都不代表你同意录制",
  "正在改期，原安排仍有效",
  "运行详情",
  "测试其他情况",
  "12 个合成危险场景",
  "外部效果均为合成",
  "function escapeHTML",
  "function escapeAttr",
  "function renderScheduling",
  "function focusAfterRender",
  "@media(max-width:720px)",
  "@media(prefers-reduced-motion:reduce)",
  ".meeting-card,.booking-card{grid-template-columns:1fr}",
  ".recording-status,.record-choices,.notice-grid,.runtime-grid{grid-template-columns:1fr}",
  ".primary-row .btn{width:100%",
  ".step>span:last-child>span{display:none}",
  'aria-live="polite"',
]) {
  if (!source.includes(requiredToken)) throw new Error("scheduling demo token is missing: " + requiredToken);
}

for (const forbiddenToken of [
  "已为你预留",
  "点击即已预约",
  "接受邀请即同意录制",
  "默认同意录制",
  "拒绝录制可能影响面试",
]) {
  if (source.includes(forbiddenToken)) throw new Error("scheduling demo contains misleading copy: " + forbiddenToken);
}

const machineStart = source.indexOf("const SchedulingMachine");
const machineEnd = source.indexOf("let schedulingState");
if (machineStart < 0 || machineEnd < machineStart) throw new Error("scheduling state machine boundary is missing");
const machineSource = source.slice(machineStart, machineEnd);
if (machineSource.includes("document.") || machineSource.includes("getElementById") || machineSource.includes("querySelector")) {
  throw new Error("scheduling state machine is coupled to DOM rendering");
}

const app = { innerHTML: "" };
const toast = { textContent: "", classList: { add() {}, remove() {} }, _t: null };
globalThis.location = {
  href: "http://localhost/scheduling?scenario=normal",
  search: "?scenario=normal",
};
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

const demo = globalThis.__schedulingDemoTest;
if (!demo?.Machine || typeof demo.renderScheduling !== "function") {
  throw new Error("scheduling demo behavior hook is missing");
}
const { Machine } = demo;
const expectedDangerFixtures = [
  "expiredProposal",
  "slotConflict",
  "partialSuccess",
  "lostResponse",
  "concurrentClaim",
  "reschedule",
  "staleCallback",
  "calendarRevoked",
  "noCommonSlot",
  "invalidLink",
  "noticeNoChoice",
  "lateParticipant",
];
if (JSON.stringify(Machine.DANGER_FIXTURE_KEYS) !== JSON.stringify(expectedDangerFixtures)) {
  throw new Error("scheduling demo does not expose the exact twelve danger fixtures");
}
if (Object.keys(Machine.FIXTURES).length !== 13 || Machine.FIXTURES.normal.danger !== false) {
  throw new Error("scheduling demo fixture catalog must contain one default plus twelve dangers");
}
for (const key of Object.keys(Machine.FIXTURES)) {
  if (Machine.createInitial(key).externalEffects !== 0) throw new Error(key + " starts with a real external effect");
}

if ((app.innerHTML.match(/class="step /g) || []).length !== 3) {
  throw new Error("default scheduling path is not expressed as exactly three product steps");
}
if (!app.innerHTML.includes("哪一个时间方便？") || !app.innerHTML.includes("提交这个时间")) {
  throw new Error("default page does not lead with candidate slot selection");
}
if (app.innerHTML.includes('name="recording-choice"')) {
  throw new Error("recording choices compete with the default scheduling step");
}
if ((app.innerHTML.match(/class="btn primary"/g) || []).length !== 1) {
  throw new Error("default selection page must have exactly one visible primary button");
}
if (!app.innerHTML.includes('<details class="fold"') || !app.innerHTML.includes('<details class="test-panel"')) {
  throw new Error("runtime and danger fixtures are not progressively disclosed");
}
if (app.innerHTML.includes('<details class="fold" open') || app.innerHTML.includes('<details class="test-panel" open')) {
  throw new Error("progressive disclosure panels are open by default");
}
if ((app.innerHTML.match(/name="candidate-slot"[^>]*checked/g) || []).length) {
  throw new Error("candidate slot is preselected");
}

function chooseAndSubmit(key, slotId = "slot-1") {
  let state = Machine.createInitial(key);
  state = Machine.transition(state, { type: "SELECT_SLOT", slotId });
  return Machine.transition(state, { type: "SUBMIT_SLOT" });
}

function succeed(state, kind, revision = state.appointment.revision) {
  return Machine.transition(state, {
    type: "RECEIPT_SUCCEEDED",
    kind,
    appointmentRevision: revision,
    receiptId: "SYN-" + kind.toUpperCase() + "-R" + revision,
  });
}

let state = chooseAndSubmit("normal");
if (state.schedulingState !== "BOOKING_PENDING" || state.booking.status !== "NONE" || state.step !== 1) {
  throw new Error("selecting a slot must enter confirmation without creating a booking");
}
if (!state.selectionReceipt || state.receipts.calendar || state.receipts.meeting || state.receipts.invite) {
  throw new Error("slot submission either lacks a selection receipt or fabricates provider receipts");
}
demo.setState(state);
if (!app.innerHTML.includes("正在确认") || !app.innerHTML.includes("现在还不是已预定") || app.innerHTML.includes('class="receipt-hero"')) {
  throw new Error("confirmation page visually overstates a candidate selection as a booking");
}

state = succeed(state, "calendar");
state = succeed(state, "meeting");
if (state.schedulingState !== "BOOKING_PENDING" || state.booking.status !== "NONE") {
  throw new Error("two of three receipts incorrectly commit a booking");
}
state = succeed(state, "invite");
if (state.schedulingState !== "BOOKED" || state.booking.status !== "BOOKED" || state.step !== 2) {
  throw new Error("three current receipts do not commit the booking");
}
if (state.bookingHistory.length !== 1 || !state.currentBooking || state.currentBooking.appointmentRevision !== 1) {
  throw new Error("normal completion does not leave exactly one current booking");
}
state = succeed(state, "invite");
if (state.bookingHistory.length !== 1) throw new Error("duplicate receipt creates a second booking");
demo.setState(state);
if (!app.innerHTML.includes("日历、会议和邀请三项当前回执都已确认") || !app.innerHTML.includes("查看面试安排")) {
  throw new Error("booked page lacks the three-receipt truth and one next action");
}
if (!app.innerHTML.includes("<span>录制说明</span><b>已送达</b>") ||
    !app.innerHTML.includes("<span>你的选择</span><b>尚未选择，录制保持关闭</b>")) {
  throw new Error("booked card does not separate recording notice delivery from the candidate choice");
}
if (/name="recording-choice"[^>]*checked/.test(app.innerHTML)) {
  throw new Error("recording choice is preselected");
}

const bookedSnapshot = JSON.stringify(state.booking);
state = Machine.transition(state, { type: "SET_RECORDING_DRAFT", value: "NO_RECORDING" });
state = Machine.transition(state, { type: "SAVE_RECORDING_CHOICE" });
if (state.recording.choice !== "NO_RECORDING" || state.recording.gate !== "NO_RECORDING" || !state.recording.receipt) {
  throw new Error("explicit no-recording choice does not produce its own receipt");
}
if (JSON.stringify(state.booking) !== bookedSnapshot || state.schedulingState !== "BOOKED") {
  throw new Error("no-recording choice changes or blocks the booking");
}
demo.setState(state);
if (!app.innerHTML.includes("不录制，面试照常进行") || !app.innerHTML.includes("不影响面试和评价机会")) {
  throw new Error("no-recording route is not presented as an equal interview route");
}

state = Machine.createInitial("noticeNoChoice");
const noticeOnlyBooking = JSON.stringify(state.booking);
state = Machine.transition(state, { type: "SET_RECORDING_DRAFT", value: "RECORDING" });
state = Machine.transition(state, { type: "SAVE_RECORDING_CHOICE" });
if (state.recording.gate !== "PENDING_SESSION_GATE" || JSON.stringify(state.booking) !== noticeOnlyBooking) {
  throw new Error("recording choice either claims capture is on or mutates the booking");
}

state = chooseAndSubmit("expiredProposal");
if (state.schedulingState !== "PROPOSAL_OPEN" || state.proposal.revision !== 2 || state.booking.status !== "NONE" || state.selectedSlotId) {
  throw new Error("expired proposal is not rejected into a fresh unselected proposal");
}

for (const key of ["slotConflict", "concurrentClaim"]) {
  state = chooseAndSubmit(key);
  if (state.schedulingState !== "PROPOSAL_OPEN" || !state.conflict || state.booking.status !== "NONE" || state.selectedSlotId) {
    throw new Error(key + " creates a booking instead of returning to a fresh proposal");
  }
  state = Machine.transition(state, { type: "SELECT_SLOT", slotId: "slot-4" });
  state = Machine.transition(state, { type: "SUBMIT_SLOT" });
  if (state.schedulingState !== "BOOKING_PENDING" || state.booking.status !== "NONE") {
    throw new Error(key + " cannot recover through the replacement proposal");
  }
}

state = chooseAndSubmit("partialSuccess");
state = succeed(state, "calendar");
state = Machine.transition(state, {
  type: "PROVIDER_FAILED",
  kind: "meeting",
  appointmentRevision: state.appointment.revision,
});
if (state.schedulingState !== "BOOKING_PENDING" || state.booking.status !== "NONE" ||
    state.exception?.kind !== "BOOKING_PARTIAL_SUCCESS") {
  throw new Error("partial success is displayed as booked or loses its recoverable exception");
}

state = chooseAndSubmit("lostResponse");
state = succeed(state, "calendar");
state = Machine.transition(state, {
  type: "OBSERVE_RESOURCE",
  kind: "meeting",
  appointmentRevision: state.appointment.revision,
  resourceId: "SYN-OBSERVED-MEETING",
});
if (state.receipts.meeting || state.booking.status !== "NONE" || !state.observedResources.meeting) {
  throw new Error("provider observation is incorrectly treated as a current receipt");
}
state = Machine.transition(state, {
  type: "RECONCILE_RESOURCE",
  kind: "meeting",
  appointmentRevision: state.appointment.revision,
});
state = succeed(state, "invite");
if (state.booking.status !== "BOOKED" || state.bookingHistory.length !== 1) {
  throw new Error("lost-response reconciliation cannot produce exactly one booking");
}

state = Machine.createInitial("reschedule");
const oldBookingId = state.currentBooking.id;
state = Machine.transition(state, { type: "SELECT_SLOT", slotId: "slot-4" });
state = Machine.transition(state, { type: "SUBMIT_SLOT" });
if (state.schedulingState !== "RESCHEDULING" || state.appointment.revision !== 2 ||
    state.currentBooking.id !== oldBookingId || state.oldBooking.status !== "BOOKED") {
  throw new Error("reschedule does not retain the old current booking while the new revision is pending");
}
demo.setState(state);
if (!app.innerHTML.includes("原安排仍有效") || !app.innerHTML.includes("8 月 13 日 · 周四")) {
  throw new Error("reschedule confirmation page hides the still-valid old booking");
}
state = succeed(state, "calendar");
state = succeed(state, "meeting");
if (state.currentBooking.id !== oldBookingId || state.oldBooking.status !== "BOOKED") {
  throw new Error("partial reschedule replaces the old booking too early");
}
state = succeed(state, "invite");
if (state.booking.status !== "BOOKED" || state.currentBooking.appointmentRevision !== 2 ||
    state.oldBooking.status !== "REPLACED_PENDING_CANCELLATION") {
  throw new Error("completed reschedule does not atomically install the new booking before compensating the old");
}

state = Machine.createInitial("staleCallback");
state = Machine.transition(state, {
  type: "RECEIPT_SUCCEEDED",
  kind: "meeting",
  appointmentRevision: 1,
  receiptId: "SYN-STALE-MTG-R1",
});
if (state.receipts.meeting || state.booking.status !== "NONE" || state.attempts.at(-1)?.result !== "STALE_RECEIPT") {
  throw new Error("late old-revision callback can write the current appointment");
}

state = chooseAndSubmit("calendarRevoked");
if (state.schedulingState !== "BLOCKED" || state.booking.status !== "NONE" ||
    state.exception?.kind !== "CALENDAR_PERMISSION_REVOKED") {
  throw new Error("revoked calendar permission does not stop booking and open one human issue");
}

state = Machine.createInitial("noCommonSlot");
state = Machine.transition(state, { type: "REQUEST_HELP" });
if (!state.helpRequested || state.booking.status !== "NONE" || state.exception?.kind !== "NO_COMMON_SLOT") {
  throw new Error("no-common-slot help route creates a booking or loses the exception");
}

state = Machine.createInitial("invalidLink");
state = Machine.transition(state, { type: "SELECT_SLOT", slotId: "slot-1" });
state = Machine.transition(state, { type: "SUBMIT_SLOT" });
if (state.booking.status !== "NONE" || state.selectionReceipt || state.attempts.at(-1)?.result !== "DENIED") {
  throw new Error("invalid coordination link can alter scheduling state");
}
demo.setState(state);
if (app.innerHTML.includes("林可欣") || app.innerHTML.includes("AI 产品经理") ||
    !app.innerHTML.includes("页面没有展示任何面试详情")) {
  throw new Error("invalid-link page leaks candidate or interview details");
}

state = Machine.createInitial("noticeNoChoice");
if (state.booking.status !== "BOOKED" || state.recording.noticeStatus !== "DELIVERED" ||
    state.recording.choice !== "NONE" || state.recording.gate !== "OFF") {
  throw new Error("notice-only fixture either loses the booking or infers recording consent");
}

state = Machine.createInitial("lateParticipant");
if (state.booking.status !== "BOOKED" || state.recording.gate !== "BLOCKED_LATE_PARTICIPANT") {
  throw new Error("late participant either cancels the interview or leaves capture available");
}
demo.setState(state);
if (!app.innerHTML.includes("参与人发生变化，录制保持关闭") || !app.innerHTML.includes("面试安排仍然有效")) {
  throw new Error("late-participant UI does not preserve the interview while blocking recording");
}

state = Machine.createInitial("normal");
state.candidate.role = '<img src=x onerror="globalThis.__xss=1">';
demo.setState(state);
if (app.innerHTML.includes('<img src=x onerror=') || !app.innerHTML.includes("&lt;img src=x onerror=")) {
  throw new Error("candidate-controlled content is not escaped before DOM rendering");
}

console.log("PASS | recruiting Agent candidate scheduling demo | 12 danger fixtures | escaped UI");
