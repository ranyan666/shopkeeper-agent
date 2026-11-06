import assert from "node:assert/strict";
import test from "node:test";

import { computeStepDurations, formatDuration } from "../src/lib/timeline.ts";
import type { ProgressStatus } from "../src/types/agent.ts";

function step(name: string, updatedAt: number, status: ProgressStatus = "success") {
  return { step: name, status, updatedAt };
}

test("少于两个步骤时不产生耗时", () => {
  assert.deepEqual(computeStepDurations([]), { durations: {}, totalMs: 0 });
  assert.deepEqual(computeStepDurations([step("执行SQL", 1000)]), {
    durations: {},
    totalMs: 0,
  });
});

test("相邻步骤的时间差记为上一个节点的耗时", () => {
  const timeline = computeStepDurations([
    step("抽取关键词", 1000),
    step("召回字段信息", 1120),
    step("生成SQL", 2120),
  ]);

  assert.deepEqual(timeline.durations, { 抽取关键词: 120, 召回字段信息: 1000 });
  assert.equal(timeline.totalMs, 1120);
});

test("最后一个节点没有后继，因此没有耗时", () => {
  const timeline = computeStepDurations([
    step("生成SQL", 1000),
    step("执行SQL", 1200),
  ]);

  assert.equal(timeline.durations["执行SQL"], undefined);
  assert.equal(timeline.durations["生成SQL"], 200);
});

test("输入乱序时按时间戳重新排序，不会算出负耗时", () => {
  const timeline = computeStepDurations([
    step("生成SQL", 3000),
    step("抽取关键词", 1000),
    step("召回字段信息", 2000),
  ]);

  assert.deepEqual(timeline.durations, { 抽取关键词: 1000, 召回字段信息: 1000 });
  assert.equal(timeline.totalMs, 2000);
});

test("并行节点同一时刻完成时耗时为 0 而不是负数", () => {
  const timeline = computeStepDurations([
    step("召回字段信息", 1500),
    step("召回指标信息", 1500),
    step("合并召回信息", 1700),
  ]);

  assert.equal(timeline.durations["合并召回信息"], undefined);
  assert.equal(timeline.totalMs, 200);
  assert.ok(Object.values(timeline.durations).every((value) => value >= 0));
});

test("formatDuration 在毫秒级展示整数毫秒", () => {
  assert.equal(formatDuration(0), "0ms");
  assert.equal(formatDuration(1), "1ms");
  assert.equal(formatDuration(999), "999ms");
});

test("formatDuration 在秒级保留一位小数", () => {
  assert.equal(formatDuration(1000), "1.0s");
  assert.equal(formatDuration(1234), "1.2s");
  assert.equal(formatDuration(59999), "60.0s");
});

test("formatDuration 在分钟级带上分钟", () => {
  assert.equal(formatDuration(60000), "1m");
  assert.equal(formatDuration(63000), "1m3s");
});

test("formatDuration 对非法输入兜底为 0ms", () => {
  assert.equal(formatDuration(-5), "0ms");
  assert.equal(formatDuration(Number.NaN), "0ms");
  assert.equal(formatDuration(Number.POSITIVE_INFINITY), "0ms");
});
