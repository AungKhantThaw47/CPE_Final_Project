FROM node:20-alpine

WORKDIR /app

COPY Codebase_Container/coordinator_job/package*.json ./

RUN npm install

COPY utils ./utils

COPY Codebase_Container/coordinator_job/*.js ./

ENTRYPOINT ["node", "DVB_Burmese.coordinator.js"]
CMD []
