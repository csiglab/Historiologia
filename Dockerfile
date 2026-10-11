FROM python:3.12-slim

WORKDIR /srv/historiologia

# Runtime needs only the thin server + the static app root (stdlib only,
# no dependencies to install).
COPY app.py ./
COPY app/ ./app/

ENV PORT=8022
ENV HOST=0.0.0.0

EXPOSE 8022

CMD ["python", "app.py"]
