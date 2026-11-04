# Frontend: build do Vite (Node) servido por nginx sem privilégios de root.
# Contexto de build: frontend/.

FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# URL pública pela qual o navegador acessa o site; o nginx encaminha /api ao backend (mesma origem, sem CORS).
# Vazio = modo demonstrativo (respostas fictícias, sem backend).
ARG VITE_API_BASE_URL=http://localhost:8080
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine
# Endereço interno do backend; o template é processado por envsubst na inicialização do nginx.
ENV BACKEND_URL=http://backend:8000
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
