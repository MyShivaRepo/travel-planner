FROM python:3.12-slim

LABEL maintainer="bernard"
LABEL description="Travel Planner – Application de planification de voyage avec Claude & Streamlit"

WORKDIR /app

COPY docker/python_dependencies.txt .
RUN pip install --no-cache-dir -r python_dependencies.txt

COPY src/ .

RUN mkdir -p /data

EXPOSE 9999

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9999/_stcore/health || exit 1

ENTRYPOINT ["python", "-m", "streamlit", "run", "app.py", \
            "--server.headless=true", \
            "--server.address=0.0.0.0", \
            "--server.port=9999", \
            "--browser.gatherUsageStats=false"]
