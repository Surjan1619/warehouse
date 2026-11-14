FROM node:22-alpine

WORKDIR /srv

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host makes the Vite dev server reachable from outside the container
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
