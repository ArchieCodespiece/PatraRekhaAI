# Email Ingestion

This Python service polls an IMAP mailbox for unread messages, uploads every attachment to the `file_storage` Supabase bucket, and inserts a row in the `files` table.

## Run locally

```bash
cd backend/email-ingestion
cp .env.example .env
set -a && source .env && set +a
./.venv/bin/python ingest.py
```

Set `ALLOWED_SENDERS` to a comma-separated list to restrict ingestion. Successfully stored messages are marked as read and recorded in `data/processed.json`, so reconnects and process restarts do not create duplicates. A failed message remains unread and will be retried on the next poll.

Use a service-role key for this backend-only process. The publishable/anon key will hit RLS when inserting into `files`.

## Supabase table

Create the table before running the poller:

```sql
create table public.files (
  file_id uuid not null default gen_random_uuid (),
  filename text not null,
  file_url text not null,
  file_type character varying(100) not null,
  file_size bigint not null,
  created_at timestamp with time zone not null default timezone ('utc'::text, now()),
  uploaded_at timestamp with time zone not null default timezone ('utc'::text, now()),
  constraint files_pkey primary key (file_id)
) TABLESPACE pg_default;

create index IF not exists idx_files_filename on public.files using btree (filename) TABLESPACE pg_default;
```
