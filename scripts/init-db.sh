# scripts/init-db.sh
#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    CREATE DATABASE quest_tracker;
    GRANT ALL PRIVILEGES ON DATABASE quest_tracker TO postgres;
EOSQL

echo "Database quest_tracker created successfully"