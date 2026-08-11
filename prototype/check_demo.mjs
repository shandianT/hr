import fs from "node:fs";

const prototypePath = new URL("招聘Agent_产品形态Demo_v1.html", import.meta.url);
const source = fs.readFileSync(prototypePath, "utf8");
const scriptMatch = source.match(/<script>([\s\S]*)<\/script>/);

if (!scriptMatch) throw new Error("prototype script is missing");
new Function(scriptMatch[1]);

for (const requiredToken of [
  "function renderA()",
  "function renderB()",
  "function renderC()",
  "必要人工决策点",
  "录制同意缺失",
  "日历时段冲突",
  "部门反馈超时",
  "受控事实回流画像治理",
  "全部为合成数据",
  "function roundRibbon()",
  "多轮循环",
  "恢复记录 · APPLIED",
  "检查点 ${state.recovery.checkpoint}",
  "function packageModal()",
  "各轮结论与证据地图",
  "data-action=\"open-package\"",
  "state.variant=variants",
  "返回 Hiring Owner 决策",
  "FINAL ASSESSMENT PACKAGE / REV ${state.evaluationRevision}",
  "state.recovery.acknowledged=true",
]) {
  if (!source.includes(requiredToken)) {
    throw new Error(`prototype token is missing: ${requiredToken}`);
  }
}

console.log("PASS | recruiting Agent product-shape prototype");
