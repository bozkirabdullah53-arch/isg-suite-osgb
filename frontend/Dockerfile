FROM node:20.18.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --global npm@10.8.2 --no-audit --no-fund \
    && npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
