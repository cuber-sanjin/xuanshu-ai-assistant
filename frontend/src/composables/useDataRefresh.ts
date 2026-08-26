// 数据刷新总线：让聊天事件驱动面板数据重新加载
//
// 问题：TodoPanel/MemoryPanel 只在挂载时加载一次，Agent 在对话中
// 创建/完成待办、保存记忆后，面板数据是陈旧的（需手动刷新页面）。
//
// 方案：模块级版本号 + bump(scope)。useChat 在 tool_end/done 事件时
// 按工具名精准 bump 对应 scope；面板 watch 自己关心的 scope，变化即重载。
// 不引入事件总线依赖（mitt），零依赖、类型安全。

import { computed, ref } from 'vue'

export type RefreshScope = 'todo' | 'memory' | 'conversation' | 'all'

// scope → 版本号（值越大越新）
const versions = ref<Record<RefreshScope, number>>({
  todo: 0,
  memory: 0,
  conversation: 0,
  all: 0,
})

/** 通知某个数据域需要刷新（面板 watch 后自动重载） */
export function bump(scope: RefreshScope) {
  versions.value[scope]++
}

/** 面板监听：返回该 scope 的版本号 computed（可 watch），变化即重载 */
export function useRefreshVersion(scope: RefreshScope) {
  return computed(() => versions.value[scope])
}

/** 工具名 → 数据域映射（tool_end 事件用） */
const TOOL_SCOPE: Record<string, RefreshScope> = {
  create_todo: 'todo',
  complete_todo: 'todo',
  delete_todo: 'todo',
  remember: 'memory',
  recall_memory: 'memory',
  forget_memory: 'memory',
}

/** 根据工具名触发对应数据域刷新 */
export function bumpByTool(toolName: string | undefined) {
  const scope = toolName ? TOOL_SCOPE[toolName] : undefined
  if (scope) bump(scope)
}
