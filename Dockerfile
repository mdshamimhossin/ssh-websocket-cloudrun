FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends openssh-server tini && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash tunneluser && mkdir -p /run/sshd
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py start.sh sshd_config ./
RUN chmod 755 /app/start.sh
EXPOSE 8080
ENTRYPOINT ["/usr/bin/tini", "--", "/app/start.sh"]
