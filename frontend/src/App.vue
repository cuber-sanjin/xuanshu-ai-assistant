<script setup lang="ts">
// 根组件：挂载主页 + 全局 Toast 宿主
import Home from './views/Home.vue'
import ToastHost from './components/ToastHost.vue'
</script>

<template>
  <Home />
  <ToastHost />
</template>
