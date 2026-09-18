// 演示模式的内容：预置数据、研究链路轨迹与报告生成。
//
// 这里的所有文本都在浏览器本地生成，不会调用任何模型或检索服务。
// 报告末尾会明确标注这一点，避免观众把演示内容误当成真实检索结果。

import type { Conversation, ConversationRecord, Provider, User } from "./types";

/** 演示账号：登录页会预填，演示模式下任意非空账号均可登录。 */
export const DEMO_ACCOUNT = {
  email: "demo@deepresearch.ai",
  password: "demo1234",
  display_name: "演示研究员",
};

export const SEED_USER: User = {
  id: 1,
  email: DEMO_ACCOUNT.email,
  display_name: DEMO_ACCOUNT.display_name,
  avatar_data: "",
};

/** 预置一个已启用的 Provider：没有 active 的 Provider，应用会停在配置页。 */
export const SEED_PROVIDER: Provider = {
  id: 1,
  name: "演示 · DeepSeek",
  provider_type: "deepseek",
  protocol: "openai_chat",
  endpoint: "https://api.deepseek.com/v1",
  model: "deepseek-chat",
  api_version: null,
  reasoning_effort: "auto",
  available_models: ["deepseek-chat", "deepseek-reasoner"],
  active: true,
};

/** 新建 Provider 时可选的模型，避免「获取模型」按钮在演示里毫无反应。 */
export const MODEL_CATALOG: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  dashscope: ["qwen-max", "qwen-plus", "qwen-turbo"],
  anthropic: ["claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
  gemini: ["gemini-2.0-flash", "gemini-2.0-pro"],
  custom: ["demo-model-chat", "demo-model-reasoner"],
};

// ---------------------------------------------------------------------------
// 预置对话
// ---------------------------------------------------------------------------

type SeedConversation = {
  thread_id: string;
  title: string;
  updated_at: string;
  history: Array<{ role: "user" | "assistant"; content: string }>;
};

const REFERENCE_NOTE =
  "> 演示模式：以下内容由浏览器本地生成，未调用任何模型或检索服务。";

export const SEED_CONVERSATIONS: SeedConversation[] = [
  {
    thread_id: "thread-1-1755518400000-a1b2c3",
    title: "多智能体检索链路的设计取舍",
    updated_at: "2026-08-19T09:20:00.000Z",
    history: [
      {
        role: "user",
        content: "多智能体检索链路里，为什么要在检索之后单独加一个「证据判断」节点？",
      },
      {
        role: "assistant",
        content: [
          "## 结论速览",
          "",
          "**证据判断节点解决的是「检索到」与「可用」之间的落差。** 检索节点只负责召回，它无法判断一条材料是否真的回答了子问题、是否存在时间或口径上的冲突。把判断独立成节点后，后续的分析与写作都只消费被标记过的证据，引用可追溯，也更容易定位质量问题。",
          "",
          "## 关键发现",
          "",
          "- **职责分离**：检索节点的优化目标是召回率，判断节点的优化目标是准确率，两个目标混在一起会互相牵制。",
          "- **可追溯性**：证据被赋予来源编号后，写作阶段的引用可以逐条回溯到原文，而不是笼统地“根据资料”。",
          "- **可调试性**：链路出错时能快速区分是“没搜到”还是“搜到了但判错了”，两者的修复手段完全不同。",
          "- **成本控制**：判断节点只处理候选集，不需要重新调用检索，通常比“多搜几轮”更省。",
          "",
          "## 证据与分歧",
          "",
          "在工程实践中存在两种路线：一种把判断与检索合并为一次模型调用，另一种严格拆开。前者延迟更低，后者在长链路里更稳定——当后续还有反思与重写环节时，显式拆开更容易控制上下文长度。",
          "",
          "## 局限与待验证",
          "",
          "- 判断节点的准确率高度依赖提示词与候选质量，候选本身偏差大时，判断只能止损，不能纠偏。",
          "- 若判断节点使用与写作节点相同的模型，两者的错误可能同源，需要额外的交叉校验。",
          "",
          REFERENCE_NOTE,
        ].join("\n"),
      },
    ],
  },
  {
    thread_id: "thread-1-1755259200000-d4e5f6",
    title: "RAG 召回率优化方案对比",
    updated_at: "2026-08-17T14:05:00.000Z",
    history: [
      {
        role: "user",
        content: "RAG 的召回效果不理想，应该先调哪些环节？按收益排序给个排查顺序。",
      },
      {
        role: "assistant",
        content: [
          "## 结论速览",
          "",
          "**先查切分，再查查询改写，最后才动向量模型。** 多数召回问题来自文档切分把语义切断了，而不是嵌入模型不够强。",
          "",
          "## 排查顺序（按投入产出比）",
          "",
          "1. **切分策略**：检查块长度与重叠是否合理，标题层级是否被保留。语义被切断时，再强的嵌入也救不回来。",
          "2. **查询改写**：用户问句往往缺少上下文，先用一次改写把口语化问题转成检索友好的表述，收益通常立竿见影。",
          "3. **混合检索**：关键词与向量各有所长，对术语、编号、专有名词密集的场景，加一路关键词检索能显著补召回。",
          "4. **重排序**：把候选集扩大后再精排，比直接提高向量模型的维度更划算。",
          "5. **嵌入模型**：以上都做完仍不达标，再考虑换模型或做领域微调。",
          "",
          "## 关键指标",
          "",
          "- 先看**召回率**，再看**排序质量**，最后才看**生成质量**，顺序颠倒会得出错误结论。",
          "- 建议固定一批标注问题做回归集，否则每次调整都无法判断是否真的变好。",
          "",
          "## 局限与待验证",
          "",
          "- 混合检索会引入权重调参成本，权重选择依赖具体语料，没有通用最优值。",
          "",
          REFERENCE_NOTE,
        ].join("\n"),
      },
    ],
  },
  {
    thread_id: "thread-1-1755086400000-g7h8i9",
    title: "向量数据库选型：Milvus 与 pgvector",
    updated_at: "2026-08-15T11:40:00.000Z",
    history: [
      {
        role: "user",
        content: "中小规模的知识库项目，选 Milvus 还是 pgvector？",
      },
      {
        role: "assistant",
        content: [
          "## 结论速览",
          "",
          "**数据量在千万级向量以下、且团队已经在用 PostgreSQL 时，pgvector 通常是更省心的选择。** 它把向量和业务数据放在同一个事务里，省掉了一致性同步的复杂度。",
          "",
          "## 对比维度",
          "",
          "- **运维成本**：pgvector 复用现有数据库；Milvus 是独立集群，需要额外的部署与监控投入。",
          "- **一致性**：pgvector 可与业务表同事务写入；Milvus 需要处理向量库与业务库之间的最终一致。",
          "- **规模上限**：Milvus 为十亿级向量与高并发检索设计，索引类型与分片策略更丰富。",
          "- **功能完整度**：Milvus 原生支持多种索引与标量过滤的组合优化，pgvector 的能力边界更窄。",
          "",
          "## 判断依据",
          "",
          "分界线不在于“哪个更强”，而在于**数据规模的增长速度**与**是否愿意引入新的有状态服务**。如果向量规模两年内预计增长十倍以上，早期就选 Milvus 反而能避免中途迁移。",
          "",
          "## 局限与待验证",
          "",
          "- 两者的性能差异与实际索引参数、数据分布强相关，需要用真实语料压测，不能只看公开跑分。",
          "",
          REFERENCE_NOTE,
        ].join("\n"),
      },
    ],
  },
];

/** 把预置对话转成「列表项 + 历史记录」两份数据。 */
export function seedConversations(): {
  conversations: Conversation[];
  histories: Record<string, ConversationRecord[]>;
} {
  const conversations: Conversation[] = [];
  const histories: Record<string, ConversationRecord[]> = {};
  let recordId = 1;

  for (const seed of SEED_CONVERSATIONS) {
    conversations.push({
      thread_id: seed.thread_id,
      title: seed.title,
      updated_at: seed.updated_at,
    });
    histories[seed.thread_id] = seed.history.map((item) => ({
      id: recordId++,
      role: item.role,
      content: item.content,
      created_at: seed.updated_at,
    }));
  }

  return { conversations, histories };
}

// ---------------------------------------------------------------------------
// 研究链路轨迹
// ---------------------------------------------------------------------------

/**
 * 生成一次研究过程的阶段轨迹。
 * 节点名称与真实后端的链路保持一致，便于观众理解产品实际做了什么。
 */
export function buildTrace(query: string, attachmentCount: number): string[] {
  const short = query.length > 18 ? `${query.slice(0, 18)}…` : query;
  const trace = [
    "正在识别意图与回答形态…",
    "已走多智能体研究路径",
    `任务规划：围绕「${short}」拆解子问题`,
    "网络检索：正在收集公开资料…",
  ];
  if (attachmentCount > 0) {
    trace.push(`本地资料检索：正在读取 ${attachmentCount} 个附件…`);
  } else {
    trace.push("本地资料检索：本轮没有附件，跳过本地召回");
  }
  trace.push(
    "证据判断：正在校验来源相关性与时效…",
    "分析：正在比对不同来源的口径差异…",
    "反思：判断是否需要补充检索…",
    "报告生成：正在组织结论与引用…",
  );
  return trace;
}

// ---------------------------------------------------------------------------
// 报告生成
// ---------------------------------------------------------------------------

type TopicProfile = {
  angles: string[];
  considerations: string[];
  limitations: string[];
};

const TOPIC_PROFILES: Array<{ match: RegExp; profile: TopicProfile }> = [
  {
    match: /(rag|向量|检索|embedding|召回|模型|大模型|agent|智能体|ai)/i,
    profile: {
      angles: [
        "技术路线的差异大多体现在**运维复杂度**与**一致性保证**上，而不是理论能力上限",
        "**评测集**是这类项目最容易缺失的一环：没有回归集，任何优化都只是凭感觉",
        "成本与延迟往往是隐性约束，它们会反过来决定架构能走多远",
      ],
      considerations: [
        "公开跑分与实际语料表现差距明显，必须用自有数据验证",
      ],
      limitations: [
        "缺少真实规模下的压测数据，当前结论只在中小规模成立",
        "未覆盖多租户与权限隔离场景，企业落地的约束可能改变结论",
      ],
    },
  },
  {
    match: /(市场|行业|商业|营收|增长|竞争|战略|business|market)/i,
    profile: {
      angles: [
        "**规模与增速**决定了竞争格局：增量市场拼速度，存量市场拼效率",
        "渠道结构与客户结构的变化，通常比总量数字更早反映趋势",
        "政策与合规是这类问题的硬约束，不是可选项",
      ],
      considerations: [
        "不同口径下的统计差异较大，横向比较前需先对齐定义",
      ],
      limitations: [
        "缺少一手调研数据，结论主要基于公开信息的交叉验证",
        "短期波动与长期趋势需要分开判断，当前样本跨度不足以区分",
      ],
    },
  },
  {
    match: /(架构|性能|并发|数据库|分布式|系统|后端|部署|运维)/i,
    profile: {
      angles: [
        "**瓶颈定位**要先于方案选择：不明确瓶颈时，任何优化都是猜测",
        "一致性与可用性的取舍必须显式写下来，否则会在实现阶段反复摇摆",
        "可观测性决定了问题能否被发现，它应该和功能一起交付",
      ],
      considerations: [
        "压测环境与生产环境的差异常常掩盖真实瓶颈",
      ],
      limitations: [
        "缺少生产环境的长周期观测数据，容量规划结论需谨慎使用",
        "未覆盖故障注入场景，容灾能力的评估尚不完整",
      ],
    },
  },
];

const DEFAULT_PROFILE: TopicProfile = {
  angles: [
    "**定义边界**是这类问题的第一步：口径不同，结论往往完全相反",
    "关键变量之间存在相互制约，单独优化某一项通常会带来副作用",
    "**可验证性**决定了结论的可信度，缺少数据的判断应当明确标注",
  ],
  considerations: [
    "不同来源的口径与时间范围存在差异，直接横向比较容易失真",
  ],
  limitations: [
    "公开资料覆盖不完整，部分结论依赖推断",
    "缺少一手数据验证，建议在决策前补充实证",
  ],
};

function pickProfile(query: string): TopicProfile {
  for (const item of TOPIC_PROFILES) {
    if (item.match.test(query)) return item.profile;
  }
  return DEFAULT_PROFILE;
}

/**
 * 生成一份与提问相关的研究报告（Markdown）。
 * markdownToHtml 支持标题、列表、引用、粗体与链接，因此这里只使用这些语法。
 */
export function buildReport(query: string, attachmentCount: number): string {
  const topic = query.trim() || "本次研究主题";
  const profile = pickProfile(topic);
  const shortTopic = topic.length > 26 ? `${topic.slice(0, 26)}…` : topic;

  const lines: string[] = [
    "## 结论速览",
    "",
    `围绕「${shortTopic}」，本次链路完成了意图识别、任务规划、双路检索、证据判断与报告生成。` +
      `综合可用信息，**建议先明确判断口径，再选定方案，最后用自有数据做回归验证**——顺序颠倒会让后续所有比较失去基准。`,
    "",
    "## 关键发现",
    "",
    ...profile.angles.map((angle) => `- ${angle}`),
    "",
    "## 证据与分歧",
    "",
    `检索到的材料在整体方向上一致，但在**适用范围**上存在分歧：` +
      `一部分材料给出的结论建立在特定前提之下，另一部分则把前提当作通用条件。` +
      `因此 ${profile.considerations.join("；")}。`,
    "",
  ];

  if (attachmentCount > 0) {
    lines.push(
      "## 本地资料核对",
      "",
      `本轮结合了 ${attachmentCount} 个附件进行交叉核对，附件内容与公开材料的结论没有直接冲突，` +
        "但附件覆盖的时间范围更窄，可作为近期情况的佐证。",
      "",
    );
  }

  lines.push(
    "## 局限与待验证",
    "",
    ...profile.limitations.map((item) => `- ${item}`),
    "",
    "## 建议的下一步",
    "",
    "1. 明确本次决策的判断口径与成功标准，写下来再讨论方案",
    "2. 用自有数据构造一个小规模回归集，作为后续优化的统一基准",
    "3. 对关键假设做一次反向验证：如果假设不成立，结论会如何变化",
    "",
    REFERENCE_NOTE,
  );

  return lines.join("\n");
}
