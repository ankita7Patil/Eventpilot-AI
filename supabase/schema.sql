create extension if not exists "pgcrypto";

create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  email text unique,
  display_name text,
  created_at timestamptz default now()
);

create table if not exists events (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  source_url text not null,
  title text not null,
  event_type text,
  summary text,
  urgency text default 'medium',
  briefing jsonb default '{}'::jsonb,
  scraped jsonb default '{}'::jsonb,
  activities jsonb default '[]'::jsonb,
  alerts jsonb default '[]'::jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists timelines (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events(id) on delete cascade,
  time_text text not null,
  title text not null,
  detail text,
  priority text default 'medium',
  created_at timestamptz default now()
);

create table if not exists reminders (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events(id) on delete cascade,
  message text not null,
  priority text default 'medium',
  scheduled_for timestamptz,
  scheduled_for_text text,
  sent_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists ai_briefings (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events(id) on delete cascade,
  provider text,
  model text,
  briefing jsonb not null,
  created_at timestamptz default now()
);

create table if not exists activity_logs (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events(id) on delete cascade,
  agent_name text not null,
  action text not null,
  status text not null default 'completed',
  details jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists alerts (
  id uuid primary key default gen_random_uuid(),
  event_id uuid references events(id) on delete cascade,
  message text not null,
  priority text default 'medium',
  scheduled_for timestamptz,
  sent_at timestamptz,
  created_at timestamptz default now()
);

create index if not exists events_user_id_idx on events(user_id);
create index if not exists events_updated_at_idx on events(updated_at desc);
create index if not exists activity_logs_event_id_idx on activity_logs(event_id);
create index if not exists reminders_event_id_idx on reminders(event_id);
