# Email Ingestion

This Python service polls connected Gmail accounts via the Gmail API for unread inbox messages, uploads every attachment to the `file_storage` Supabase bucket, and inserts a row in the `files` table. Each stored row is tagged with the mailbox owner email so document lists stay isolated per account.

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
alter table public.files
  add column if not exists owner_email text;

create index if not exists idx_files_owner_email on public.files using btree (owner_email);
```
