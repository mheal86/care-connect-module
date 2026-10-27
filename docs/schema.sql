-- Care Connect public module schema. Demo host tables: users, user_relative, user_profile, one_time_reminders.

CREATE TABLE IF NOT EXISTS users (
 id SERIAL PRIMARY KEY, username VARCHAR(255) NOT NULL UNIQUE,
 password_hash TEXT NOT NULL DEFAULT '', salt TEXT NOT NULL DEFAULT '',
 display_name TEXT NOT NULL DEFAULT '', role VARCHAR(32) NOT NULL DEFAULT 'elder',
 status VARCHAR(32) NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS user_relative (
 id SERIAL PRIMARY KEY, caregiver_id VARCHAR(255) NOT NULL,
 elder_id VARCHAR(255) NOT NULL, UNIQUE(caregiver_id, elder_id)
);
CREATE TABLE IF NOT EXISTS user_profile (
 id SERIAL PRIMARY KEY, user_id VARCHAR(255) NOT NULL UNIQUE,
 data JSONB NOT NULL DEFAULT '{}'::jsonb, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS one_time_reminders (
    id              VARCHAR(100) PRIMARY KEY,
    user_id         VARCHAR(255) NOT NULL DEFAULT 'default',
    date            DATE NOT NULL,
    time            VARCHAR(10) NOT NULL,
    title           VARCHAR(500),
    type            VARCHAR(100),
    details         TEXT,
    status          VARCHAR(50) NOT NULL DEFAULT 'waiting',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS care_facilities (
    id               VARCHAR(64) PRIMARY KEY,
    name             VARCHAR(255) NOT NULL,
    facility_type    VARCHAR(32)  NOT NULL,
    district         VARCHAR(120) NOT NULL,
    address          TEXT         NOT NULL,
    phone            VARCHAR(64)  NOT NULL,
    hours            VARCHAR(120) NOT NULL,
    distance_km      NUMERIC(5,2) NOT NULL DEFAULT 0,
    lat              DOUBLE PRECISION,
    lng              DOUBLE PRECISION,
    geo_verified     BOOLEAN      NOT NULL DEFAULT FALSE,
    verified_badge   BOOLEAN      NOT NULL DEFAULT FALSE,
    price_from       INTEGER      NOT NULL DEFAULT 0,
    price_to         INTEGER      NOT NULL DEFAULT 0,
    price_unit       VARCHAR(32)  NOT NULL DEFAULT 'month',
    support_tags     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    highlights       JSONB        NOT NULL DEFAULT '[]'::jsonb,
    suitable_for     JSONB        NOT NULL DEFAULT '[]'::jsonb,
    services         JSONB        NOT NULL DEFAULT '[]'::jsonb,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS care_facility_services (
    id             VARCHAR(64) PRIMARY KEY,
    facility_id    VARCHAR(64) NOT NULL,
    name           VARCHAR(255) NOT NULL,
    category       VARCHAR(32)  NOT NULL,
    duration_label VARCHAR(64)  NOT NULL,
    price          INTEGER      NOT NULL DEFAULT 0,
    price_unit     VARCHAR(32)  NOT NULL DEFAULT 'month',
    note           TEXT         NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS care_facility_services_fac_idx ON care_facility_services (facility_id);

CREATE TABLE IF NOT EXISTS care_facility_members (
    id          SERIAL PRIMARY KEY,
    facility_id VARCHAR(64)  NOT NULL,
    user_id     VARCHAR(255) NOT NULL,
    member_role VARCHAR(32)  NOT NULL DEFAULT 'staff',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (facility_id, user_id)
);
CREATE INDEX IF NOT EXISTS care_facility_members_user_idx ON care_facility_members (user_id);

CREATE TABLE IF NOT EXISTS care_requests (
    id                 VARCHAR(64) PRIMARY KEY,
    code               VARCHAR(32)  NOT NULL UNIQUE,
    user_id            VARCHAR(255) NOT NULL,
    profile_id         VARCHAR(64)  NOT NULL,
    profile_name       VARCHAR(255) NOT NULL,
    profile_age        INTEGER      NOT NULL,
    care_level         VARCHAR(16)  NOT NULL,
    care_needs         TEXT         NOT NULL DEFAULT '',
    facility_id        VARCHAR(64)  NOT NULL,
    facility_name      VARCHAR(255) NOT NULL,
    service_id         VARCHAR(64)  NOT NULL,
    service_name       VARCHAR(255) NOT NULL,
    consult_type       VARCHAR(32)  NOT NULL,
    preferred_slot     TIMESTAMPTZ  NOT NULL,
    confirmed_slot     TIMESTAMPTZ,
    proposed_slot      TIMESTAMPTZ,
    slot_id            VARCHAR(64),
    contact_name       VARCHAR(255) NOT NULL,
    contact_phone      VARCHAR(64)  NOT NULL,
    note               TEXT         NOT NULL DEFAULT '',
    status             VARCHAR(32)  NOT NULL,
    version            INTEGER      NOT NULL DEFAULT 1,
    last_reason        TEXT         NOT NULL DEFAULT '',
    idempotency_key    VARCHAR(128),
    reminder_opt_in    BOOLEAN      NOT NULL DEFAULT FALSE,
    reminder_id        VARCHAR(128),
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS care_requests_user_idx     ON care_requests (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS care_requests_facility_idx ON care_requests (facility_id, status);

CREATE TABLE IF NOT EXISTS care_request_events (
    id          BIGSERIAL PRIMARY KEY,
    request_id  VARCHAR(64)  NOT NULL,
    at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    actor_role  VARCHAR(32)  NOT NULL,
    actor_name  VARCHAR(255) NOT NULL,
    action      VARCHAR(64)  NOT NULL,
    from_status VARCHAR(32)  NOT NULL,
    to_status   VARCHAR(32)  NOT NULL,
    note        TEXT         NOT NULL DEFAULT '',
    slot        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS care_request_events_req_idx ON care_request_events (request_id, id ASC);

CREATE TABLE IF NOT EXISTS care_consult_slots (
    id           VARCHAR(64) PRIMARY KEY,
    facility_id  VARCHAR(64) NOT NULL,
    consult_type VARCHAR(32) NOT NULL,
    starts_at    TIMESTAMPTZ NOT NULL,
    ends_at      TIMESTAMPTZ NOT NULL,
    capacity     INTEGER     NOT NULL DEFAULT 1,
    booked_count INTEGER     NOT NULL DEFAULT 0,
    CHECK (booked_count >= 0 AND booked_count <= capacity)
);
CREATE INDEX IF NOT EXISTS care_consult_slots_fac_idx ON care_consult_slots (facility_id, starts_at);

CREATE TABLE IF NOT EXISTS care_feedback (
    id                VARCHAR(64) PRIMARY KEY,
    request_id        VARCHAR(64)  NOT NULL UNIQUE,
    facility_id       VARCHAR(64)  NOT NULL,
    user_id           VARCHAR(255) NOT NULL,
    rating            SMALLINT     NOT NULL CHECK (rating BETWEEN 1 AND 5),
    tags              JSONB        NOT NULL DEFAULT '[]'::jsonb,
    comment           TEXT         NOT NULL DEFAULT '',
    moderation_status VARCHAR(16)  NOT NULL DEFAULT 'pending',
    moderated_by      VARCHAR(255),
    moderated_at      TIMESTAMPTZ,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS care_feedback_fac_idx ON care_feedback (facility_id, moderation_status);

-- Additive fields keep existing installations compatible with the catalogue UI.
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS published BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS region VARCHAR(32) NOT NULL DEFAULT 'hcm';
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
ALTER TABLE care_facilities ADD COLUMN IF NOT EXISTS amenities JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE care_requests ADD COLUMN IF NOT EXISTS idempotency_hash VARCHAR(64);

CREATE TABLE IF NOT EXISTS care_trial_alerts (
    id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(255) NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    client_event_id VARCHAR(128) NOT NULL,
    source VARCHAR(24) NOT NULL,
    note TEXT NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'NEW',
    acknowledged_by VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(created_by, client_event_id)
);
CREATE TABLE IF NOT EXISTS care_profile_grants (
    id VARCHAR(64) PRIMARY KEY,
    profile_id VARCHAR(255) NOT NULL,
    owner_id VARCHAR(255) NOT NULL,
    facility_id VARCHAR(64) NOT NULL,
    fields JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS care_profile_access_log (
    id BIGSERIAL PRIMARY KEY,
    grant_id VARCHAR(64) NOT NULL,
    actor_id VARCHAR(255) NOT NULL,
    action VARCHAR(24) NOT NULL,
    at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
