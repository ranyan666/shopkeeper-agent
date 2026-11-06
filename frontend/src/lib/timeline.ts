/**
 * 执行流程耗时计算
 * 把按完成顺序记录的步骤时间戳转换成每个节点的耗时，用于流程图上展示
 */
import type { StepState } from "../types/agent";

export type StepTimeline = {
  /** 节点名 -> 耗时毫秒数 */
  durations: Record<string, number>;
  /** 从第一个节点完成到最后一个节点完成的整体耗时 */
  totalMs: number;
};

/**
 * 计算各节点耗时
 *
 * 步骤是按「完成」顺序追加到数组里的，所以相邻两个时间戳之差
 * 就是上一个节点从完成到下一个节点完成的间隔，用来近似单节点耗时。
 */
export function computeStepDurations(steps: StepState[] = []): StepTimeline {
  const durations: Record<string, number> = {};

  if (steps.length < 2) {
    return { durations, totalMs: 0 };
  }

  // 事件理论上已按时间递增，这里排序一次避免并行节点乱序导致出现负数耗时
  const ordered = [...steps].sort((a, b) => a.updatedAt - b.updatedAt);

  for (let index = 0; index < ordered.length - 1; index += 1) {
    const delta = ordered[index + 1].updatedAt - ordered[index].updatedAt;
    durations[ordered[index].step] = Math.max(0, delta);
  }

  return {
    durations,
    totalMs: Math.max(0, ordered[ordered.length - 1].updatedAt - ordered[0].updatedAt),
  };
}

/** 把毫秒数格式化成 120ms / 1.2s / 1m3s */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms <= 0) {
    return "0ms";
  }

  const rounded = Math.round(ms);
  if (rounded < 1000) {
    return `${rounded}ms`;
  }

  if (rounded < 60000) {
    return `${(rounded / 1000).toFixed(1)}s`;
  }

  const minutes = Math.floor(rounded / 60000);
  const seconds = Math.round((rounded % 60000) / 1000);
  return seconds > 0 ? `${minutes}m${seconds}s` : `${minutes}m`;
}
