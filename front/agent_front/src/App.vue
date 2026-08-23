<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

type User = {
  id: number;
  email: string;
  display_name: string;
  avatar_data?: string;
};
type Provider = {
  id: number;
  name: string;
  provider_type: string;
  protocol: string;
  endpoint: string;
  model: string;
  api_version?: string | null;
  reasoning_effort: "auto" | "low" | "medium" | "high" | "xhigh";
  available_models: string[];
  active: boolean;
};
type ProviderForm = {
  name: string;
  provider_type: string;
  protocol: string;
  endpoint: string;
  api_key: string;
  model: string;
  api_version: string;
  reasoning_effort: "auto" | "low" | "medium" | "high" | "xhigh";
};
type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  kind: string;
  is_image: boolean;
};
type Message = {
  id: string;
  role: "user" | "assistant" | "status";
  content: string;
};
type ConversationRecord = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
type Conversation = {
  thread_id: string;
  title: string;
  updated_at: string;
};
type VoiceState = "idle" | "listening" | "thinking" | "speaking";
type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0?: { transcript: string };
};
type SpeechRecognitionEventLike = Event & {
  results: ArrayLike<SpeechRecognitionResultLike>;
  resultIndex?: number;
};
type SpeechRecognitionErrorEventLike = Event & {
  error?: string;
};
type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
};
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

const token = ref(localStorage.getItem("deepresearch_token") || "");
const user = ref<User | null>(null);
const providers = ref<Provider[]>([]);
const view = ref<"chat" | "settings" | "profile">("chat");
const authMode = ref<"login" | "register">("login");
const theme = ref<"light" | "dark">(
  (localStorage.getItem("deepresearch_theme") as "light" | "dark") || "dark",
);
const locale = ref<"zh" | "en">(
  (localStorage.getItem("deepresearch_locale") as "zh" | "en") || "zh",
);
const loading = ref(false);
const authLoading = ref(false);
const notice = ref("");
const errorMessage = ref("");
const authForm = ref({ email: "", password: "", display_name: "" });
const form = ref<ProviderForm>({
  name: "DeepSeek",
  provider_type: "deepseek",
  protocol: "openai_chat",
  endpoint: "https://api.deepseek.com/v1",
  api_key: "",
  model: "deepseek-chat",
  api_version: "",
  reasoning_effort: "auto",
});
const editingProviderId = ref<number | null>(null);
const testResult = ref<{ ok: boolean; message: string; models?: string[] } | null>(null);
const modelOptions = ref<string[]>([]);
const modelLoading = ref(false);
const selectedModel = ref("");
const selectedReasoning = ref<"auto" | "low" | "medium" | "high" | "xhigh">("auto");
const composerSettingsOpen = ref(false);
const query = ref("");
const progress = ref<string[]>([]);
const messages = ref<Message[]>([]);
const conversations = ref<Conversation[]>([]);
const currentThreadId = ref<string | null>(null);
const messageList = ref<HTMLElement | null>(null);
const composerTextarea = ref<HTMLTextAreaElement | null>(null);
const profileLoading = ref(false);
const profileNotice = ref("");
const profileError = ref("");
const profileForm = ref({ display_name: "" });
const passwordForm = ref({
  current_password: "",
  new_password: "",
  confirm_password: "",
});
const attachments = ref<Attachment[]>([]);
const attachmentInput = ref<HTMLInputElement | null>(null);
const attachmentDragging = ref(false);
const attachmentLoading = ref(false);
const voiceSupported = ref(false);
const voiceSupportReason = ref("");
const voiceState = ref<VoiceState>("idle");
const voiceTranscript = ref("");
const ttsAvailable = ref(false);
const preferredSpeechVoice = ref<SpeechSynthesisVoice | null>(null);
let speechRecognition: SpeechRecognitionLike | null = null;
let recognitionFinalText = "";
let recognitionLatestText = "";
let speechVoicesChangedHandler: (() => void) | null = null;
let speechRunId = 0;
let currentSpeechAudio: HTMLAudioElement | null = null;
let currentSpeechObjectUrl = "";
let speechQueue: string[] = [];
let speechBuffer = "";
let speechQueueRunning = false;
let speechStreamReceived = false;
let speechStreamEnded = false;

const presets: Record<string, Partial<ProviderForm>> = {
  deepseek: {
    name: "DeepSeek",
    provider_type: "deepseek",
    protocol: "openai_chat",
    endpoint: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
  },
  openai: {
    name: "OpenAI",
    provider_type: "openai",
    protocol: "openai_chat",
    endpoint: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
  },
  dashscope: {
    name: "阿里云百炼",
    provider_type: "dashscope",
    protocol: "openai_chat",
    endpoint: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
  },
  anthropic: {
    name: "Anthropic",
    provider_type: "anthropic",
    protocol: "anthropic_messages",
    endpoint: "https://api.anthropic.com/v1",
    model: "claude-3-5-sonnet-latest",
    api_version: "2023-06-01",
  },
  gemini: {
    name: "Google Gemini",
    provider_type: "gemini",
    protocol: "gemini_generate",
    endpoint: "https://generativelanguage.googleapis.com/v1beta",
    model: "gemini-2.0-flash",
  },
  custom: {
    name: "Custom Provider",
    provider_type: "custom",
    protocol: "openai_chat",
    endpoint: "https://api.example.com/v1",
    model: "your-model",
  },
};

const t = (zh: string, en: string) => (locale.value === "zh" ? zh : en);
const activeProvider = computed(
  () => providers.value.find((item) => item.active) || null,
);
const needsSetup = computed(
  () => Boolean(token.value) && !activeProvider.value,
);
const chatModelOptions = computed(() => {
  const provider = activeProvider.value;
  if (!provider) return [];
  const options = [...(provider.available_models || [])];
  if (provider.model && !options.includes(provider.model)) options.unshift(provider.model);
  if (selectedModel.value && !options.includes(selectedModel.value)) options.unshift(selectedModel.value);
  return options;
});
const composerHasText = computed(() => query.value.trim().length > 0);
const composerExpanded = computed(
  () => attachments.value.length > 0 || query.value.trim().length >= 24,
);
function resizeComposer() {
  const textarea = composerTextarea.value;
  if (!textarea) return;
  const minHeight = 42;
  const maxHeight = 220;
  textarea.style.height = "auto";
  const nextHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight);
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY = textarea.scrollHeight > maxHeight ? "auto" : "hidden";
}
function syncChatSettings() {
  const provider = activeProvider.value;
  selectedModel.value = provider?.model || "";
  selectedReasoning.value = provider?.reasoning_effort || "auto";
}
function reasoningLabel(value: "auto" | "low" | "medium" | "high" | "xhigh") {
  const labels = {
    auto: t("自动", "Auto"),
    low: t("低", "Low"),
    medium: t("中", "Medium"),
    high: t("高", "High"),
    xhigh: t("极高", "X-High"),
  };
  return labels[value];
}
watch(activeProvider, syncChatSettings, { immediate: true });
watch(query, () => requestAnimationFrame(() => resizeComposer()));
function setTheme(next: "light" | "dark") {
  theme.value = next;
  localStorage.setItem("deepresearch_theme", next);
}
function setLocale(next: "zh" | "en") {
  locale.value = next;
  localStorage.setItem("deepresearch_locale", next);
}
function authHeaders(): Record<string, string> {
  return token.value ? { Authorization: `Bearer ${token.value}` } : {};
}

async function request(path: string, init: RequestInit = {}) {
  const response = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `${response.status}`);
  return data;
}

async function uploadAttachments(files: FileList | File[]) {
  if (!token.value || !files.length) return;
  const selected = Array.from(files);
  if (attachments.value.length + selected.length > 5) {
    errorMessage.value = t(
      "一条消息最多添加 5 个附件",
      "Add up to 5 attachments per message",
    );
    return;
  }
  attachmentLoading.value = true;
  errorMessage.value = "";
  try {
    const body = new FormData();
    selected.forEach((file) => body.append("files", file));
    const response = await fetch("/api/v1/attachments", {
      method: "POST",
      headers: authHeaders(),
      body,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `${response.status}`);
    attachments.value = [...attachments.value, ...(data as Attachment[])];
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t("附件上传失败", "Attachment upload failed");
  } finally {
    attachmentLoading.value = false;
    if (attachmentInput.value) attachmentInput.value.value = "";
  }
}
function onAttachmentInput(event: Event) {
  const input = event.target as HTMLInputElement;
  if (input.files) void uploadAttachments(input.files);
}
function onAttachmentDrop(event: DragEvent) {
  attachmentDragging.value = false;
  if (event.dataTransfer?.files)
    void uploadAttachments(event.dataTransfer.files);
}
async function removeAttachment(attachment: Attachment) {
  try {
    await request(`/api/v1/attachments/${attachment.id}`, { method: "DELETE" });
    attachments.value = attachments.value.filter(
      (item) => item.id !== attachment.id,
    );
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t("附件删除失败", "Attachment removal failed");
  }
}

function resetProviderForm() {
  editingProviderId.value = null;
  form.value = {
    name: "DeepSeek",
    provider_type: "deepseek",
    protocol: "openai_chat",
    endpoint: "https://api.deepseek.com/v1",
    api_key: "",
    model: "deepseek-chat",
    api_version: "",
    reasoning_effort: "auto",
  };
  testResult.value = null;
  modelOptions.value = [];
}
function applyPreset(key: string) {
  form.value = {
    ...form.value,
    ...presets[key],
    api_key: form.value.api_key || "",
  } as ProviderForm;
  testResult.value = null;
  modelOptions.value = [];
}
function editProvider(provider: Provider) {
  editingProviderId.value = provider.id;
  form.value = {
    name: provider.name,
    provider_type: provider.provider_type,
    protocol: provider.protocol,
    endpoint: provider.endpoint,
    api_key: "",
    model: provider.model,
    api_version: provider.api_version || "",
    reasoning_effort: provider.reasoning_effort || "auto",
  };
  testResult.value = null;
  modelOptions.value = [...(provider.available_models || [])];
  errorMessage.value = "";
  notice.value = "";
  view.value = "settings";
}

async function submitAuth() {
  authLoading.value = true;
  errorMessage.value = "";
  try {
    const path =
      authMode.value === "login"
        ? "/api/v1/auth/login"
        : "/api/v1/auth/register";
    const data = await request(path, {
      method: "POST",
      body: JSON.stringify(authForm.value),
    });
    token.value = data.access_token;
    user.value = data.user;
    localStorage.setItem("deepresearch_token", token.value);
    await loadProviders();
    await loadConversations();
    if (activeProvider.value) {
      const firstConversation = conversations.value[0];
      if (firstConversation) await selectConversation(firstConversation);
      else startNewConversation();
    }
    view.value = activeProvider.value ? "chat" : "settings";
    notice.value = activeProvider.value
      ? t("登录成功", "Signed in")
      : t(
          "账号已准备好，请先配置 AI Provider",
          "Account ready. Configure an AI Provider first.",
        );
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : t("请求失败", "Request failed");
  } finally {
    authLoading.value = false;
  }
}

async function loadProviders() {
  if (!token.value) return;
  try {
    providers.value = await request("/api/v1/providers");
    syncChatSettings();
  } catch {
    logout(false);
  }
}
async function loadConversations() {
  if (!token.value) return;
  try {
    conversations.value = await request("/api/v1/research/conversations");
  } catch {
    conversations.value = [];
  }
}
function createThreadId() {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return `thread-${user.value?.id || "local"}-${suffix}`;
}
function conversationThreadId() {
  if (!currentThreadId.value) currentThreadId.value = createThreadId();
  return currentThreadId.value;
}
async function loadConversationHistory(threadId = conversationThreadId()) {
  if (!token.value || !user.value) return;
  try {
    const records = (await request(
      `/api/v1/research/history?thread_id=${encodeURIComponent(threadId)}`,
    )) as ConversationRecord[];
    messages.value = records.map((item) => ({
      id: String(item.id),
      role: item.role,
      content: item.content,
    }));
  } catch {
    // History is supplemental; a temporary read failure must not log the user out.
  }
}
async function selectConversation(conversation: Conversation) {
  if (loading.value) return;
  currentThreadId.value = conversation.thread_id;
  messages.value = [];
  errorMessage.value = "";
  view.value = "chat";
  await loadConversationHistory(conversation.thread_id);
}
async function deleteConversation(conversation: Conversation) {
  if (loading.value) return;
  const confirmed = window.confirm(
    t(
      `确定删除“${conversation.title}”吗？删除后无法恢复。`,
      `Delete “${conversation.title}”? This cannot be undone.`,
    ),
  );
  if (!confirmed) return;
  try {
    await request(
      `/api/v1/research/conversations/${encodeURIComponent(conversation.thread_id)}`,
      { method: "DELETE" },
    );
    conversations.value = conversations.value.filter(
      (item) => item.thread_id !== conversation.thread_id,
    );
    if (currentThreadId.value === conversation.thread_id) {
      startNewConversation();
    }
    notice.value = t("对话已删除", "Conversation deleted");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : t("删除失败", "Delete failed");
  }
}
function startNewConversation() {
  if (loading.value) return;
  currentThreadId.value = createThreadId();
  messages.value = [];
  query.value = "";
  attachments.value = [];
  errorMessage.value = "";
  notice.value = "";
  view.value = "chat";
}
function openProfile() {
  if (!user.value) return;
  profileForm.value.display_name = user.value.display_name;
  passwordForm.value = {
    current_password: "",
    new_password: "",
    confirm_password: "",
  };
  profileNotice.value = "";
  profileError.value = "";
  view.value = "profile";
}
function handleAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !user.value) return;
  if (!file.type.startsWith("image/")) {
    profileError.value = t("请选择图片文件", "Please choose an image file");
    input.value = "";
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    profileError.value = t(
      "头像不能超过 2MB",
      "Avatar must be smaller than 2MB",
    );
    input.value = "";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    user.value = { ...user.value!, avatar_data: String(reader.result || "") };
    profileError.value = "";
  };
  reader.readAsDataURL(file);
}
async function updateProfile() {
  if (!user.value) return;
  profileLoading.value = true;
  profileNotice.value = "";
  profileError.value = "";
  try {
    const updated = await request("/api/v1/auth/me", {
      method: "PATCH",
      body: JSON.stringify({
        display_name: profileForm.value.display_name,
        avatar_data: user.value.avatar_data || "",
      }),
    });
    user.value = updated;
    profileNotice.value = t("个人资料已更新", "Profile updated");
  } catch (error) {
    profileError.value =
      error instanceof Error ? error.message : t("保存失败", "Save failed");
  } finally {
    profileLoading.value = false;
  }
}
async function changePassword() {
  profileLoading.value = true;
  profileNotice.value = "";
  profileError.value = "";
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    profileError.value = t(
      "两次输入的新密码不一致",
      "New passwords do not match",
    );
    profileLoading.value = false;
    return;
  }
  try {
    await request("/api/v1/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: passwordForm.value.current_password,
        new_password: passwordForm.value.new_password,
      }),
    });
    passwordForm.value = {
      current_password: "",
      new_password: "",
      confirm_password: "",
    };
    profileNotice.value = t(
      "密码已修改，请妥善保管",
      "Password changed successfully",
    );
  } catch (error) {
    profileError.value =
      error instanceof Error
        ? error.message
        : t("修改密码失败", "Password change failed");
  } finally {
    profileLoading.value = false;
  }
}
async function testProvider() {
  testResult.value = null;
  loading.value = true;
  errorMessage.value = "";
  try {
    testResult.value = await request("/api/v1/providers/test", {
      method: "POST",
      body: JSON.stringify(form.value),
    });
    if (testResult.value?.models?.length) {
      modelOptions.value = testResult.value.models;
      if (!modelOptions.value.includes(form.value.model))
        form.value.model = modelOptions.value[0] || form.value.model;
    }
  } catch (error) {
    testResult.value = {
      ok: false,
      message:
        error instanceof Error
          ? error.message
          : t("连接失败", "Connection failed"),
    };
  } finally {
    loading.value = false;
  }
}
async function fetchModels() {
  modelLoading.value = true;
  errorMessage.value = "";
  testResult.value = null;
  try {
    const data = editingProviderId.value !== null && !form.value.api_key
      ? await request(`/api/v1/providers/${editingProviderId.value}/models`)
      : await request("/api/v1/providers/models", {
          method: "POST",
          body: JSON.stringify(form.value),
        });
    modelOptions.value = data.models || [];
    if (editingProviderId.value !== null && modelOptions.value.length) {
      providers.value = providers.value.map((provider) =>
        provider.id === editingProviderId.value
          ? { ...provider, available_models: [...modelOptions.value] }
          : provider,
      );
    }
    testResult.value = { ok: Boolean(data.ok), message: data.message, models: modelOptions.value };
    if (modelOptions.value.length && !modelOptions.value.includes(form.value.model))
      form.value.model = modelOptions.value[0] || form.value.model;
  } catch (error) {
    testResult.value = {
      ok: false,
      message: error instanceof Error ? error.message : t("获取模型失败", "Model discovery failed"),
    };
  } finally {
    modelLoading.value = false;
  }
}
async function saveProvider() {
  loading.value = true;
  errorMessage.value = "";
  notice.value = "";
  try {
    if (editingProviderId.value !== null) {
      const current = providers.value.find(
        (item) => item.id === editingProviderId.value,
      );
      const keptExistingApiKey = !form.value.api_key;
      const data = await request(
        `/api/v1/providers/${editingProviderId.value}`,
        {
          method: "PUT",
          body: JSON.stringify({
            ...form.value,
            available_models: modelOptions.value,
            api_key: form.value.api_key || null,
            active: Boolean(current?.active),
          }),
        },
      );
      providers.value = providers.value.map((item) =>
        item.id === data.id ? data : item,
      );
      syncChatSettings();
      resetProviderForm();
      notice.value = keptExistingApiKey
        ? t(
            "Provider 已更新，原 API Key 已保留",
            "Provider updated; the existing API key was kept",
          )
        : t("Provider 和 API Key 已更新", "Provider and API key updated");
    } else {
      const data = await request("/api/v1/providers", {
        method: "POST",
        body: JSON.stringify({
          ...form.value,
          available_models: modelOptions.value,
          active: true,
        }),
      });
      providers.value = [
        ...providers.value.map((item) => ({ ...item, active: false })),
        data,
      ];
      syncChatSettings();
      resetProviderForm();
      view.value = "chat";
      notice.value = t("Provider 已保存并启用", "Provider saved and activated");
      messages.value = [
        {
          id: `welcome-${Date.now()}`,
          role: "assistant",
          content: t(
            "你好，我是 DeepResearch。你的 Provider 已连接，可以开始提问。",
            "Hello, I am DeepResearch. Your Provider is connected and ready.",
          ),
        },
      ];
    }
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : t("保存失败", "Save failed");
  } finally {
    loading.value = false;
  }
}
async function activateProvider(provider: Provider) {
  try {
    const data = await request(`/api/v1/providers/${provider.id}/activate`, {
      method: "PUT",
    });
    providers.value = providers.value.map((item) => ({
      ...item,
      active: item.id === data.id,
    }));
    syncChatSettings();
    view.value = "chat";
  } catch (error) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t("启用失败", "Activation failed");
  }
}
async function deleteProvider(provider: Provider) {
  const confirmed = window.confirm(
    t(
      `确定删除「${provider.name}」吗？删除后需要重新配置 API Key。`,
      `Delete “${provider.name}”? You will need to configure its API key again.`,
    ),
  );
  if (!confirmed) return;
  try {
    await request(`/api/v1/providers/${provider.id}`, { method: "DELETE" });
    providers.value = providers.value.filter((item) => item.id !== provider.id);
    if (editingProviderId.value === provider.id) resetProviderForm();
    if (!providers.value.some((item) => item.active)) view.value = "settings";
    notice.value = t("Provider 已删除", "Provider deleted");
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : t("删除失败", "Delete failed");
  }
}
function logout(clear = true) {
  token.value = "";
  user.value = null;
  providers.value = [];
  view.value = "chat";
  messages.value = [];
  if (clear) localStorage.removeItem("deepresearch_token");
}
function inlineMarkdown(value: string) {
  const escaped = value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
  const codeTokens: string[] = [];
  const withCode = escaped.replace(/`([^`]+)`/g, (_match, code: string) => {
    const token = `@@CODE_${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });
  const linked = withCode.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  );
  const formatted = linked
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  return formatted.replace(
    /@@CODE_(\d+)@@/g,
    (_match, index: string) => codeTokens[Number(index)] || "",
  );
}

function markdownToHtml(value: string) {
  const lines = value.replaceAll("\r\n", "\n").split("\n");
  const output: string[] = [];
  let paragraph: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let inCode = false;
  let codeLines: string[] = [];

  const closeParagraph = () => {
    if (paragraph.length) {
      output.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
      paragraph = [];
    }
  };
  const closeList = () => {
    if (listType) {
      output.push(`</${listType}>`);
      listType = null;
    }
  };
  const closeCode = () => {
    if (inCode) {
      output.push(
        `<pre><code>${codeLines.join("\n").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</code></pre>`,
      );
      codeLines = [];
      inCode = false;
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      closeParagraph();
      closeList();
      if (inCode) closeCode();
      else inCode = true;
      continue;
    }
    if (inCode) {
      codeLines.push(line);
      continue;
    }
    if (!line.trim()) {
      closeParagraph();
      closeList();
      continue;
    }
    const heading = line.match(/^\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) {
      const level = heading[1]?.length || 1;
      const title = heading[2] || "";
      closeParagraph();
      closeList();
      output.push(`<h${level}>${inlineMarkdown(title)}</h${level}>`);
      continue;
    }
    const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    if (unordered || ordered) {
      closeParagraph();
      const nextType = unordered ? "ul" : "ol";
      if (listType !== nextType) {
        closeList();
        output.push(`<${nextType}>`);
        listType = nextType;
      }
      const itemText = unordered?.[1] || ordered?.[1] || "";
      output.push(`<li>${inlineMarkdown(itemText)}</li>`);
      continue;
    }
    const quote = line.match(/^\s*>\s?(.*)$/);
    if (quote) {
      closeParagraph();
      closeList();
      output.push(`<blockquote>${inlineMarkdown(quote[1] || "")}</blockquote>`);
      continue;
    }
    closeList();
    paragraph.push(line);
  }
  closeParagraph();
  closeList();
  closeCode();
  return output.join("");
}

function setupVoiceRecognition() {
  if (
    !window.isSecureContext &&
    !["localhost", "127.0.0.1"].includes(window.location.hostname)
  ) {
    voiceSupportReason.value = t(
      "麦克风需要 HTTPS；当前 HTTP 地址无法安全调用麦克风。",
      "Microphone access requires HTTPS on this address.",
    );
    return;
  }
  const speechWindow = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  const Recognition =
    speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
  if (!Recognition) {
    voiceSupportReason.value = t(
      "当前浏览器不支持语音识别，请使用最新版 Chrome 或 Edge。",
      "Speech recognition is unavailable. Use the latest Chrome or Edge.",
    );
    return;
  }
  voiceSupported.value = true;
  voiceSupportReason.value = "";
  speechRecognition = new Recognition();
  speechRecognition.continuous = false;
  speechRecognition.interimResults = true;
  speechRecognition.maxAlternatives = 1;
  speechRecognition.onresult = (event) => {
    let interimText = "";
    let finalText = "";
    for (let index = 0; index < event.results.length; index += 1) {
      const result = event.results[index];
      const transcript = result?.[0]?.transcript || "";
      if (result?.isFinal) finalText += transcript;
      else interimText += transcript;
    }
    recognitionFinalText = finalText.trim();
    recognitionLatestText = `${finalText} ${interimText}`.trim();
    voiceTranscript.value = recognitionLatestText;
  };
  speechRecognition.onerror = (event) => {
    voiceState.value = "idle";
    voiceTranscript.value = "";
    const messages: Record<string, [string, string]> = {
      "not-allowed": [
        "麦克风权限被拒绝，请在浏览器地址栏中允许麦克风后重试。",
        "Microphone permission was denied. Allow it in the address bar and retry.",
      ],
      "audio-capture": [
        "没有检测到可用麦克风，请检查系统输入设备。",
        "No microphone was detected. Check the system input device.",
      ],
      network: [
        "浏览器语音识别服务连接失败，可改用 OpenAI Realtime 语音。",
        "The browser speech service could not connect. OpenAI Realtime can be used instead.",
      ],
      "no-speech": [
        "没有检测到语音，请靠近麦克风后重试。",
        "No speech was detected. Move closer to the microphone and retry.",
      ],
    };
    const message = messages[event.error || ""] || [
      "语音输入失败，请检查麦克风权限和网络连接。",
      "Voice input failed. Check microphone permission and network access.",
    ];
    errorMessage.value = t(message[0], message[1]);
  };
  speechRecognition.onend = async () => {
    const transcript =
      recognitionFinalText.trim() || recognitionLatestText.trim();
    recognitionFinalText = "";
    recognitionLatestText = "";
    if (voiceState.value !== "listening") return;
    if (!transcript) {
      voiceState.value = "idle";
      voiceTranscript.value = "";
      return;
    }
    voiceTranscript.value = transcript;
    query.value = transcript;
    voiceState.value = "thinking";
    await sendQuery({ speakResponse: true });
  };
}

function toggleVoice() {
  if (voiceState.value === "speaking") {
    stopVoiceOutput();
    return;
  }
  if (voiceState.value === "listening") {
    speechRecognition?.stop();
    return;
  }
  if (loading.value || !activeProvider.value) return;
  if (!voiceSupported.value || !speechRecognition) {
    errorMessage.value =
      voiceSupportReason.value ||
      t(
        "当前环境不支持语音输入。",
        "Voice input is unavailable in this environment.",
      );
    return;
  }
  errorMessage.value = "";
  voiceTranscript.value = "";
  recognitionFinalText = "";
  recognitionLatestText = "";
  speechRecognition.lang = locale.value === "zh" ? "zh-CN" : "en-US";
  voiceState.value = "listening";
  try {
    speechRecognition.start();
  } catch (error) {
    voiceState.value = "idle";
    errorMessage.value =
      error instanceof DOMException && error.name === "NotAllowedError"
        ? t(
            "麦克风权限被拒绝，请允许麦克风后重试。",
            "Microphone permission was denied. Allow it and retry.",
          )
        : t("无法启动语音输入，请稍后重试。", "Could not start voice input.");
  }
}

function speechVoiceScore(voice: SpeechSynthesisVoice, language: "zh" | "en") {
  const name = `${voice.name} ${voice.lang}`.toLowerCase();
  const target = language === "zh" ? "zh" : "en";
  const femaleMarkers = language === "zh"
    ? ["xiaoxiao", "xiaoyi", "xiaohan", "xiaomeng", "晓晓", "晓伊", "晓涵", "晓梦", "女"]
    : ["samantha", "karen", "victoria", "zira", "jenny", "aria", "ava", "allison", "serena", "female", "女"];
  const maleMarkers = language === "zh"
    ? ["yunxi", "yunyang", "yunxia", "yunfeng", "云希", "云扬", "云夏", "云枫", "男"]
    : ["david", "mark", "alex", "daniel", "male", "男"];
  const naturalMarkers = ["natural", "online", "neural", "premium", "enhanced", "edge"];
  let score = 0;
  if (voice.lang.toLowerCase() === (language === "zh" ? "zh-cn" : "en-us")) score += 50;
  else if (voice.lang.toLowerCase().startsWith(target)) score += 30;
  if (femaleMarkers.some((marker) => name.includes(marker))) score += 80;
  if (maleMarkers.some((marker) => name.includes(marker))) score -= 80;
  if (naturalMarkers.some((marker) => name.includes(marker))) score += 35;
  if (!voice.localService) score += 8;
  return score;
}

function refreshSpeechVoice() {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return;
  const language = locale.value;
  preferredSpeechVoice.value = [...voices].sort(
    (left, right) => speechVoiceScore(right, language) - speechVoiceScore(left, language),
  )[0] || null;
}

function setupSpeechSynthesis() {
  if (!("speechSynthesis" in window)) return;
  speechVoicesChangedHandler = refreshSpeechVoice;
  refreshSpeechVoice();
  window.speechSynthesis.addEventListener("voiceschanged", speechVoicesChangedHandler);
}

async function loadTTSConfig() {
  try {
    const config = (await request("/api/v1/tts/config")) as { enabled?: boolean };
    ttsAvailable.value = Boolean(config.enabled);
  } catch {
    ttsAvailable.value = false;
  }
}

function splitSpeechText(value: string, maxLength = 72) {
  const sentences = value.match(/[^。！？!?；;\n]+[。！？!?；;\n]?/g) || [value];
  const chunks: string[] = [];
  let current = "";
  for (const sentence of sentences) {
    const next = `${current}${sentence}`.trim();
    if (current && next.length > maxLength) {
      chunks.push(current);
      current = sentence.trim();
    } else {
      current = next;
    }
  }
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

function takeSpeechSentences(force = false) {
  const chunks: string[] = [];
  const completed = speechBuffer.match(/[\s\S]*?[。！？!?；;\n]+/g) || [];
  if (completed.length) {
    let consumed = 0;
    for (const sentence of completed) {
      const candidate = sentence.trim();
      if (!candidate) {
        consumed += sentence.length;
        continue;
      }
      const previous = chunks.at(-1);
      if (previous !== undefined && previous.length < 8 && candidate.length < 24) {
        chunks[chunks.length - 1] = `${previous}${candidate}`;
      } else {
        chunks.push(candidate);
      }
      consumed += sentence.length;
    }
    speechBuffer = speechBuffer.slice(consumed);
  }
  if (force && speechBuffer.trim()) {
    chunks.push(...splitSpeechText(speechBuffer));
    speechBuffer = "";
  } else if (speechBuffer.length >= 84) {
    const splitAt = Math.max(
      speechBuffer.lastIndexOf("，", 72),
      speechBuffer.lastIndexOf(",", 72),
      speechBuffer.lastIndexOf(" ", 72),
    );
    if (splitAt > 12) {
      chunks.push(speechBuffer.slice(0, splitAt + 1).trim());
      speechBuffer = speechBuffer.slice(splitAt + 1);
    }
  }
  return chunks.filter(Boolean).map(spokenText).filter(Boolean);
}

function spokenText(value: string) {
  return value
    .replace(/```[\s\S]*?```/g, "代码内容已省略")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/\[[A-Z]+\d+_\d+-\d+\]/g, "")
    .replace(/[#*_>`~-]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 8000);
}

function finishSpeech(runId: number) {
  if (runId !== speechRunId) return;
  voiceState.value = "idle";
  voiceTranscript.value = "";
}

function speakWithBrowser(text: string, runId: number) {
  if (!("speechSynthesis" in window)) {
    finishSpeech(runId);
    return;
  }
  refreshSpeechVoice();
  const chunks = splitSpeechText(text);
  let index = 0;
  const speakNext = () => {
    if (runId !== speechRunId || index >= chunks.length) {
      finishSpeech(runId);
      return;
    }
    const chunk = chunks[index++] || "";
    const utterance = new SpeechSynthesisUtterance(spokenText(chunk));
    utterance.lang = locale.value === "zh" ? "zh-CN" : "en-US";
    utterance.voice = preferredSpeechVoice.value;
    utterance.rate = locale.value === "zh" ? 0.94 : 0.97;
    utterance.pitch = locale.value === "zh" ? 1.07 : 1.04;
    utterance.volume = 1;
    utterance.onend = () => window.setTimeout(speakNext, 55);
    utterance.onerror = () => finishSpeech(runId);
    window.speechSynthesis.speak(utterance);
  };
  window.setTimeout(speakNext, 50);
}

function speakBrowserChunk(text: string, runId: number) {
  return new Promise<void>((resolve, reject) => {
    if (runId !== speechRunId || !("speechSynthesis" in window)) {
      resolve();
      return;
    }
    refreshSpeechVoice();
    const utterance = new SpeechSynthesisUtterance(spokenText(text));
    utterance.lang = locale.value === "zh" ? "zh-CN" : "en-US";
    utterance.voice = preferredSpeechVoice.value;
    utterance.rate = locale.value === "zh" ? 0.94 : 0.97;
    utterance.pitch = locale.value === "zh" ? 1.07 : 1.04;
    utterance.volume = 1;
    utterance.onend = () => resolve();
    utterance.onerror = () => reject(new Error("browser speech failed"));
    window.speechSynthesis.speak(utterance);
  });
}

async function playCloudSpeech(text: string, runId: number) {
  const response = await fetch("/api/v1/tts/synthesize", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ text }),
  });
  if (!response.ok) throw new Error(`TTS ${response.status}`);
  const blob = await response.blob();
  if (runId !== speechRunId) return;
  currentSpeechObjectUrl = URL.createObjectURL(blob);
  currentSpeechAudio = new Audio(currentSpeechObjectUrl);
  currentSpeechAudio.preload = "auto";
  await new Promise<void>((resolve, reject) => {
    const audio = currentSpeechAudio;
    if (!audio) return reject(new Error("audio unavailable"));
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("audio playback failed"));
    void audio.play().catch(reject);
  });
  currentSpeechAudio = null;
  URL.revokeObjectURL(currentSpeechObjectUrl);
  currentSpeechObjectUrl = "";
}

async function drainSpeechQueue(runId: number) {
  if (speechQueueRunning) return;
  speechQueueRunning = true;
  voiceState.value = "speaking";
  try {
    while (runId === speechRunId && speechQueue.length) {
      const chunk = speechQueue.shift() || "";
      if (!chunk) continue;
      if (ttsAvailable.value) {
        try {
          await playCloudSpeech(chunk, runId);
        } catch {
          // Keep the conversation usable when a cloud provider times out.
          ttsAvailable.value = false;
          try {
            await speakBrowserChunk(chunk, runId);
          } catch {
            // A browser autoplay restriction should not break the Agent stream.
          }
        }
      } else {
        try {
          await speakBrowserChunk(chunk, runId);
        } catch {
          // Speech output is best-effort; text chat remains available.
        }
      }
    }
  } finally {
    speechQueueRunning = false;
    if (runId === speechRunId && speechStreamEnded && !speechQueue.length && !speechBuffer.trim()) {
      finishSpeech(runId);
    }
  }
}

function beginSpeechStream() {
  speechRunId += 1;
  const runId = speechRunId;
  window.speechSynthesis?.cancel();
  currentSpeechAudio?.pause();
  currentSpeechAudio = null;
  if (currentSpeechObjectUrl) {
    URL.revokeObjectURL(currentSpeechObjectUrl);
    currentSpeechObjectUrl = "";
  }
  speechQueue = [];
  speechBuffer = "";
  speechQueueRunning = false;
  speechStreamReceived = false;
  speechStreamEnded = false;
  voiceState.value = "thinking";
  return runId;
}

function enqueueSpeechDelta(value: string, runId: number) {
  if (runId !== speechRunId || !value) return;
  speechStreamReceived = true;
  speechBuffer += value;
  speechQueue.push(...takeSpeechSentences());
  void drainSpeechQueue(runId);
}

function endSpeechStream(finalText: string, runId: number) {
  if (runId !== speechRunId) return;
  speechStreamEnded = true;
  speechQueue.push(...takeSpeechSentences(true));
  if (!speechStreamReceived) {
    speakAnswer(finalText);
    return;
  }
  void drainSpeechQueue(runId);
}

async function speakAnswer(value: string) {
  const text = spokenText(value);
  const runId = ++speechRunId;
  if (!text) {
    finishSpeech(runId);
    return;
  }
  window.speechSynthesis?.cancel();
  currentSpeechAudio?.pause();
  currentSpeechAudio = null;
  voiceState.value = "speaking";
  if (ttsAvailable.value) {
    let playedCloudAudio = false;
    try {
      for (const chunk of splitSpeechText(text)) {
        if (runId !== speechRunId) return;
        await playCloudSpeech(chunk, runId);
        playedCloudAudio = true;
      }
      finishSpeech(runId);
      return;
    } catch {
      // A provider timeout or autoplay restriction must not break voice chat.
      if (playedCloudAudio || runId !== speechRunId) {
        finishSpeech(runId);
        return;
      }
    }
  }
  speakWithBrowser(text, runId);
}

function stopVoiceOutput() {
  speechRunId += 1;
  window.speechSynthesis?.cancel();
  currentSpeechAudio?.pause();
  currentSpeechAudio = null;
  if (currentSpeechObjectUrl) {
    URL.revokeObjectURL(currentSpeechObjectUrl);
    currentSpeechObjectUrl = "";
  }
  speechQueue = [];
  speechBuffer = "";
  speechQueueRunning = false;
  speechStreamReceived = false;
  speechStreamEnded = false;
  voiceState.value = "idle";
  voiceTranscript.value = "";
}

function voiceLabel() {
  if (voiceState.value === "listening") return t("正在聆听...", "Listening...");
  if (voiceState.value === "thinking") return t("正在思考...", "Thinking...");
  if (voiceState.value === "speaking") return t("正在回答...", "Speaking...");
  return t("语音对话", "Voice chat");
}

function voiceHint() {
  if (!voiceSupported.value)
    return (
      voiceSupportReason.value ||
      t("浏览器暂不支持语音输入", "Voice input is unavailable")
    );
  if (voiceState.value === "listening")
    return voiceTranscript.value || t("说完后点击结束", "Tap to finish speaking");
  if (voiceState.value === "thinking")
    return t("语音已发送给 Agent", "Voice sent to the Agent");
  if (voiceState.value === "speaking")
    return t("点击语音球停止播放", "Tap the orb to stop playback");
  return t("点击开始说话", "Tap to start speaking");
}

async function sendQuery(options: { speakResponse?: boolean } = {}) {
  if (
    (!query.value.trim() && !attachments.value.length) ||
    loading.value ||
    !activeProvider.value
  )
    return;
  const text = query.value.trim();
  const sentAttachments = [...attachments.value];
  query.value = "";
  attachments.value = [];
  loading.value = true;
  const speechRun = options.speakResponse ? beginSpeechStream() : 0;
  errorMessage.value = "";
  progress.value = [];
  const displayText = [
    text,
    sentAttachments.length
      ? `\n📎 ${sentAttachments.map((item) => item.filename).join(", ")}`
      : "",
  ]
    .join("")
    .trim();
  messages.value.push({
    id: `u-${Date.now()}`,
    role: "user",
    content: displayText,
  });
  const statusId = `s-${Date.now()}`;
  messages.value.push({
    id: statusId,
    role: "status",
    content: t("正在初始化研究链路...", "Initializing research workflow..."),
  });
  try {
    const response = await fetch("/api/v1/research/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({
        query: text,
        attachment_ids: sentAttachments.map((item) => item.id),
        thread_id: conversationThreadId(),
        model: selectedModel.value || undefined,
        reasoning_effort: selectedReasoning.value,
      }),
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${response.status}`);
    }
    if (!response.body)
      throw new Error(t("流式响应不可用", "Streaming response unavailable"));
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      buffer += decoder.decode(part.value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        if (!chunk.startsWith("data: ")) continue;
        const event = JSON.parse(chunk.slice(6));
        if (
          event.type === "phase" ||
          event.type === "status" ||
          event.type === "route"
        ) {
          progress.value.push(event.message);
          const status = messages.value.find((item) => item.id === statusId);
          if (status) status.content = progress.value.slice(-5).join("\n");
        }
        if (event.type === "final") {
          messages.value = messages.value.filter(
            (item) => item.id !== statusId,
          );
          messages.value.push({
            id: `a-${Date.now()}`,
            role: "assistant",
            content: event.final || "",
          });
          void loadConversations();
          if (options.speakResponse) endSpeechStream(String(event.final || ""), speechRun);
        }
        if (event.type === "speech_delta" && options.speakResponse) {
          enqueueSpeechDelta(String(event.text || ""), speechRun);
        }
        if (event.type === "error") throw new Error(event.message);
      }
      if (messageList.value)
        messageList.value.scrollTop = messageList.value.scrollHeight;
    }
  } catch (error) {
    messages.value = messages.value.filter((item) => item.id !== statusId);
    errorMessage.value =
      error instanceof Error ? error.message : t("请求失败", "Request failed");
    if (options.speakResponse) {
      stopVoiceOutput();
    }
  } finally {
    loading.value = false;
    if (options.speakResponse && speechRun === speechRunId && voiceState.value === "thinking") {
      speechStreamEnded = true;
      speechQueue.push(...takeSpeechSentences(true));
      void drainSpeechQueue(speechRun);
    }
  }
}

onMounted(async () => {
  requestAnimationFrame(() => resizeComposer());
  setupVoiceRecognition();
  setupSpeechSynthesis();
  void loadTTSConfig();
  if (token.value) {
    try {
      const currentUser = (await request("/api/v1/auth/me")) as User;
      user.value = currentUser;
      profileForm.value.display_name = currentUser.display_name;
      await loadProviders();
      await loadConversations();
      if (needsSetup.value) view.value = "settings";
      else if (conversations.value.length) {
        const firstConversation = conversations.value[0];
        if (firstConversation) await selectConversation(firstConversation);
      }
      else startNewConversation();
    } catch {
      logout();
    }
  }
  if (!token.value && !messages.value.length)
    messages.value = [
      {
        id: "welcome",
        role: "assistant",
        content: t(
          "登录后配置 Provider，即可开始深度研究。",
          "Sign in and configure a Provider to start researching.",
        ),
      },
    ];
});

onBeforeUnmount(() => {
  speechRunId += 1;
  speechRecognition?.abort();
  if (speechVoicesChangedHandler && "speechSynthesis" in window)
    window.speechSynthesis.removeEventListener("voiceschanged", speechVoicesChangedHandler);
  window.speechSynthesis?.cancel();
  currentSpeechAudio?.pause();
  if (currentSpeechObjectUrl) URL.revokeObjectURL(currentSpeechObjectUrl);
});
</script>

<template>
  <div class="app" :data-theme="theme">
    <header class="topbar">
      <div class="brand">
        <span class="brand-mark"><img src="/jian-shi-mark.svg" alt="" /></span>
        <div>
          <strong>DeepResearch</strong><small>Multi-agent workspace</small>
        </div>
      </div>
      <div class="top-actions">
        <button
          class="text-btn"
          @click="setLocale(locale === 'zh' ? 'en' : 'zh')"
        >
          {{ locale === "zh" ? "EN" : "中文" }}</button
        ><button
          class="text-btn"
          @click="setTheme(theme === 'dark' ? 'light' : 'dark')"
        >
          {{ theme === "dark" ? "☼" : "☾" }}</button
        ><template v-if="user"
          ><button class="user-chip user-chip-button" @click="openProfile">
            <span class="avatar avatar-small"
              ><img
                v-if="user.avatar_data"
                :src="user.avatar_data"
                alt=""
              /><span v-else>{{
                user.display_name.slice(0, 1).toUpperCase()
              }}</span></span
            >{{ user.display_name }}</button
          ><button class="text-btn" @click="logout()">
            {{ t("退出", "Sign out") }}
          </button></template
        >
      </div>
    </header>
    <main v-if="!token" class="auth-shell">
      <section class="auth-intro">
        <span class="eyebrow">AI RESEARCH SYSTEM</span>
        <h1>
          {{
            t(
              "把复杂问题交给一条可追踪的研究链路",
              "Turn complex questions into a traceable research workflow",
            )
          }}
        </h1>
        <p>
          {{
            t(
              "注册后配置你自己的模型 Provider。密钥只在服务端加密保存，未配置前无法调用研究功能。",
              "Create an account, configure your own model Provider, and keep the key encrypted on the server.",
            )
          }}
        </p>
        <div class="intro-points">
          <span>Intent routing</span><span>Evidence review</span
          ><span>SSE streaming</span>
        </div>
      </section>
      <section class="auth-card">
        <div class="tabs">
          <button
            :class="{ active: authMode === 'login' }"
            @click="authMode = 'login'"
          >
            {{ t("登录", "Sign in") }}</button
          ><button
            :class="{ active: authMode === 'register' }"
            @click="authMode = 'register'"
          >
            {{ t("注册", "Create account") }}
          </button>
        </div>
        <h2>
          {{
            authMode === "login"
              ? t("欢迎回来", "Welcome back")
              : t("创建你的账户", "Create your account")
          }}
        </h2>
        <p class="muted">
          {{
            t(
              "使用邮箱和密码进入工作台",
              "Use your email and password to access the workspace",
            )
          }}
        </p>
        <form @submit.prevent="submitAuth">
          <label v-if="authMode === 'register'"
            >{{ t("显示名称", "Display name")
            }}<input
              v-model="authForm.display_name"
              required
              :placeholder="t('例如：你的昵称', 'Your name')" /></label
          ><label
            >{{ t("邮箱", "Email")
            }}<input
              v-model="authForm.email"
              type="email"
              required
              placeholder="you@example.com" /></label
          ><label
            >{{ t("密码", "Password")
            }}<input
              v-model="authForm.password"
              type="password"
              required
              minlength="8"
              placeholder="••••••••"
          /></label>
          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
          <button class="primary-btn" :disabled="authLoading">
            {{
              authLoading
                ? t("处理中...", "Working...")
                : authMode === "login"
                  ? t("登录工作台", "Enter workspace")
                  : t("注册并继续", "Create and continue")
            }}
          </button>
        </form>
      </section>
    </main>
    <main v-else class="workspace">
      <aside class="side-nav">
        <div class="side-title">
          <span class="eyebrow">WORKSPACE</span
          ><button class="side-profile" @click="openProfile">
            <span class="avatar"
              ><img
                v-if="user?.avatar_data"
                :src="user.avatar_data"
                alt=""
              /><span v-else>{{
                user?.display_name.slice(0, 1).toUpperCase()
              }}</span></span
            ><span
              ><h2>{{ user?.display_name }}</h2>
              <p>{{ user?.email }}</p></span
            >
          </button>
        </div>
        <button
          :class="{ selected: view === 'chat' && !needsSetup }"
          @click="view = 'chat'"
        >
          ⌂ <span>{{ t("研究助手", "Research assistant") }}</span></button
        ><button
          :class="{ selected: view === 'settings' }"
          @click="view = 'settings'"
        >
          ⚙ <span>{{ t("API 配置", "API providers") }}</span
          ><i v-if="needsSetup">!</i></button
        ><button :class="{ selected: view === 'profile' }" @click="openProfile">
          ◎ <span>{{ t("个人资料", "Profile") }}</span>
        </button>
        <div class="conversation-nav">
          <div class="conversation-nav-heading">
            <span>{{ t("最近对话", "Recent chats") }}</span>
            <button
              class="new-chat-btn"
              :disabled="loading"
              :title="t('新建对话', 'New chat')"
              @click="startNewConversation"
            >
              ＋
            </button>
          </div>
          <div
            v-for="conversation in conversations"
            :key="conversation.thread_id"
            class="conversation-item"
            :class="{
              selected:
                view === 'chat' && currentThreadId === conversation.thread_id,
            }"
            :title="conversation.title"
            @click="selectConversation(conversation)"
            @keydown.enter="selectConversation(conversation)"
            role="button"
            tabindex="0"
          >
            <span class="conversation-title">{{ conversation.title }}</span>
            <button
              class="conversation-delete-btn"
              type="button"
              :title="t('删除对话', 'Delete conversation')"
              :aria-label="t('删除对话', 'Delete conversation')"
              @click.stop="deleteConversation(conversation)"
            >
              ×
            </button>
          </div>
          <small v-if="!conversations.length" class="conversation-empty">
            {{ t("还没有历史对话", "No conversations yet") }}
          </small>
        </div>
        <div class="side-footer">
          <small>{{
            activeProvider
              ? `${activeProvider.name} · ${activeProvider.model}`
              : t("尚未配置 Provider", "No Provider configured")
          }}</small>
        </div>
      </aside>
      <section v-if="view === 'profile'" class="content profile-content">
        <div class="page-heading">
          <div>
            <span class="eyebrow">ACCOUNT SETTINGS</span>
            <h1>{{ t("个人资料", "Your profile") }}</h1>
            <p>
              {{
                t(
                  "管理你的公开信息和登录安全设置。",
                  "Manage your public profile and sign-in security.",
                )
              }}
            </p>
          </div>
        </div>
        <div class="profile-layout">
          <section class="panel form-panel">
            <div class="profile-hero">
              <span class="avatar avatar-large"
                ><img
                  v-if="user?.avatar_data"
                  :src="user.avatar_data"
                  alt=""
                /><span v-else>{{
                  user?.display_name.slice(0, 1).toUpperCase()
                }}</span></span
              >
              <div>
                <h3>{{ user?.display_name }}</h3>
                <p>{{ user?.email }}</p>
              </div>
            </div>
            <label
              >{{ t("头像", "Avatar")
              }}<input
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                @change="handleAvatarChange"
              /><small class="field-help">{{
                t(
                  "支持 PNG、JPEG、WEBP、GIF，最大 2MB",
                  "PNG, JPEG, WEBP or GIF, up to 2MB",
                )
              }}</small></label
            ><label
              >{{ t("昵称", "Display name")
              }}<input v-model="profileForm.display_name" maxlength="40"
            /></label>
            <p v-if="profileError" class="error">{{ profileError }}</p>
            <p v-if="profileNotice" class="notice">{{ profileNotice }}</p>
            <button
              class="primary-btn"
              :disabled="profileLoading"
              @click="updateProfile"
            >
              {{
                profileLoading
                  ? t("保存中...", "Saving...")
                  : t("保存个人资料", "Save profile")
              }}
            </button>
          </section>
          <section class="panel form-panel">
            <span class="eyebrow">SECURITY</span>
            <h3>{{ t("修改密码", "Change password") }}</h3>
            <label
              >{{ t("当前密码", "Current password")
              }}<input
                v-model="passwordForm.current_password"
                type="password"
                autocomplete="current-password" /></label
            ><label
              >{{ t("新密码", "New password")
              }}<input
                v-model="passwordForm.new_password"
                type="password"
                minlength="8"
                autocomplete="new-password"
              /><small class="field-help">{{
                t("密码长度至少 8 位", "Use at least 8 characters")
              }}</small></label
            ><label
              >{{ t("确认新密码", "Confirm new password")
              }}<input
                v-model="passwordForm.confirm_password"
                type="password"
                minlength="8"
                autocomplete="new-password" /></label
            ><button
              class="secondary-btn"
              :disabled="
                profileLoading ||
                !passwordForm.current_password ||
                !passwordForm.new_password ||
                !passwordForm.confirm_password
              "
              @click="changePassword"
            >
              {{
                profileLoading
                  ? t("提交中...", "Submitting...")
                  : t("更新密码", "Update password")
              }}
            </button>
          </section>
        </div>
      </section>
      <section
        v-else-if="view === 'settings' || needsSetup"
        class="content settings-content"
      >
        <div class="page-heading">
          <div>
            <span class="eyebrow">PROVIDER SETTINGS</span>
            <h1>
              {{
                editingProviderId !== null
                  ? t("编辑 AI Provider", "Edit AI Provider")
                  : t("连接你的 AI Provider", "Connect your AI Provider")
              }}
            </h1>
            <p>
              {{
                t(
                  editingProviderId !== null
                    ? "可更新名称、协议、地址和模型。留空 API Key 会继续使用已加密保存的密钥。"
                    : "先测试连接，再保存并启用。API Key 只在服务端加密存储，不会回传到页面。",
                  editingProviderId !== null
                    ? "Update the name, protocol, endpoint, or model. Leave the API key empty to keep the encrypted key already saved."
                    : "Test the connection before saving. Your API key is encrypted server-side and never returned.",
                )
              }}
            </p>
          </div>
          <span class="secure-badge">● {{ t("加密存储", "Encrypted") }}</span>
        </div>
        <div class="provider-layout">
          <section class="panel form-panel">
            <label
              >{{ t("快速选择供应商", "Provider preset")
              }}<select
                @change="
                  applyPreset(($event.target as HTMLSelectElement).value)
                "
              >
                <option value="custom">
                  {{
                    t("自定义 OpenAI Compatible", "Custom OpenAI Compatible")
                  }}
                </option>
                <option value="deepseek">DeepSeek</option>
                <option value="openai">OpenAI</option>
                <option value="dashscope">
                  {{ t("阿里云百炼", "DashScope") }}
                </option>
                <option value="anthropic">Anthropic</option>
                <option value="gemini">Google Gemini</option>
              </select></label
            >
            <div class="two-col">
              <label
                >{{ t("供应商名称", "Display name")
                }}<input v-model="form.name" /></label
              ><label
                >{{ t("模型 ID", "Model ID") }}<input v-model="form.model"
                  list="provider-model-options"
                /><datalist id="provider-model-options">
                  <option v-for="model in modelOptions" :key="model" :value="model" />
                </datalist>
                <button
                  type="button"
                  class="model-fetch-btn"
                  :disabled="modelLoading || (!form.api_key && editingProviderId === null)"
                  @click="fetchModels"
                >
                  {{ modelLoading ? t("获取中...", "Loading...") : t("自动获取模型", "Fetch models") }}
                </button></label>
            </div>
            <label
              >{{ t("推理强度", "Reasoning effort") }}<select v-model="form.reasoning_effort">
                <option value="auto">{{ t("自动（按模型默认）", "Auto (model default)") }}</option>
                <option value="low">{{ t("低", "Low") }}</option>
                <option value="medium">{{ t("中", "Medium") }}</option>
                <option value="high">{{ t("高", "High") }}</option>
                <option value="xhigh">{{ t("极高", "X-High") }}</option>
              </select>
              <small class="field-help">{{ t("仅对支持 reasoning_effort 的 OpenAI Compatible 模型生效。", "Only applies to OpenAI-compatible models that support reasoning_effort.") }}</small></label
            >
            <label
              >{{ t("API 协议", "API protocol")
              }}<select v-model="form.protocol">
                <option value="openai_chat">OpenAI Chat Completions</option>
                <option value="anthropic_messages">Anthropic Messages</option>
                <option value="gemini_generate">Gemini Generate Content</option>
              </select></label
            ><label
              >{{ t("API Endpoint", "API endpoint")
              }}<input
                v-model="form.endpoint"
                placeholder="https://api.example.com/v1" /></label
            ><label
              >{{ t("API Key", "API key")
              }}<input
                v-model="form.api_key"
                type="password"
                autocomplete="new-password"
                :placeholder="
                  editingProviderId !== null
                    ? t(
                        '留空则保留当前 API Key',
                        'Leave empty to keep the current API key',
                      )
                    : t(
                        '只在这里填写，不会显示在列表中',
                        'Enter once; it will not be shown again',
                      )
                " /></label
            ><label v-if="form.protocol === 'anthropic_messages'"
              >{{ t("API 版本", "API version")
              }}<input v-model="form.api_version" placeholder="2023-06-01"
            /></label>
            <div class="form-actions">
              <button
                class="secondary-btn"
                :disabled="loading || !form.api_key"
                @click="testProvider"
              >
                {{
                  loading
                    ? t("测试中...", "Testing...")
                    : t("测试连接", "Test connection")
                }}</button
              ><button
                class="primary-btn"
                :disabled="loading || (!form.api_key && editingProviderId === null)"
                @click="saveProvider"
              >
                {{
                  editingProviderId !== null
                    ? t("保存修改", "Save changes")
                    : t("保存并启用", "Save and activate")
                }}
              </button>
              <button
                v-if="editingProviderId !== null"
                class="text-btn"
                :disabled="loading"
                @click="resetProviderForm"
              >
                {{ t("取消编辑", "Cancel editing") }}
              </button>
            </div>
            <p
              v-if="testResult"
              :class="['test-result', testResult.ok ? 'ok' : 'bad']"
            >
              {{ testResult.ok ? "✓" : "×" }} {{ testResult.message }}
            </p>
            <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
          </section>
          <aside class="panel guide">
            <span class="eyebrow">FLOW</span>
            <h3>{{ t("使用前完成三步", "Three steps before use") }}</h3>
            <ol>
              <li>
                <b>{{ t("选择协议", "Choose protocol") }}</b
                ><span>{{
                  t(
                    "兼容 OpenAI、Anthropic、Gemini 等主流接口。",
                    "Use OpenAI, Anthropic, Gemini, or a compatible endpoint.",
                  )
                }}</span>
              </li>
              <li>
                <b>{{ t("测试连接", "Test connection") }}</b
                ><span>{{
                  t(
                    "确认 Endpoint、Key 和模型可以正常响应。",
                    "Verify endpoint, key, and model response.",
                  )
                }}</span>
              </li>
              <li>
                <b>{{ t("保存启用", "Save and activate") }}</b
                ><span>{{
                  t(
                    "只有启用 Provider 后，研究接口才会开放。",
                    "Research endpoints unlock only after activation.",
                  )
                }}</span>
              </li>
            </ol>
          </aside>
        </div>
        <div v-if="providers.length" class="panel saved-list">
          <h3>{{ t("已保存的 Provider", "Saved providers") }}</h3>
          <div
            v-for="provider in providers"
            :key="provider.id"
            class="saved-row"
          >
            <div>
              <strong>{{ provider.name }}</strong
              ><small>{{ provider.model }} · {{ provider.endpoint }} · {{ t("推理", "Reasoning") }}: {{ provider.reasoning_effort }}</small>
            </div>
            <div class="saved-actions">
              <span v-if="provider.active" class="active-label">
                {{ t("当前使用", "Active") }}
              </span>
              <button
                v-else
                class="secondary-btn"
                @click="activateProvider(provider)"
              >
                {{ t("启用", "Activate") }}
              </button>
              <button class="secondary-btn" @click="editProvider(provider)">
                {{ t("编辑", "Edit") }}
              </button>
              <button class="danger-btn" @click="deleteProvider(provider)">
                {{ t("删除", "Delete") }}
              </button>
            </div>
          </div>
        </div>
      </section>
      <section v-else class="content chat-content">
        <div class="page-heading chat-page-heading">
          <div>
            <span class="eyebrow">RESEARCH ASSISTANT</span>
            <h1>{{ t("今天研究什么？", "What will you research today?") }}</h1>
          </div>
        </div>
        <div ref="messageList" class="messages">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['message', message.role]"
          >
            <span class="message-role">{{
              message.role === "user" ? t("你", "You") : "AI"
            }}</span>
            <div v-html="markdownToHtml(message.content)"></div>
          </div>
        </div>
        <div
          class="composer-wrap"
          :class="{
            dragging: attachmentDragging,
            'has-text': composerHasText,
            expanded: composerExpanded,
          }"
          @dragover.prevent="attachmentDragging = true"
          @dragleave.prevent="attachmentDragging = false"
          @drop.prevent="onAttachmentDrop"
        >
          <div v-if="attachments.length" class="attachment-list">
            <div
              v-for="attachment in attachments"
              :key="attachment.id"
              class="attachment-chip"
            >
              <span class="attachment-icon">{{
                attachment.is_image ? "▧" : "▤"
              }}</span
              ><span class="attachment-name" :title="attachment.filename">{{
                attachment.filename
              }}</span
              ><button
                type="button"
                class="remove-attachment"
                :aria-label="t('移除附件', 'Remove attachment')"
                @click="removeAttachment(attachment)"
              >
                ×
              </button>
            </div>
          </div>
          <div v-if="composerSettingsOpen" class="chat-settings-popover" aria-label="Chat model settings">
            <label class="chat-control">
              <span>{{ t("模型", "Model") }}</span>
              <select v-model="selectedModel" :disabled="loading || !chatModelOptions.length">
                <option v-for="model in chatModelOptions" :key="model" :value="model">
                  {{ model }}
                </option>
              </select>
            </label>
            <label class="chat-control">
              <span>{{ t("推理等级", "Reasoning") }}</span>
              <select v-model="selectedReasoning" :disabled="loading">
                <option value="auto">{{ t("自动", "Auto") }}</option>
                <option value="low">{{ t("低", "Low") }}</option>
                <option value="medium">{{ t("中", "Medium") }}</option>
                <option value="high">{{ t("高", "High") }}</option>
                <option value="xhigh">{{ t("极高", "X-High") }}</option>
              </select>
            </label>
          </div>
          <form class="composer" @submit.prevent="sendQuery()">
            <input
              ref="attachmentInput"
              class="visually-hidden"
              type="file"
              multiple
              accept=".txt,.md,.csv,.tsv,.json,.yaml,.yml,.xml,.html,.htm,.py,.js,.ts,.vue,.java,.go,.c,.cpp,.h,.sql,.log,.ini,.toml,.rst,.pdf,.docx,.xlsx,image/png,image/jpeg,image/webp,image/gif"
              @change="onAttachmentInput"
            /><textarea
              ref="composerTextarea"
              v-model="query"
              :disabled="loading"
              :placeholder="
                attachments.length
                  ? t(
                      '补充问题，或直接发送附件',
                      'Add a question, or send the attachments',
                    )
                  : t(
                      '描述目标、背景和期望输出，按 Enter 发送',
                      'Describe your goal, context, and desired output. Press Enter to send',
                    )
              "
              @input="resizeComposer"
              @keydown.enter.exact.prevent="sendQuery()"
            ></textarea>
            <div class="composer-toolbar">
              <button
                type="button"
                class="attach-btn icon-btn"
              :disabled="loading || attachmentLoading"
              :title="t('添加文件或图片', 'Add files or images')"
              @click="attachmentInput?.click()"
            >
              ＋</button>
              <span class="composer-spacer"></span>
              <button
                type="button"
                class="model-summary-btn"
                :class="{ active: composerSettingsOpen }"
                :aria-expanded="composerSettingsOpen"
                :disabled="loading || !activeProvider"
                :title="t('模型与推理设置', 'Model and reasoning settings')"
                @click="composerSettingsOpen = !composerSettingsOpen"
              >
                <span class="model-summary-name">{{ selectedModel || t("模型", "Model") }}</span>
                <span class="model-summary-separator" aria-hidden="true">·</span>
                <span class="model-summary-reasoning">{{ reasoningLabel(selectedReasoning) }}</span>
                <span class="model-summary-chevron" aria-hidden="true">⌄</span>
              </button>
              <div
                class="voice-panel"
                :class="[`voice-${voiceState}`, { unavailable: !voiceSupported }]"
              >
                <div class="voice-orb-control">
                  <span class="voice-orb-fallback" aria-hidden="true"></span>
                  <iframe
                    class="voice-orb-frame"
                    src="/voice-orb.html"
                    title=""
                    tabindex="-1"
                    aria-hidden="true"
                  ></iframe>
                  <span class="voice-orb-ring voice-orb-ring-one"></span>
                  <span class="voice-orb-ring voice-orb-ring-two"></span>
                  <button
                    type="button"
                    class="voice-orb"
                    :disabled="loading && voiceState !== 'speaking'"
                    :aria-label="voiceLabel()"
                    :title="voiceHint()"
                    @click="toggleVoice"
                  ></button>
                </div>
              </div>
              <button
                class="send-btn icon-btn"
                :disabled="
                  loading ||
                  attachmentLoading ||
                  (!query.trim() && !attachments.length)
                "
                :title="loading ? t('研究中...', 'Researching...') : t('发送', 'Send')"
                :aria-label="t('发送', 'Send')"
              >↑</button>
            </div>
          </form>
        </div>
        <p v-if="notice" class="notice">{{ notice }}</p>
        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
      </section>
    </main>
  </div>
</template>
