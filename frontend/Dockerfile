# Builder stage
FROM node:18-alpine AS builder

WORKDIR /app

# Копируем файлы package.json и lock файл  
COPY package.json ./
COPY package-lock.json ./

# Устанавливаем зависимости
RUN npm ci --prefer-offline --no-audit

# Копируем исходный код
COPY . .

# Выполняем сборку
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Создаем пользователя для безопасности
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Копируем package.json для зависимостей
COPY --from=builder /app/package.json ./

# Копируем standalone сборку
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Копируем static файлы в правильную директорию
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Копируем public директорию
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

EXPOSE 3000

# Запускаем сервер
CMD ["node", "server.js"]
