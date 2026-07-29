alter table public.files
  add column if not exists owner_email text;

create index if not exists idx_files_owner_email
  on public.files using btree (owner_email);
