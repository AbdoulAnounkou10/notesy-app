# ---- Stage 1: Build the TypeScript/JS assets ----
# We use Node just to compile the frontend bundle
# This stage gets thrown away after — it never ends up in the final image
FROM node:20-slim AS node-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY apps/notes/static_src ./apps/notes/static_src
RUN npm run build

# ---- Stage 2: Python base ----
# Slim image = smaller, fewer vulnerabilities than the full python image
FROM python:3.12-slim AS final
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# PYTHONDONTWRITEBYTECODE: don't write .pyc files (useless in containers)
# PYTHONUNBUFFERED: log output streams immediately, don't buffer it

WORKDIR /app

# Install libpq-dev so psycopg2 can talk to Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the compiled JS bundle from the Node stage
# This is the multi-stage magic — we get the built assets without Node in our final image
COPY --from=node-build /app/static/js ./static/js

# Copy the rest of the application code
COPY . .

# Create a non-root user and switch to it
# If the container is ever compromised, attacker only gets this user's permissions
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Copy and run the entrypoint script
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["bash", "/entrypoint.sh"]