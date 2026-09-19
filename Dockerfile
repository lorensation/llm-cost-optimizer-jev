FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app app
COPY config config
COPY contracts contracts
COPY migrations migrations
COPY dashboard dashboard
RUN pip install --no-cache-dir .
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
