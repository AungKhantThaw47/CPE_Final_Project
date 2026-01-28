FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Run the crawler
CMD ["node", "DVB_Burmese.crawler.js"]
