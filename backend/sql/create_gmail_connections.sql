create table if not exists public.gmail_connections (
  owner_email text primary key,
  google_email text not null,
  provider_access_token text not null,
  provider_refresh_token text,
  scopes text,
  connected_at timestamp with time zone not null default timezone('utc'::text, now()),
  updated_at timestamp with time zone not null default timezone('utc'::text, now())
);

create index if not exists idx_gmail_connections_google_email
  on public.gmail_connections using btree (google_email);
