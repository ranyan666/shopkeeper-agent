/**
 * 智能体类型定义
 * 定义问数智能体前端使用的 SSE 事件、流程步骤和聊天消息类型
 */
export type ProgressStatus = "running" | "success" | "error";

export type ProgressEvent = {
  type: "progress";
  step: string;
  status: ProgressStatus;
};

/** 本次查询用到的指标口径 */
export type MetricInfo = {
  name: string;
  description: string;
  alias: string[];
};

/** 查询依据：生成的 SQL、召回关键词和指标口径 */
export type MetaInfo = {
  sql: string;
  keywords: string[];
  metrics: MetricInfo[];
};

export type MetaEvent = MetaInfo & {
  type: "meta";
};

export type ResultEvent = {
  type: "result";
  data: unknown;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type AgentEvent = ProgressEvent | MetaEvent | ResultEvent | ErrorEvent;

export type StepState = {
  step: string;
  status: ProgressStatus;
  updatedAt: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error";
  steps?: StepState[];
  meta?: MetaInfo;
  result?: unknown;
  error?: string;
};
