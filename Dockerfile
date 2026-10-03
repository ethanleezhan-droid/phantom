# Container image for the Phantom Wallet Simulator web app.
# Works on Fly.io, Railway (Docker), Cloud Run, or any container host.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project (app.py, wallet_core.py, templates/, static/,
# assets/, data/, admin/ seed files).
COPY . .

# Hosts inject $PORT; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 1 --timeout 120"]
