# Migrating to Supabase PostgreSQL

This guide helps you migrate from a local PostgreSQL database to Supabase.

## Step 1: Create a Supabase Account and Project

1. Go to [https://supabase.com](https://supabase.com) and sign up
2. Create a new project
3. Choose a region close to your location
4. Set a strong database password (save this!)
5. Wait for the project to be provisioned (takes ~2 minutes)

## Step 2: Get Your Database Connection String

1. Go to your Supabase project dashboard
2. Click on "Settings" → "Database"
3. Find the "Connection String" section
4. Copy the "URI" connection string
5. It should look like: `postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres`

## Step 3: Update Your Environment Variables

Create or update your `.env` file:

```bash
# Replace with your actual Supabase connection string
SQLALCHEMY_DATABASE_URI=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Optional: Supabase project details for management
SUPABASE_URL=https://[PROJECT-REF].supabase.co
SUPABASE_KEY=[YOUR-ANON-KEY]
SUPABASE_PROJECT_ID=[PROJECT-REF]
```

## Step 4: Export Data from Local Database (Optional)

If you have existing data you want to preserve:

```bash
# Export data from local database
docker exec quest-tracker-db pg_dump -U postgres quest_tracker > backup.sql

# Import to Supabase (replace connection details)
psql postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres < backup.sql
```

## Step 5: Run Migrations on Supabase

```bash
# Make sure your .env file has the Supabase connection string
# Then run migrations
alembic upgrade head

# Or using Docker:
docker-compose -f docker-compose.supabase.yml run --rm api alembic upgrade head
```

## Step 6: Start Your Application

```bash
# Using the new Supabase-specific Docker Compose
docker-compose -f docker-compose.supabase.yml up

# Or run locally with Python
uvicorn app.main:app --reload
```

## Benefits of Using Supabase

1. **Managed Database**: No more database disappearing overnight
2. **Automatic Backups**: Supabase handles backups for you
3. **High Availability**: Better uptime and reliability
4. **Connection Pooling**: Built-in connection pooling with PgBouncer
5. **Web Dashboard**: Easy database management through Supabase Studio
6. **Row Level Security**: Additional security features if needed
7. **Real-time Subscriptions**: Future capability for real-time features

## Security Best Practices

1. **Use Environment Variables**: Never commit database credentials
2. **Enable SSL**: Supabase connections use SSL by default
3. **IP Restrictions**: Consider adding IP allowlists in Supabase dashboard
4. **Regular Backups**: Enable point-in-time recovery in Supabase

## Troubleshooting

### Connection Issues
- Ensure your database password doesn't contain special characters that need URL encoding
- Check if your IP is allowed in Supabase (Settings → Database → Connection Pooling)

### Migration Issues
- Make sure all migrations are up to date locally before running on Supabase
- Use `alembic history` to check migration status

### Performance
- Supabase uses connection pooling by default
- For production, use the pooled connection string (port 6543 instead of 5432)

## Monitoring Your Database

1. Go to Supabase Dashboard → Database
2. Monitor:
   - Active connections
   - Database size
   - Query performance
   - Slow queries

## Cost Considerations

- Free tier includes:
  - 500MB database
  - 2GB bandwidth
  - Suitable for development/small projects
- Pro plan ($25/month) includes:
  - 8GB database
  - 50GB bandwidth
  - Point-in-time recovery
  - Daily backups 