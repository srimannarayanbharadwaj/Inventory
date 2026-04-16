## Inventory System (Database-native multi-user copy)

This folder is the migrated version of the original inventory app.

It now:

- uses PostgreSQL through `DATABASE_URL` for multi-user live data
- auto-loads `.env` from this folder
- manages categories and products directly in the database
- no longer depends on `Product name list.xlsx` for runtime catalog data
- includes deployment files for hosted Streamlit runs

### Runtime backend

- if `DATABASE_URL` is set, the app uses PostgreSQL
- otherwise it falls back to local SQLite

### Local run

```bash
D:\Inventory cursor\.venv\Scripts\python.exe -m pip install -r requirements.txt
D:\Inventory cursor\.venv\Scripts\python.exe -m streamlit run app.py
```

### Supabase / PostgreSQL setup

1. Create the tables in Supabase by running `supabase_schema.sql` in the SQL Editor.
2. Create `.env` in this folder:

```env
DATABASE_URL=postgresql://...
```

3. Verify the hosted connection:

```bash
D:\Inventory cursor\.venv\Scripts\python.exe verify_postgres_setup.py
```

4. Start the app:

```bash
D:\Inventory cursor\.venv\Scripts\python.exe -m streamlit run app.py
```

### CSV export for manual imports

If you need CSV exports from the local SQLite database:

```bash
D:\Inventory cursor\.venv\Scripts\python.exe export_sqlite_to_csv.py
```

This creates:

- `csv_export/products.csv`
- `csv_export/users.csv`
- `csv_export/transactions.csv`
- `csv_export/orders.csv`

### Deployment

This folder includes:

- `Dockerfile` for container hosting
- `Procfile` for simple PaaS-style hosting
- `.dockerignore` to keep local files out of the image

Recommended production behavior:

- run `python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT`
- set `DATABASE_URL` in the host environment
- do not use the local auto-stop launcher scripts for production
- rotate the default admin password after first login

### Remaining recommended improvements

- replace the local password recovery flow with email-based recovery
- add stronger audit logging and admin activity reporting
- add near-real-time refresh if multiple users will work at once
