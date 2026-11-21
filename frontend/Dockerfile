# syntax=docker/dockerfile:1
FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts          # lockfile-exact install, no install scripts (A08)
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

# Unprivileged nginx: runs as a non-root user on port 8080 (A05)
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
