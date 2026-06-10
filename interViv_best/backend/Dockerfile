FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY backend ./backend
COPY modules ./modules
COPY data ./data

EXPOSE 8000

CMD ["sh", "-c", "if [ -n \"$DATABASE_URL\" ]; then alembic upgrade head; fi; uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
