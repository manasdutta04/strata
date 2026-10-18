FROM node:20-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# The browser calls the API directly, so its public URL is baked in at build time.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine
WORKDIR /web
ENV NODE_ENV=production
COPY --from=build /web/package.json /web/package-lock.json ./
COPY --from=build /web/node_modules ./node_modules
COPY --from=build /web/.next ./.next
EXPOSE 3000
CMD ["npm", "start"]
