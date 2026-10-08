FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY database/ /srv/database/

RUN useradd --create-home appuser
USER appuser

EXPOSE 5000
# O mesmo container serve a API (padrão) ou o worker: `python worker.py`
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
