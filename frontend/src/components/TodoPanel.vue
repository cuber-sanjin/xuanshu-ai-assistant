<script setup lang="ts">
// 待办面板：列表 + 新增 + 完成切换 + 删除
// 与聊天工具（todo_tool）共用同一组后端接口，但这里是直接 UI 操作

import { onMounted, ref, watch } from 'vue'
import { createTodo, deleteTodo, getTodos, updateTodo, type Todo } from '../services/api'
import { useRefreshVersion } from '../composables/useDataRefresh'
import { useToast } from '../composables/useToast'

const todos = ref<Todo[]>([])
const newTitle = ref('')
const loading = ref(false)

const { success: toastSuccess, error: toastError } = useToast()

// 数据刷新总线：Agent 通过 create_todo 等工具改数据时自动重载
const refreshVersion = useRefreshVersion('todo')
watch(refreshVersion, () => load())

// 加载列表
async function load() {
  loading.value = true
  try {
    todos.value = await getTodos()
  } catch (err) {
    console.error('load todos failed:', err)
  } finally {
    loading.value = false
  }
}

// 新增
async function add() {
  const title = newTitle.value.trim()
  if (!title) return
  try {
    await createTodo(title)
    newTitle.value = ''
    await load()
  } catch (err) {
    console.error('create todo failed:', err)
  }
}

// 完成切换
async function toggle(todo: Todo) {
  try {
    await updateTodo(todo.id, !todo.completed)
    await load()
  } catch (err) {
    console.error('update todo failed:', err)
  }
}

// 删除
async function remove(todo: Todo) {
  try {
    await deleteTodo(todo.id)
    await load()
    toastSuccess(`已删除待办「${todo.title}」`)
  } catch (err) {
    console.error('delete todo failed:', err)
    toastError('删除待办失败，请重试')
  }
}

onMounted(load)
</script>

<template>
  <aside class="todo-panel">
    <h3 class="panel-title">待办清单</h3>

    <!-- 新增输入 -->
    <div class="add-row">
      <input
        v-model="newTitle"
        class="add-input"
        type="text"
        placeholder="添加待办…"
        @keydown.enter="add"
      />
      <button class="add-btn" :disabled="!newTitle.trim()" @click="add">＋</button>
    </div>

    <!-- 列表 -->
    <ul v-if="todos.length > 0" class="todo-list">
      <li v-for="t in todos" :key="t.id" class="todo-item" :class="{ done: t.completed }">
        <label class="todo-check" @click="toggle(t)">
          <input type="checkbox" :checked="t.completed" @change="toggle(t)" />
          <span class="checkmark"></span>
        </label>
        <div class="todo-body">
          <span class="todo-title">{{ t.title }}</span>
          <span v-if="t.due_time" class="todo-due">{{ t.due_time }}</span>
        </div>
        <button class="del-btn" @click="remove(t)" title="删除">✕</button>
      </li>
    </ul>

    <p v-else class="empty-tip">{{ loading ? '加载中…' : '暂无待办' }}</p>
  </aside>
</template>

<style scoped>
.todo-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: rgba(13, 27, 48, 0.4);
  overflow-y: auto;
}
.panel-title {
  font-size: 14px;
  letter-spacing: 2px;
  color: #7dd3fc;
  margin: 0;
}
.add-row {
  display: flex;
  gap: 8px;
}
.add-input {
  flex: 1;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(148, 197, 255, 0.2);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e2ecff;
  font-size: 13px;
  outline: none;
}
.add-input:focus {
  border-color: #22d3ee;
}
.add-btn {
  width: 34px;
  background: linear-gradient(135deg, #0ea5e9, #22d3ee);
  border: none;
  border-radius: 8px;
  color: #062b3a;
  font-size: 16px;
  cursor: pointer;
}
.add-btn:disabled {
  opacity: 0.4;
}
.todo-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 0;
}
.todo-item {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(148, 197, 255, 0.12);
  border-radius: 8px;
  padding: 8px 10px;
}
.todo-item.done .todo-title {
  text-decoration: line-through;
  opacity: 0.5;
}
.todo-check {
  cursor: pointer;
  display: flex;
}
.todo-check input {
  display: none;
}
.checkmark {
  width: 16px;
  height: 16px;
  border: 1px solid #5a7a9a;
  border-radius: 4px;
  display: inline-block;
}
.todo-item.done .checkmark {
  background: #22d3ee;
  border-color: #22d3ee;
}
.todo-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.todo-title {
  font-size: 13px;
}
.todo-due {
  font-size: 11px;
  color: #5a7a9a;
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
.empty-tip {
  color: #5a7a9a;
  font-size: 13px;
  text-align: center;
  padding: 20px 0;
}
</style>
