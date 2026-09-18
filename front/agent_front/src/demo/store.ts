// 演示模式的内存数据库。
//
// 设计要点与真实后端保持一致的行为特征：
// 1. GET /providers、/research/conversations、/research/history、POST /attachments
//    必须返回「数组」——前端直接对返回值做 .map/.length/展开，返回对象会直接报错。
// 2. POST /providers 与 PUT /providers/{id} 必须原样回显 id，
//    前端用 id 做匹配；id 不一致会导致「看起来保存了但列表没变」。
// 3. PUT /providers/{id}/activate 只读响应里的 id，回错 id 会让应用卡在配置页。
// 4. 错误统一用 { detail: string }，因为前端的错误提示只读 detail。
// 5. 数据写入 localStorage，刷新后仍在，访客体验连续。

import {
  DEMO_ACCOUNT,
  MODEL_CATALOG,
  SEED_PROVIDER,
  SEED_USER,
  buildReport,
  buildTrace,
  seedConversations,
} from "./content";
import type {
  Attachment,
  Conversation,
  ConversationRecord,
  Provider,
  ReasoningEffort,
  ResearchRequest,
  User,
} from "./types";

const STORAGE_KEY = "deepresearch_demo_db_v1";
const DB_VERSION = 1;

type DemoState = {
  version: number;
  sequence: number;
  user: User;
  providers: Provider[];
  conversations: Conversation[];
  histories: Record<string, ConversationRecord[]>;
  attachments: Attachment[];
};

/** 业务错误：会被转换成 HTTP 状态码与 { detail } 错误体。 */
export class DemoError extends Error {
  status: number;

  constructor(message: string, status = 400) {
    super(message);
    this.name = "DemoError";
    this.status = status;
  }
}

let state: DemoState | null = null;

function freshState(): DemoState {
  const { conversations, histories } = seedConversations();
  return {
    version: DB_VERSION,
    sequence: 5000,
    user: { ...SEED_USER },
    providers: [{ ...SEED_PROVIDER, available_models: [...SEED_PROVIDER.available_models] }],
    conversations,
    histories,
    attachments: [],
  };
}

function persist(): void {
  if (!state) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // 隐私模式下 localStorage 可能不可写，此时退化成纯内存演示。
  }
}

function load(): DemoState {
  if (state) return state;
  let restored: DemoState | null = null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as DemoState;
      if (parsed && parsed.version === DB_VERSION) restored = parsed;
    }
  } catch {
    restored = null;
  }
  state = restored ?? freshState();
  persist();
  return state;
}

function nextId(): number {
  const db = load();
  db.sequence += 1;
  return db.sequence;
}

/** 重置演示数据，回到初始的预置状态。 */
export function resetDemoState(): void {
  state = freshState();
  persist();
}

export { DEMO_ACCOUNT };

// ---------------------------------------------------------------------------
// 账号
// ---------------------------------------------------------------------------

export function login(email: string, password: string): { access_token: string; user: User } {
  const db = load();
  if (!email.trim() || !password.trim()) {
    throw new DemoError("请输入邮箱与密码", 422);
  }
  db.user = { ...db.user, email: email.trim() };
  persist();
  return { access_token: "demo-access-token", user: { ...db.user } };
}

export function register(
  email: string,
  password: string,
  displayName: string,
): { access_token: string; user: User } {
  const db = load();
  if (!email.trim() || !password.trim()) {
    throw new DemoError("请输入邮箱与密码", 422);
  }
  db.user = {
    ...db.user,
    email: email.trim(),
    display_name: displayName.trim() || DEMO_ACCOUNT.display_name,
  };
  persist();
  return { access_token: "demo-access-token", user: { ...db.user } };
}

export function getMe(): User {
  return { ...load().user };
}

export function updateProfile(patch: { display_name?: string; avatar_data?: string }): User {
  const db = load();
  db.user = {
    ...db.user,
    ...(typeof patch.display_name === "string" && patch.display_name.trim()
      ? { display_name: patch.display_name.trim() }
      : {}),
    ...(typeof patch.avatar_data === "string" ? { avatar_data: patch.avatar_data } : {}),
  };
  persist();
  return { ...db.user };
}

export function changePassword(): void {
  // 演示模式不校验旧密码，仅返回成功（真实后端返回 204 空响应）。
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function listProviders(): Provider[] {
  return load().providers.map((item) => ({
    ...item,
    available_models: [...item.available_models],
  }));
}

export function providerModels(providerType: string): string[] {
  return [...(MODEL_CATALOG[providerType] ?? MODEL_CATALOG.custom ?? [])];
}

type ProviderTestForm = {
  provider_type?: string;
  endpoint?: string;
  model?: string;
  api_key?: string;
};

/** 演示模式的「连接测试」不发起真实请求，直接返回成功与可选模型。 */
export function testProvider(form: ProviderTestForm): {
  ok: boolean;
  message: string;
  models: string[];
} {
  if (!form.endpoint?.trim()) {
    throw new DemoError("请先填写 Endpoint", 422);
  }
  if (!form.api_key?.trim()) {
    throw new DemoError("请先填写 API Key", 422);
  }
  const models = form.model?.trim()
    ? [form.model.trim(), ...providerModels(form.provider_type ?? "custom").filter((m) => m !== form.model)]
    : providerModels(form.provider_type ?? "custom");
  return {
    ok: true,
    message: "连接成功（演示模式，未发起真实请求）",
    models,
  };
}

export function discoverModels(form: ProviderTestForm): {
  ok: boolean;
  message: string;
  models: string[];
} {
  const models = providerModels(form.provider_type ?? "custom");
  return {
    ok: true,
    message: `已获取 ${models.length} 个模型（演示模式）`,
    models,
  };
}

export function modelsOfProvider(id: string | number): {
  ok: boolean;
  message: string;
  models: string[];
} {
  const provider = load().providers.find((item) => String(item.id) === String(id));
  if (!provider) throw new DemoError("Provider 不存在", 404);
  return {
    ok: true,
    message: "已获取模型列表",
    models: [...provider.available_models],
  };
}

type ProviderPayload = {
  name?: string;
  provider_type?: string;
  protocol?: string;
  endpoint?: string;
  model?: string;
  api_version?: string | null;
  reasoning_effort?: ReasoningEffort;
  available_models?: string[];
  api_key?: string | null;
  active?: boolean;
};

function normalizeProvider(payload: ProviderPayload, existing: Provider | null): Provider {
  const models = Array.isArray(payload.available_models)
    ? payload.available_models.filter((item): item is string => typeof item === "string" && Boolean(item))
    : (existing?.available_models ?? []);
  const model = payload.model?.trim() || models[0] || existing?.model || "";

  return {
    id: existing?.id ?? 0,
    name: payload.name?.trim() || existing?.name || "未命名 Provider",
    provider_type: payload.provider_type || existing?.provider_type || "custom",
    protocol: payload.protocol || existing?.protocol || "openai_chat",
    endpoint: payload.endpoint?.trim() || existing?.endpoint || "",
    model,
    api_version: payload.api_version ?? existing?.api_version ?? null,
    reasoning_effort: payload.reasoning_effort || existing?.reasoning_effort || "auto",
    available_models: models.length ? models : model ? [model] : [],
    active: payload.active ?? existing?.active ?? false,
  };
}

export function createProvider(payload: ProviderPayload): Provider {
  const db = load();
  const provider = normalizeProvider(payload, null);
  provider.id = nextId();
  // 与真实后端一致：新建并启用时，其余 Provider 取消启用。
  if (provider.active) {
    db.providers = db.providers.map((item) => ({ ...item, active: false }));
  }
  db.providers = [...db.providers, provider];
  persist();
  return { ...provider, available_models: [...provider.available_models] };
}

export function updateProvider(id: string | number, payload: ProviderPayload): Provider {
  const db = load();
  const index = db.providers.findIndex((item) => String(item.id) === String(id));
  const existing = index >= 0 ? db.providers[index] : undefined;
  if (!existing) throw new DemoError("Provider 不存在", 404);

  const updated = normalizeProvider(payload, existing);
  // 必须回显原 id：前端用 item.id === data.id 匹配更新后的记录。
  updated.id = existing.id;
  db.providers = db.providers.map((item, i) => (i === index ? updated : item));
  persist();
  return { ...updated, available_models: [...updated.available_models] };
}

export function activateProvider(id: string | number): Provider {
  const db = load();
  const target = db.providers.find((item) => String(item.id) === String(id));
  if (!target) throw new DemoError("Provider 不存在", 404);
  db.providers = db.providers.map((item) => ({
    ...item,
    active: String(item.id) === String(id),
  }));
  persist();
  const active = db.providers.find((item) => item.active) ?? target;
  return { ...active, available_models: [...active.available_models] };
}

export function deleteProvider(id: string | number): void {
  const db = load();
  db.providers = db.providers.filter((item) => String(item.id) !== String(id));
  persist();
}

// ---------------------------------------------------------------------------
// 对话
// ---------------------------------------------------------------------------

export function listConversations(): Conversation[] {
  return load()
    .conversations.slice()
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .map((item) => ({ ...item }));
}

export function getHistory(threadId: string): ConversationRecord[] {
  const db = load();
  return (db.histories[threadId] ?? []).map((item) => ({ ...item }));
}

export function deleteConversation(threadId: string): void {
  const db = load();
  db.conversations = db.conversations.filter((item) => item.thread_id !== threadId);
  delete db.histories[threadId];
  persist();
}

// ---------------------------------------------------------------------------
// 附件
// ---------------------------------------------------------------------------

function kindOf(filename: string, contentType: string): string {
  const ext = filename.includes(".") ? filename.split(".").pop()?.toLowerCase() ?? "" : "";
  if (contentType.startsWith("image/")) return "image";
  if (ext === "pdf") return "pdf";
  if (["docx", "doc"].includes(ext)) return "document";
  if (["xlsx", "xls", "csv", "tsv"].includes(ext)) return "spreadsheet";
  if (["py", "js", "ts", "vue", "java", "go", "c", "cpp", "h", "sql", "json", "yaml", "yml", "xml", "html"].includes(ext)) return "code";
  return "text";
}

export function uploadAttachments(files: File[]): Attachment[] {
  const db = load();
  const created = files.map((file) => {
    const contentType = file.type || "text/plain";
    return {
      id: `demo-${nextId()}`,
      filename: file.name,
      content_type: contentType,
      size_bytes: file.size,
      kind: kindOf(file.name, contentType),
      is_image: contentType.startsWith("image/"),
    };
  });
  db.attachments = [...db.attachments, ...created];
  persist();
  return created;
}

export function deleteAttachment(id: string): void {
  const db = load();
  db.attachments = db.attachments.filter((item) => item.id !== id);
  persist();
}

// ---------------------------------------------------------------------------
// 研究（流式）
// ---------------------------------------------------------------------------

export type PreparedResearch = {
  threadId: string;
  query: string;
  attachmentCount: number;
  trace: string[];
  report: string;
};

/** 准备一次研究：生成链路轨迹与报告，此时还没有写入历史。 */
export function prepareResearch(payload: ResearchRequest): PreparedResearch {
  const db = load();
  const query = (payload.query ?? "").trim();
  const attachmentIds = Array.isArray(payload.attachment_ids) ? payload.attachment_ids : [];
  const available = db.attachments.filter((item) => attachmentIds.includes(item.id)).length;
  const threadId = payload.thread_id?.trim() || `thread-${db.user.id}-${Date.now()}`;

  if (!query && available === 0) {
    throw new DemoError("请输入问题或添加附件", 422);
  }
  if (!db.providers.some((item) => item.active)) {
    throw new DemoError("请先配置并启用一个 AI Provider", 409);
  }

  return {
    threadId,
    query: query || "（仅附件）",
    attachmentCount: available,
    trace: buildTrace(query || "附件内容", available),
    report: buildReport(query || "附件内容", available),
  };
}

/** 流式输出结束后写入历史与对话列表。 */
export function commitResearch(prepared: PreparedResearch): void {
  const db = load();
  const now = new Date().toISOString();
  const records = db.histories[prepared.threadId] ?? [];

  records.push({
    id: nextId(),
    role: "user",
    content: prepared.query,
    created_at: now,
  });
  records.push({
    id: nextId(),
    role: "assistant",
    content: prepared.report,
    created_at: now,
  });
  db.histories[prepared.threadId] = records;

  const title = prepared.query.length > 24 ? `${prepared.query.slice(0, 24)}…` : prepared.query;
  const existing = db.conversations.find((item) => item.thread_id === prepared.threadId);
  if (existing) {
    existing.title = title;
    existing.updated_at = now;
  } else {
    db.conversations = [
      ...db.conversations,
      { thread_id: prepared.threadId, title, updated_at: now },
    ];
  }
  persist();
}
