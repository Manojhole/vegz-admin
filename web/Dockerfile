FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ARG NEXT_PUBLIC_VEGZ_ADMIN_API_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_VEGZ_ADMIN_API_URL=$NEXT_PUBLIC_VEGZ_ADMIN_API_URL
RUN npm run build
FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY --from=build /app/src ./src
COPY --from=build /app/next.config.ts ./next.config.ts
EXPOSE 3000
CMD ["npm","run","start"]
