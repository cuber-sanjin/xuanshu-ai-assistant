# ===== 玄枢前端镜像（多阶段构建） =====
# 阶段 1 (build)：node 镜像里装依赖 + 构建静态文件
# 阶段 2 (runtime)：nginx 托管静态文件 + 反代 /api 到后端
# 多阶段好处：最终镜像只有 nginx + 静态文件（~50MB），不含 node/npm

# ---------- 阶段 1：构建 ----------
FROM node:22-alpine AS build

WORKDIR /app

# 先装依赖（package-lock 存在时用 npm ci，锁定版本、更快更可复现）
COPY package.json package-lock.json ./
RUN npm ci

# 再拷贝源码并构建（vue-tsc 类型检查 + vite 打包）
COPY . .
RUN npm run build

# ---------- 阶段 2：运行 ----------
FROM nginx:alpine

# 静态产物 → nginx 站点根目录
COPY --from=build /app/dist /usr/share/nginx/html

# 自定义 nginx 配置：SPA 回退 + /api 反代 + SSE 关缓冲
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
