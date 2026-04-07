FROM python:3.12-slim

LABEL maintainer="bernard"
LABEL description="Travel Planner – POI Finder avec Claude & Streamlit"

WORKDIR /app

COPY python_dependencies.txt .
RUN pip install --no-cache-dir -r python_dependencies.txt

COPY src/app.py .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["python", "-m", "streamlit", "run", "app.py", \
            "--server.headless=true", \
            "--server.address=0.0.0.0", \
            "--server.port=8501", \
            "--browser.gatherUsageStats=false"]
