# Interface web servie par Nginx, avec proxy /api/ vers le service api.
# Contexte de build : racine du projet (voir Dockerfile.dockerignore).
FROM nginx:1.29-alpine
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY frontend/index.html frontend/app.js frontend/style.css /usr/share/nginx/html/
