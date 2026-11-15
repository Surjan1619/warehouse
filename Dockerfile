FROM python:3.14-slim

WORKDIR /srv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt requirements-dev.txt ./
# The dev requirements add the test runner; this image is for development
RUN pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

COPY alembic.ini pytest.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app
COPY tests ./tests

EXPOSE 8000

# Apply pending migrations, then start the API
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
