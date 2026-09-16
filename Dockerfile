FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY gmail_mcp ./gmail_mcp

RUN pip install --no-cache-dir .

EXPOSE 8811

CMD ["uvicorn", "gmail_mcp.http_app:app", "--host", "0.0.0.0", "--port", "8811"]
