FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install minimal system dependencies
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg \
    build-essential unzip; \
    install -m 0755 -d /etc/apt/keyrings; \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    chmod a+r /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release; echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
    docker-ce-cli docker-compose-plugin; \
    rm -rf /var/lib/apt/lists/*

# Create the directories for our sibling mounts
RUN mkdir -p /app
# Set the starting directory for the script
WORKDIR /app

# Copy the script to a neutral location
COPY run_task.sh /usr/local/bin/run_task.sh
RUN chmod +x /usr/local/bin/run_task.sh

ENTRYPOINT ["/usr/local/bin/run_task.sh"]
