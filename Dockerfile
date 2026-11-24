FROM python:3.13-slim
WORKDIR /app
COPY server.py config.default.json ./
COPY public ./public
ENV DATA_DIR=/data PORT=8080
USER 1000:1000
CMD ["python", "server.py"]
