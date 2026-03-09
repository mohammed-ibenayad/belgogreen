FROM ghcr.io/puppeteer/puppeteer:23.6.0

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Copy source code
COPY . .

EXPOSE 3002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3002/health', (r) => { process.exit(r.statusCode === 200 ? 0 : 1) })"

CMD ["node", "src/index.js"]
