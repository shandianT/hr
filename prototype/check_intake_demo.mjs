import fs from "node:fs";

const prototypePath = new URL("招聘Agent_核心功能1_简历收件Demo.html", import.meta.url);
const source = fs.readFileSync(prototypePath, "utf8");
const scriptMatch = source.match(/<script>([\s\S]*)<\/script>/);

if (!scriptMatch) throw new Error("intake demo script is missing");
new Function(scriptMatch[1]);

for (const requiredToken of [
  "一份附件，先证明来源、文件、身份和申请范围",
  "演示输入，不是 HR 的日常触发",
  "接收与安全",
  "解析与证据",
  "去重与身份",
  "岗位与批次",
  "自动开案",
  "重复来源，不重复建案",
  "检测到材料内的操作指令",
  "同一联系方式对应两个身份候选",
  "岗位或招聘批次不唯一",
  "工具调用 0",
  "提交你的判断",
  "INTAKE/COMMIT/1",
  "function renderIntake()",
  "function submitHumanDecision()",
  "data-action=\"auto-run\"",
  "全部为合成数据",
]) {
  if (!source.includes(requiredToken)) {
    throw new Error(`intake demo token is missing: ${requiredToken}`);
  }
}

const app = { innerHTML: "" };
const toast = {
  textContent: "",
  classList: { add() {}, remove() {} },
  _t: null,
};
globalThis.location = { href: "http://localhost/intake" };
globalThis.history = { replaceState() {} };
globalThis.addEventListener = () => {};
globalThis.document = {
  getElementById(id) { return id === "app" ? app : toast; },
  querySelectorAll() { return []; },
  querySelector() { return null; },
};
new Function(scriptMatch[1])();
const demo = globalThis.__intakeDemoTest;
if (!demo) throw new Error("intake demo behavior hook is missing");

Object.assign(demo.state, { scenario: "injection", selection: "", decisionReceipt: null, decisionHistory: [] });
if (demo.personData().name !== "王浩" || demo.routeData().req !== "REQ-GPM-1182") {
  throw new Error("prompt-injection fixture is cross-wired to another candidate");
}
if (!demo.commitView().includes("王浩") || !demo.commitView().includes("AP-24107")) {
  throw new Error("prompt-injection fixture does not keep its own case data");
}

Object.assign(demo.state, {
  scenario: "identity",
  selection: "candidate-new",
  decisionReceipt: { actor: "周岩 / Hiring Owner", selection: "candidate-new", reason: "test" },
  decisionHistory: [],
});
if (demo.personData().id !== "P-NEW-24122" || !demo.commitView().includes("P-NEW-24122")) {
  throw new Error("human identity choice does not control the committed identity");
}

Object.assign(demo.state, {
  scenario: "routing",
  selection: "route-growth",
  decisionReceipt: { actor: "周岩 / Hiring Owner", selection: "route-growth", reason: "test" },
  decisionHistory: [],
});
if (demo.routeData().req !== "REQ-GPM-1182" || !demo.commitView().includes("REQ-GPM-1182")) {
  throw new Error("human routing choice does not control the committed route");
}

Object.assign(demo.state, {
  scenario: "duplicate", step: 2, view: 2, started: true, resolved: false,
  committed: false, selection: "", decisionReceipt: null, needsInfo: false,
});
if (!demo.isComplete() || demo.gateClass(2) !== "done") {
  throw new Error("duplicate arrival is not projected as a safe completed state");
}
demo.renderIntake();
if (!app.innerHTML.includes("等待对象：无") || !app.innerHTML.includes("查看原案件或结束本次重复投递处理")) {
  throw new Error("duplicate completion still claims to wait for a human");
}

Object.assign(demo.state, { scenario: "injection", evidenceOpen: true, evidenceField: 0 });
if (!demo.evidenceDrawer().includes("<h2 style=\"margin:6px 0\">姓名</h2>") || !demo.evidenceDrawer().includes("“王浩”")) {
  throw new Error("field evidence drawer is not bound to the selected field");
}

Object.assign(demo.state, {
  scenario: "routing", step: 3, started: true, resolved: false, needsInfo: true,
  decisionReceipt: {
    kind: "ROUTING_INFO_REQUEST", actor: "林敏 / 招聘运营（路由复核）",
    selection: "route-more", reason: "需要候选人确认岗位",
    checkpoint: "INTAKE/ROUTING/WAIT-1", revisionLabel: "Routing Review Revision 2",
  },
  decisionHistory: [],
});
if (!demo.routingView().includes("INTAKE/ROUTING/WAIT-1")) {
  throw new Error("request-more-information branch has no durable checkpoint");
}

Object.assign(demo.state, {
  scenario: "duplicate", step: 2, view: 2, started: true, resolved: false,
  committed: false, needsInfo: false, decisionReceipt: null, decisionHistory: [],
});
if (demo.completionToastMessage() !== "重复来源已附加，没有创建第二案件") {
  throw new Error("duplicate completion toast still claims a safety stop");
}

for (const fixture of [
  { scenario: "normal", work: ["7 年", "2019.07—至今，累计 7 年"], specialty: ["3 年", "2023.07—至今，连续 3 年"] },
  { scenario: "duplicate", work: ["7 年", "2019.07—至今，累计 7 年"], specialty: ["3 年", "2023.07—至今，连续 3 年"] },
  { scenario: "injection", work: ["6 年", "2020.07—至今，累计 6 年"], specialty: ["4 年", "2022.07—至今，连续 4 年"] },
  { scenario: "identity", work: ["5 年", "2021.07—至今，累计 5 年"], specialty: ["3 年", "2023.07—至今，连续 3 年"] },
  { scenario: "routing", work: ["8 年", "2018.07—至今，累计 8 年"], specialty: ["5 年", "2021.07—至今，连续 5 年"] },
]) {
  Object.assign(demo.state, {
    scenario: fixture.scenario, selection: "", resolved: false,
    evidenceOpen: true, evidenceField: 2, decisionReceipt: null, decisionHistory: [],
  });
  const workEvidence = demo.evidenceDrawer();
  if (!workEvidence.includes(fixture.work[0]) || !workEvidence.includes(fixture.work[1])) {
    throw new Error(`${fixture.scenario} work-years evidence does not support its value`);
  }
  demo.state.evidenceField = 3;
  const specialtyEvidence = demo.evidenceDrawer();
  if (!specialtyEvidence.includes(fixture.specialty[0]) || !specialtyEvidence.includes(fixture.specialty[1])) {
    throw new Error(`${fixture.scenario} specialty-years evidence does not support its value`);
  }
}

const expectedIdentityReceipt = {
  kind: "IDENTITY_RESOLUTION",
  actor: "林敏 / 招聘运营（身份复核）",
  selection: "candidate-new",
  reason: "两个历史身份均不匹配",
  checkpoint: "INTAKE/IDENTITY/REV-2",
  revisionLabel: "Identity Resolution Revision 2",
};
Object.assign(demo.state, {
  scenario: "identity", step: 2, view: 2, started: true, committed: false,
  selection: "candidate-new", reason: expectedIdentityReceipt.reason, resolved: false,
  decisionReceipt: null, decisionHistory: [], needsInfo: false,
});
demo.submitHumanDecision();
const identityReceipt = demo.state.decisionReceipt;
for (const [field, expected] of Object.entries(expectedIdentityReceipt)) {
  if (identityReceipt?.[field] !== expected) {
    throw new Error(`identity decision receipt has wrong ${field}: ${identityReceipt?.[field]}`);
  }
}
const identityCommit = demo.commitView();
for (const expected of [
  identityReceipt.actor,
  identityReceipt.revisionLabel,
  identityReceipt.checkpoint,
  "<span>Routing</span><b>Revision 1</b>",
]) {
  if (!identityCommit.includes(expected)) {
    throw new Error(`identity decision receipt is missing: ${expected}`);
  }
}

const expectedMoreInfoReceipt = {
  kind: "ROUTING_INFO_REQUEST",
  actor: "林敏 / 招聘运营（路由复核）",
  selection: "route-more",
  reason: "需要候选人确认岗位",
  checkpoint: "INTAKE/ROUTING/WAIT-1",
  revisionLabel: "Routing Review Revision 2",
};
Object.assign(demo.state, {
  scenario: "routing", step: 3, view: 3, started: true, resolved: false,
  committed: false, needsInfo: false, selection: "route-more", reason: expectedMoreInfoReceipt.reason,
  decisionReceipt: null, decisionHistory: [],
});
demo.submitHumanDecision();
const moreInfoReceipt = demo.state.decisionReceipt;
for (const [field, expected] of Object.entries(expectedMoreInfoReceipt)) {
  if (moreInfoReceipt?.[field] !== expected) {
    throw new Error(`routing information receipt has wrong ${field}: ${moreInfoReceipt?.[field]}`);
  }
}
demo.resumeDecision();
if (demo.state.decisionHistory.length !== 1 || demo.state.decisionHistory[0].reason !== moreInfoReceipt.reason) {
  throw new Error("resuming a routing decision erased the prior receipt");
}
if (!demo.routingView().includes(moreInfoReceipt.reason) || !demo.routingView().includes(moreInfoReceipt.checkpoint)) {
  throw new Error("resumed routing task no longer shows its prior recovery receipt");
}
if (!demo.activityItems().some((item) => item.text.includes("补充信息任务已记录"))) {
  throw new Error("resumed routing task lost its prior activity record");
}

Object.assign(demo.state, { selection: "route-growth", reason: "岗位编号与当前开放批次一致" });
demo.submitHumanDecision();
if (demo.state.decisionHistory.length !== 2 || !demo.state.decisionHistory.some((receipt) => receipt.kind === "ROUTING_INFO_REQUEST")) {
  throw new Error("final routing decision overwrote the earlier information-request receipt");
}
const routedCommit = demo.commitView();
for (const expected of [moreInfoReceipt.reason, moreInfoReceipt.checkpoint, "岗位编号与当前开放批次一致", "Routing Revision 2"]) {
  if (!routedCommit.includes(expected)) {
    throw new Error(`committed routing history is missing: ${expected}`);
  }
}
if (!demo.activityItems().some((item) => item.text.includes("补充信息任务已记录"))) {
  throw new Error("committed routing activity lost the earlier information-request event");
}

console.log("PASS | recruiting Agent intake product demo");
