FROM node:20-alpine

WORKDIR /app

# Copy package files FIRST (least frequently changed)
# This layer is cached unless package*.json changes
# Build context is project root, so specify full path
COPY Codebase_Container/crawler_job/package*.json ./

# Install dependencies
# Cached layer - only rebuilds if package*.json changes
RUN npm install

# Copy shared utils into /app/utils so require('./utils/gcs_utils') resolves correctly
COPY utils ./utils

# Copy application code LAST (most frequently changed)
# This ensures code changes don't invalidate dependency cache
COPY Codebase_Container/crawler_job/*.js Codebase_Container/crawler_job/*.json Codebase_Container/crawler_job/*.html ./

# Use entrypoint so Cloud Run Job arguments are forwarded to the crawler script
ENTRYPOINT ["node", "DVB_Burmese.crawler.js"]
CMD []
