FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FACTORY_DB=/data/factory.db
WORKDIR /app
COPY index.html factory.js factory.css server.py tools_catalog.py install.py ./
RUN python3 install.py && mkdir -p /data && chown 10001:10001 /data
USER 10001:10001
EXPOSE 8765
CMD ["python3", "server.py"]
