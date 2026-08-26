// Markdown 渲染工具：统一出口
// 为什么必须消毒（DOMPurify）？
//   LLM 输出不可信——若用户让模型"复述我发的内容"，恶意输入（<img onerror>、
//   <script>）会被原样回显。v-html 直接渲染 = XSS 漏洞。
//   DOMPurify 只保留安全标签/属性，是 AI 前端渲染模型输出的安全底线。
//
// 代码块语法高亮（highlight.js）：
//   - 用 marked 自定义 renderer 拦截 code 块，hljs 着色后返回 HTML
//   - 语言未知时用 highlightAuto 自动检测；失败退回纯文本
//   - DOMPurify 默认允许 span/class，高亮输出的样式类可安全通过

import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/common' // 常用语言子集（~几十种，控制体积）
import { marked } from 'marked'

// marked 配置：开 GFM（表格/删除线等），保持默认安全选项
marked.setOptions({ gfm: true, breaks: true })

// 自定义代码块渲染：marked 解析到 code 时走这里做语法高亮
marked.use({
  renderer: {
    code({ text, lang }) {
      // 处理行内代码（无语言/未换行）→ 原样输出（CSS 已有行内样式）
      if (!lang && !text.includes('\n')) {
        return `<code>${text}</code>`
      }
      try {
        const langLower = (lang || '').toLowerCase()
        const highlighted = langLower
          ? hljs.getLanguage(langLower)
            ? hljs.highlight(text, { language: langLower }).value
            : hljs.highlightAuto(text).value
          : hljs.highlightAuto(text).value
        // language-xxx class 供主题 CSS 生效；非高亮内容保留原文本
        return `<pre><code class="hljs language-${langLower || 'plaintext'}">${highlighted}</code></pre>`
      } catch {
        // 高亮失败（极端情况）退回原样输出
        return `<pre><code>${text}</code></pre>`
      }
    },
  },
})

/**
 * 把 Markdown 文本渲染为安全的 HTML 字符串。
 * 所有 assistant 消息渲染必须走这里，禁止直接 v-html 原始内容。
 */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  const rawHtml = marked.parse(text) as string
  return DOMPurify.sanitize(rawHtml)
}
