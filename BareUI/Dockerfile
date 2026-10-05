# --- Stage 1: Build ---
FROM node:20-alpine AS builder

WORKDIR /app

ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

# Build Svelte + Vite app
RUN npm run build


# --- Stage 2: Production ---
FROM nginx:alpine AS runner

# Remove default nginx files
RUN rm -rf /usr/share/nginx/html/*

# Copy Vite production build
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
