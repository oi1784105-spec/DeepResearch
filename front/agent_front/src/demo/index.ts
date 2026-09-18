// 演示模式的网络层。
//
// 前端与网络交互只有 4 个点：一个 request() 辅助函数（内部调用 fetch）
// 加上附件上传、TTS 合成、研究流式接口三处直接 fetch。
// 因此只要替换 window.fetch 就能整体接管，视图代码一行都不用改。
//
// 必须严格遵守的约定（否则前端会静默失效）：
// 1. 路径全部是站点根绝对路径 /api/v1/...；
// 2. 出错时返回 { detail: string } —— 前端错误提示只读 detail；
// 3. 数组类接口必须返回数组：/providers、/research/conversations、
//    /research/history、POST /attachments；
// 4. SSE 帧必须是 LF 换行、以 "data: " 开头（含空格）、以空行分隔，
//    每个分帧里只能有一个 JSON 对象；
// 5. 只有 { type: "final", final: "..." } 会生成助手气泡。

import * as db from "./store";
import { DemoError, type PreparedResearch } from "./store";
import type { StreamEvent } from "./types";

/**
 * 是否为演示构建。
 * 用可选链读取 import.meta.env：该字段只由 Vite 注入，
 * 在纯 Node 环境下导入本模块（例如跑演示层自测）时不会抛错。
 */
export const DEMO_MODE = import.meta.env?.VITE_DEMO_MODE === "true";

/** 演示账号，登录页用它做预填。 */
export const DEMO_CREDENTIALS = db.DEMO_ACCOUNT;

const API_PREFIX = "/api/v1";

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

// ---------------------------------------------------------------------------
// 响应构造
// ---------------------------------------------------------------------------

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function noContent(): Response {
  return new Response(null, { status: 204 });
}

function toErrorResponse(error: unknown): Response {
  if (error instanceof DemoError) return json({ detail: error.message }, error.status);
  const message = error instanceof Error ? error.message : "演示模式无法处理该请求";
  return json({ detail: message }, 500);
}

// ---------------------------------------------------------------------------
// 请求体解析
// ---------------------------------------------------------------------------

function readJson<T extends object>(init: RequestInit | undefined): T {
  const body = init?.body;
  if (typeof body !== "string" || !body) return {} as T;
  try {
    return JSON.parse(body) as T;
  } catch {
    return {} as T;
  }
}

function readFiles(init: RequestInit | undefined): File[] {
  const body = init?.body;
  if (typeof FormData !== "undefined" && body instanceof FormData) {
    return body.getAll("files").filter((item): item is File => item instanceof File);
  }
  return [];
}

// ---------------------------------------------------------------------------
// 研究流式响应
// ---------------------------------------------------------------------------

const PHASE_DELAY = 420;

function encodeEvent(event: StreamEvent): Uint8Array {
  // 必须是 "data: "（带空格）+ JSON + 空行，且只能使用 LF。
  return new TextEncoder().encode(`data: ${JSON.stringify(event)}\n\n`);
}

function streamResearch(prepared: PreparedResearch): Response {
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      try {
        controller.enqueue(encodeEvent({ type: "status", message: "正在初始化研究链路…" }));
        await sleep(300);

        for (const message of prepared.trace) {
          // 与真实后端一致：路由决策用 route 事件，其余阶段用 phase 事件。
          const isRoute = message.startsWith("已走");
          controller.enqueue(
            encodeEvent(
              isRoute
                ? { type: "route", message }
                : { type: "phase", node: "demo", message },
            ),
          );
          await sleep(PHASE_DELAY);
        }

        // 与真实链路一致：内容生成完成后才写入历史，
        // 这样前端在 final 之后刷新对话列表就能看到这条新对话。
        db.commitResearch(prepared);
        controller.enqueue(encodeEvent({ type: "final", final: prepared.report }));
      } catch (error) {
        const message = error instanceof Error ? error.message : "演示模式处理失败";
        controller.enqueue(encodeEvent({ type: "error", message }));
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream; charset=utf-8" },
  });
}

// ---------------------------------------------------------------------------
// 路由
// ---------------------------------------------------------------------------

type RouteHandler = (context: {
  match: RegExpExecArray;
  url: URL;
  init: RequestInit | undefined;
}) => Response;

/** 顺序重要：静态路径必须排在带参数的路径之前。 */
const ROUTES: Array<[string, RegExp, RouteHandler]> = [
  // 账号
  ["POST", /^\/auth\/login$/, ({ init }) => {
    const body = readJson<{ email?: string; password?: string }>(init);
    return json(db.login(body.email ?? "", body.password ?? ""));
  }],
  ["POST", /^\/auth\/register$/, ({ init }) => {
    const body = readJson<{ email?: string; password?: string; display_name?: string }>(init);
    return json(db.register(body.email ?? "", body.password ?? "", body.display_name ?? ""));
  }],
  ["GET", /^\/auth\/me$/, () => json(db.getMe())],
  ["PATCH", /^\/auth\/me$/, ({ init }) => {
    const body = readJson<{ display_name?: string; avatar_data?: string }>(init);
    return json(db.updateProfile(body));
  }],
  ["POST", /^\/auth\/change-password$/, () => {
    db.changePassword();
    return noContent();
  }],

  // Provider
  ["GET", /^\/providers$/, () => json(db.listProviders())],
  ["POST", /^\/providers$/, ({ init }) => json(db.createProvider(readJson(init)))],
  ["POST", /^\/providers\/test$/, ({ init }) => json(db.testProvider(readJson(init)))],
  ["POST", /^\/providers\/models$/, ({ init }) => json(db.discoverModels(readJson(init)))],
  ["GET", /^\/providers\/([^/]+)\/models$/, ({ match }) => json(db.modelsOfProvider(decodeURIComponent(match[1] ?? "")))],
  ["PUT", /^\/providers\/([^/]+)\/activate$/, ({ match }) => json(db.activateProvider(decodeURIComponent(match[1] ?? "")))],
  ["PUT", /^\/providers\/([^/]+)$/, ({ match, init }) =>
    json(db.updateProvider(decodeURIComponent(match[1] ?? ""), readJson(init)))],
  ["DELETE", /^\/providers\/([^/]+)$/, ({ match }) => {
    db.deleteProvider(decodeURIComponent(match[1] ?? ""));
    return noContent();
  }],

  // 研究：对话列表必须在 /research/stream 之前不会有冲突，但顺序保持一致更易读
  ["GET", /^\/research\/conversations$/, () => json(db.listConversations())],
  ["GET", /^\/research\/history$/, ({ url }) =>
    json(db.getHistory(url.searchParams.get("thread_id") ?? ""))],
  ["DELETE", /^\/research\/conversations\/([^/]+)$/, ({ match }) => {
    db.deleteConversation(decodeURIComponent(match[1] ?? ""));
    return noContent();
  }],
  ["POST", /^\/research\/stream$/, ({ init }) =>
    streamResearch(db.prepareResearch(readJson(init)))],

  // 附件
  ["POST", /^\/attachments$/, ({ init }) => json(db.uploadAttachments(readFiles(init)), 201)],
  ["DELETE", /^\/attachments\/([^/]+)$/, ({ match }) => {
    db.deleteAttachment(decodeURIComponent(match[1] ?? ""));
    return noContent();
  }],

  // 语音：演示模式不提供云端合成，前端会退回浏览器语音。
  ["GET", /^\/tts\/config$/, () => json({ enabled: false, provider: "browser", voice: "" })],
];

function resolveRoute(method: string, pathname: string): { handler: RouteHandler; match: RegExpExecArray } | null {
  const relative = pathname.startsWith(API_PREFIX) ? pathname.slice(API_PREFIX.length) : pathname;
  for (const [routeMethod, pattern, handler] of ROUTES) {
    if (routeMethod !== method) continue;
    const match = pattern.exec(relative);
    if (match) return { handler, match };
  }
  return null;
}

/**
 * 处理一个 /api/v1/ 请求，返回 Response。
 *
 * 注意：这里接收的是调用方原始的 RequestInit，而不是把它包成 Request。
 * 包成 Request 会让 init.body 从 FormData 变成 ReadableStream，
 * 附件上传就无法解析了。
 */
function handleApiRequest(method: string, url: URL, init: RequestInit | undefined): Response {
  const route = resolveRoute(method, url.pathname);
  if (!route) {
    return json({ detail: `演示模式未实现该接口：${method} ${url.pathname}` }, 404);
  }
  try {
    return route.handler({ match: route.match, url, init });
  } catch (error) {
    return toErrorResponse(error);
  }
}

/**
 * 处理一个演示接口请求。
 *
 * 不是 /api/v1/ 路径时返回 null，调用方应回退到真实 fetch。
 * 单独导出是为了让演示层可以在 Node 里被直接测试，
 * 而不必依赖浏览器与构建产物。
 */
export function handleDemoRequest(
  rawUrl: string,
  init?: RequestInit,
): Promise<Response> | null {
  let url: URL;
  try {
    const base = typeof window === "undefined" ? "http://localhost/" : window.location.href;
    url = new URL(rawUrl, base);
  } catch {
    return null;
  }
  if (!url.pathname.startsWith(`${API_PREFIX}/`)) return null;

  const method = (
    init?.method ?? "GET"
  ).toUpperCase();
  return Promise.resolve(handleApiRequest(method, url, init));
}

/**
 * 安装 fetch 垫片。
 * 只接管 /api/v1/ 下的请求，其余（静态资源等）原样放行。
 */
export function installDemoNetwork(): void {
  if (!DEMO_MODE) return;
  if (typeof window === "undefined") return;
  const target = window as Window & { __deepresearchDemoFetch?: boolean };
  if (target.__deepresearchDemoFetch) return;

  const originalFetch = window.fetch.bind(window);
  window.fetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const handled = handleDemoRequest(rawUrl, init);
    if (handled) return handled;
    return originalFetch(input, init);
  };
  target.__deepresearchDemoFetch = true;
}

/** 清空演示数据并刷新页面。 */
export function resetDemo(): void {
  db.resetDemoState();
  window.location.reload();
}
