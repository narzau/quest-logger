# scripts/start.sh
#!/bin/bash
set -e

# Wait for postgres to be ready
echo "Waiting for PostgreSQL to be ready..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL is ready!"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Optional: Run the seed script if the database is fresh
if [ "$SEED_DB" = "true" ]; then
  echo "Seeding the database..."
  python scripts/seed_data.py
fi

# Start the application
echo "Starting the application..."
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload