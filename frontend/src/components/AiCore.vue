<script setup lang="ts">
// AI 核心：圆形渐变球体 + 双层辉光呼吸动画
// active=true（思考中）时加速并增强辉光，传达"玄枢在工作"的状态
// 注意：球体内的「玄」字不旋转，旋转的是外层虚线环

withDefaults(defineProps<{ size?: number; active?: boolean }>(), {
  size: 48,
  active: false,
})
</script>

<template>
  <div
    class="ai-core"
    :class="{ active }"
    :style="{ width: size + 'px', height: size + 'px' }"
  >
    <!-- 旋转虚线环 -->
    <span class="ring"></span>
    <!-- 外圈光晕（呼吸扩散） -->
    <span class="halo"></span>
    <!-- 渐变球体 -->
    <span class="sphere">玄</span>
  </div>
</template>

<style scoped>
.ai-core {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
/* 旋转虚线环：科技感轨道 */
.ring {
  position: absolute;
  inset: -10px;
  border-radius: 50%;
  border: 1px dashed rgba(34, 211, 238, 0.4);
  animation: ring-spin 12s linear infinite;
}
/* 外圈光晕：呼吸扩散 */
.halo {
  position: absolute;
  inset: -5px;
  border-radius: 50%;
  border: 1px solid rgba(34, 211, 238, 0.45);
  animation: halo-breathe 3s ease-in-out infinite;
}
/* 球体：青蓝渐变 + 内发光（静止，文字不旋转） */
.sphere {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: radial-gradient(circle at 32% 30%, #7dd3fc, #0ea5e9 55%, #063c63 100%);
  color: #062b3a;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  box-shadow:
    0 0 18px rgba(34, 211, 238, 0.55),
    inset 0 -6px 12px rgba(6, 60, 99, 0.6);
  animation: glow-breathe 3s ease-in-out infinite;
  user-select: none;
}
/* 思考中：加速 + 辉光增强 */
.ai-core.active .ring {
  animation-duration: 2s;
  border-color: rgba(34, 211, 238, 0.9);
}
.ai-core.active .halo {
  animation-duration: 1.2s;
  border-color: rgba(34, 211, 238, 0.9);
}
.ai-core.active .sphere {
  box-shadow:
    0 0 32px rgba(34, 211, 238, 0.95),
    inset 0 -6px 12px rgba(6, 60, 99, 0.6);
}

@keyframes ring-spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes halo-breathe {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.9;
  }
  50% {
    transform: scale(1.25);
    opacity: 0.35;
  }
}
@keyframes glow-breathe {
  0%,
  100% {
    box-shadow:
      0 0 14px rgba(34, 211, 238, 0.45),
      inset 0 -6px 12px rgba(6, 60, 99, 0.6);
  }
  50% {
    box-shadow:
      0 0 26px rgba(34, 211, 238, 0.8),
      inset 0 -6px 12px rgba(6, 60, 99, 0.6);
  }
}
</style>
