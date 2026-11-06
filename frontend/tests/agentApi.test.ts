import assert from "node:assert/strict";
import test from "node:test";

import { parseSseChunk } from "../src/lib/agentApi.ts";

test("解析 progress 事件", () => {
  const event = parseSseChunk('data: {"type":"progress","step":"生成SQL","status":"running"}');

  assert.deepEqual(event, { type: "progress", step: "生成SQL", status: "running" });
});

test("解析 meta 事件并保留中文", () => {
  const payload = {
    type: "meta",
    sql: "SELECT SUM(amount) FROM dw.dwd_order",
    keywords: ["华北", "销售额"],
    metrics: [{ name: "GMV", description: "成交总额", alias: ["成交额"] }],
  };

  const event = parseSseChunk(`data: ${JSON.stringify(payload)}`);

  assert.deepEqual(event, payload);
});

test("解析 result 事件", () => {
  const event = parseSseChunk('data: {"type":"result","data":[{"销售总额":41099.5}]}');

  assert.equal(event?.type, "result");
  assert.deepEqual((event as { data: unknown }).data, [{ 销售总额: 41099.5 }]);
});

test("多行 data 会被拼接后解析", () => {
  const event = parseSseChunk('data: {"type":"progress",\ndata: "step":"校验SQL",\ndata: "status":"success"}');

  assert.equal(event?.type, "progress");
  assert.equal((event as { step: string }).step, "校验SQL");
});

test("没有 data 行时返回 null", () => {
  assert.equal(parseSseChunk(""), null);
  assert.equal(parseSseChunk(": keep-alive"), null);
});

test("JSON 非法时转成 error 事件而不是抛异常", () => {
  const event = parseSseChunk("data: {not-json}");

  assert.equal(event?.type, "error");
  assert.match((event as { message: string }).message, /无法解析后端事件/);
});
