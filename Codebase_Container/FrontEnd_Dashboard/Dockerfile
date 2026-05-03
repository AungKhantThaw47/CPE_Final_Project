FROM nginx:alpine

# Copy static assets
COPY crisis-dashboard.html /usr/share/nginx/html/index.html
COPY project-poster.html /usr/share/nginx/html/poster.html
COPY poster-canva.html /usr/share/nginx/html/canva.html

# Update nginx to listen on 8080
RUN sed -i 's/listen\s*80;/listen 8080;/g' /etc/nginx/conf.d/default.conf

# Set default EVENTS_API_URL if not provided by Cloud Run
ENV EVENTS_API_URL=http://events-api:8080/events

EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
