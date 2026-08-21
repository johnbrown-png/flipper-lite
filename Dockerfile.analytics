# Container for the standalone analytics webhook receiver (analytics_webhook_server.py).
# This is deployed separately from the Streamlit app so events have a durable,
# publicly reachable home instead of the Streamlit Cloud app's ephemeral filesystem.
FROM python:3.12-slim

WORKDIR /app
COPY analytics_webhook_server.py ./

ENV PORT=8080
ENV ANALYTICS_DB_PATH=/data/events.db

EXPOSE 8080

CMD ["python", "analytics_webhook_server.py"]
