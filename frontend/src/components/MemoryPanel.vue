<script setup lang="ts">
// 长期记忆面板：展示玄枢记住的关于用户的信息
// 记忆由对话自动提取（save_memory 节点）或用户说"记住…"产生

import { onMounted, ref, watch } from 'vue'
import { deleteMemory, getMemories, type Memory } from '../services/api'
import { useRefreshVersion } from '../composables/useDataRefresh'
import { useToast } from '../composables/useToast'

const memories = ref<Memory[]>([])
const loading = ref(false)

const { success: toastSuccess, error: toastError } = useToast()

// 数据刷新总线：对话自动提取 / remember 工具保存记忆后自动重载
const refreshVersion = useRefreshVersion('memory')
watch(refreshVersion, () => load())

// 记忆类型中文映射
const TYPE_LABELS: Record<string, string> = {
  preference: '偏好',
  profile: '资料',
  goal: '目标',
  learning: '学习',
  habit: '习惯',
  important_event: '重要事件',
}

async function load() {
  loading.value = true
  try {
    memories.value = await getMemories()
  } catch (err) {
    console.error('load memories failed:', err)
  } finally {
    loading.value = false
  }
}

async function remove(mem: Memory) {
  try {
    await deleteMemory(mem.id)
    await load()
    toastSuccess('已删除一条记忆')
  } catch (err) {
    console.error('delete memory failed:', err)
    toastError('删除记忆失败，请重试')
  }
}

onMounted(load)
</script>

<template>
  <aside class="memory-panel">
    <h3 class="panel-title">长久记忆</h3>

    <ul v-if="memories.length > 0" class="memory-list">
      <li v-for="m in memories" :key="m.id" class="memory-item">
        <div class="memory-head">
          <span class="tag">{{ TYPE_LABELS[m.memory_type] ?? m.memory_type }}</span>
          <button class="del-btn" @click="remove(m)" title="忘记这条">✕</button>
        </div>
        <p class="memory-content">{{ m.content }}</p>
      </li>
    </ul>

    <p v-else class="empty-tip">{{ loading ? '加载中…' : '玄枢还没有记住关于你的信息' }}</p>
  </aside>
</template>

<style scoped>
.memory-panel {
  border-top: 1px solid rgba(148, 197, 255, 0.12);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  max-height: 45%;
}
.panel-title {
  font-size: 14px;
  letter-spacing: 2px;
  color: #7dd3fc;
  margin: 0;
}
.memory-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
}
.memory-item {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 197, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
}
.memory-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.tag {
  font-size: 11px;
  color: #22d3ee;
  border: 1px solid rgba(34, 211, 238, 0.4);
  border-radius: 4px;
  padding: 1px 6px;
}
.del-btn {
  background: none;
  border: none;
  color: #5a7a9a;
  cursor: pointer;
  font-size: 12px;
}
.del-btn:hover {
  color: #f87171;
}
.memory-content {
  font-size: 12px;
  color: #cfe0ff;
  line-height: 1.5;
  margin: 0;
}
.empty-tip {
  color: #5a7a9a;
  font-size: 12px;
  text-align: center;
  padding: 12px 0;
}
</style>
