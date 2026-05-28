FROM node:18-alpine AS build

WORKDIR /app

# Copy frontend sources and install dependencies
COPY frontend/package*.json frontend/
RUN cd frontend && npm ci --silent
COPY frontend/ frontend/

# Build static assets
RUN cd frontend && npm run build

FROM nginx:stable-alpine

# Copy built static files into nginx
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
