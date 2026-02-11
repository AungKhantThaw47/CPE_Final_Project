FROM node:20-alpine

WORKDIR /app

# Copy package files FIRST (least frequently changed)
# This layer is cached unless package*.json changes
COPY package*.json ./

# Install dependencies
# Cached layer - only rebuilds if package*.json changes
RUN npm install

# Copy shared utils (changes less frequently than app code)
# Expected to be in build context via terraform copy
COPY utils /workspace/utils

# Copy application code LAST (most frequently changed)
# This ensures code changes don't invalidate dependency cache
COPY *.js *.json *.html ./

# Run the crawler
CMD ["node", "DVB_Burmese.crawler.js"]
