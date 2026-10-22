# Imagem única: compila o painel (React) e roda a API Flask, que também serve o painel.
# Usada no Render (Web Service > Docker) e numa VPS (docker compose).

# ---- 1) Painel ---------------------------------------------------------------
FROM node:25-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 2) API ------------------------------------------------------------------
FROM python:3.13-slim
# APP_ENV=production por padrão (debug desligado, HSTS, checagem da SECRET_KEY);
# a variável do serviço no Render/VPS continua tendo prioridade.
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 APP_ENV=production
WORKDIR /srv/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY database/ /srv/database/
COPY --from=web /web/dist /srv/frontend/dist

RUN useradd --create-home appuser
USER appuser

# O Render define $PORT; localmente o padrão é 5000 (gunicorn.conf.py)
EXPOSE 5000
# Aplica migrations pendentes e sobe a API. Para o worker separado: `python worker.py`
CMD ["sh", "-c", "python migrate.py && exec gunicorn -c gunicorn.conf.py wsgi:app"]
