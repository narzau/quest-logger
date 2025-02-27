# scripts/setup-local-dev.sh
#!/bin/bash
set -e

echo "Setting up local development environment..."

# Start the database
echo "Starting PostgreSQL container..."
docker compose up -d db

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Seed initial data
echo "Seeding initial data..."
python scripts/seed_data.py

echo "Setup complete! You can now run the application locally."