<template>
  <span v-if="DEMO_MODE" class="demo-chip" :title="hint">
    <span class="demo-dot" />
    <span class="demo-chip-text">{{ title }}</span>
    <button class="demo-reset" type="button" :title="hint" @click="resetDemo">
      {{ resetLabel }}
    </button>
  </span>
</template>

<script setup lang="ts">
import { computed } from "vue";

import { DEMO_MODE, resetDemo } from "./index";

const props = defineProps<{ locale: "zh" | "en" }>();

const isZh = computed(() => props.locale === "zh");

const title = computed(() => (isZh.value ? "演示模式" : "Demo mode"));

const hint = computed(() =>
  isZh.value
    ? "数据由浏览器本地生成，不会调用真实模型或检索服务"
    : "Data is generated locally in your browser. No real model or search service is called.",
);

const resetLabel = computed(() => (isZh.value ? "重置" : "Reset"));
</script>

<style scoped>
/*
 * 顶栏内联的演示标记，而不是固定在角落的浮层。
 * 固定浮层会遮挡内容：这个应用把输入区和侧栏都铺到视口底部，
 * 底部浮层必然压住可交互元素。顶栏在登录页与工作台都会渲染，
 * 因此放在这里既能被看到，又不占用任何内容空间。
 */
.demo-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 6px 6px 10px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
}
.demo-dot {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #f5a524;
}
.demo-chip-text {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.demo-reset {
  padding: 4px 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: transparent;
  color: var(--muted);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
}
.demo-reset:hover {
  color: var(--text);
}
/* 窄屏只保留状态点与短标签，避免把顶栏挤爆。 */
@media (max-width: 860px) {
  .demo-chip-text,
  .demo-reset {
    display: none;
  }
  .demo-chip {
    padding: 6px;
  }
}
</style>
