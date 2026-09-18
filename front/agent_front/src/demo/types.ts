// 演示模式使用的数据类型。
//
// 这些形状与 App.vue 顶部手写的类型保持一致，也与真实后端的响应字段一致：
// 演示层替代的是网络，不是数据结构，因此字段名必须逐一对齐。

export type ReasoningEffort = "auto" | "low" | "medium" | "high" | "xhigh";

export type User = {
  id: number;
  email: string;
  display_name: string;
  avatar_data?: string;
};

export type Provider = {
  id: number;
  name: string;
  provider_type: string;
  protocol: string;
  endpoint: string;
  model: string;
  api_version?: string | null;
  reasoning_effort: ReasoningEffort;
  available_models: string[];
  active: boolean;
};

export type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  kind: string;
  is_image: boolean;
};

export type Conversation = {
  thread_id: string;
  title: string;
  updated_at: string;
};

export type ConversationRecord = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

/** 一次研究请求的提交内容（对应 POST /api/v1/research/stream 的请求体）。 */
export type ResearchRequest = {
  query?: string;
  attachment_ids?: string[];
  thread_id?: string;
  model?: string;
  reasoning_effort?: ReasoningEffort;
};

/** 流式事件的负载，字段名与前端读取的完全一致。 */
export type StreamEvent =
  | { type: "status"; message: string }
  | { type: "route"; message: string }
  | { type: "phase"; node?: string; message: string }
  | { type: "final"; final: string }
  | { type: "error"; message: string };
