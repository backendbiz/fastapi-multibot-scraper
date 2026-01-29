# Docker Commands for FastAPI Scraper Server

This guide provides the essential Docker commands to manage the FastAPI Scraper Server.

## Prerequisites

- Docker Desktop installed and running
- Clone the repository

## Quick Start

### 1. Build and Run

This command builds the image and starts the container.

```bash
docker-compose up --build
```

### 2. Run in Detached Mode (Background)

Start the server in the background so it doesn't occupy your terminal.

```bash
docker-compose up -d --build
```

### 3. Stop the Server

Stop the running containers.

```bash
docker-compose down
```

## Logs and Debugging

### View Logs

Watch the real-time logs of the application.

```bash
docker-compose logs -f
```

### View Logs for Specific Service

If you want to just see the logs for the scraper service:

```bash
docker logs -f fastapi-scraper
```

### Check Running Containers

See status of active containers.

```bash
docker ps
```

## Management and Maintenance

### Rebuild Without Cache

If you made changes to `requirements.txt` or `Dockerfile` and need a clean build:

```bash
docker-compose build --no-cache
```

### Access the Container Shell

Open a bash shell inside the running container for debugging.

```bash
docker exec -it fastapi-scraper /bin/bash
```

### Prune Docker System

Clean up unused images, containers, and networks (use with caution).

```bash
docker system prune -f
```

## Troubleshooting

### "Cannot connect to the Docker daemon"

Ensure Docker Desktop is running. On macOS/Linux, verify with:

```bash
docker info
```

### Port Conflicts

If port 8000 is already in use, you can modify the port mapping in `docker-compose.yml` or run:

```bash
PORT=8001 docker-compose up
```
