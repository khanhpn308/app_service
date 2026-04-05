FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Small EC2 (1 GiB RAM): cap heap to reduce swap thrashing; use 2048+ on t3.small or build off-server
ENV NODE_OPTIONS="--max-old-space-size=1024"
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/prod.conf /etc/nginx/conf.d/default.conf
EXPOSE 80 443
CMD ["nginx", "-g", "daemon off;"]

