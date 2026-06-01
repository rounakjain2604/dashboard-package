create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    email text unique not null,
    created_at timestamptz not null default now()
);

create table if not exists subscriptions (
    id uuid primary key default gen_random_uuid(),
    email text not null,
    provider text not null,
    provider_customer_id text,
    provider_subscription_id text,
    plan text not null,
    status text not null,
    current_period_end timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists usage_events (
    id uuid primary key default gen_random_uuid(),
    email text,
    anonymous_id text,
    event_type text not null,
    ticker text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists export_credits (
    email text primary key,
    credits_remaining integer not null default 0,
    updated_at timestamptz not null default now()
);

create table if not exists exports (
    id uuid primary key default gen_random_uuid(),
    email text,
    ticker text not null,
    status text not null,
    warnings jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists payment_events (
    id uuid primary key default gen_random_uuid(),
    provider text not null,
    provider_event_id text not null unique,
    event_type text not null,
    email text,
    amount integer,
    currency text,
    raw jsonb not null,
    created_at timestamptz not null default now()
);
