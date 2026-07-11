CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(254) NOT NULL,
    phone VARCHAR(32),
    password_hash TEXT NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'RUB'
        CHECK (currency IN ('RUB', 'USD', 'EUR')),
    week_start VARCHAR(10) NOT NULL DEFAULT 'monday'
        CHECK (week_start IN ('monday', 'sunday')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_unique
    ON users (LOWER(email));

CREATE TABLE IF NOT EXISTS families (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    invite_code VARCHAR(16) NOT NULL UNIQUE,
    created_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS family_members (
    family_id BIGINT NOT NULL REFERENCES families(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'member'
        CHECK (role IN ('owner', 'member')),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (family_id, user_id),
    UNIQUE (user_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS family_single_owner_unique
    ON family_members (family_id)
    WHERE role = 'owner';

CREATE TABLE IF NOT EXISTS categories (
    id BIGSERIAL PRIMARY KEY,
    scope VARCHAR(10) NOT NULL,
    owner_user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    family_id BIGINT REFERENCES families(id) ON DELETE CASCADE,
    parent_id BIGINT REFERENCES categories(id) ON DELETE RESTRICT,
    name VARCHAR(80) NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
    icon VARCHAR(2),
    color CHAR(7) NOT NULL DEFAULT '#2563eb',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT categories_scope_check CHECK (
        (scope = 'personal' AND owner_user_id IS NOT NULL AND family_id IS NULL)
        OR
        (scope = 'family' AND owner_user_id IS NULL AND family_id IS NOT NULL)
    ),
    CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE UNIQUE INDEX IF NOT EXISTS categories_personal_name_unique
    ON categories (owner_user_id, COALESCE(parent_id, 0), LOWER(name))
    WHERE scope = 'personal';

CREATE UNIQUE INDEX IF NOT EXISTS categories_family_name_unique
    ON categories (family_id, COALESCE(parent_id, 0), LOWER(name))
    WHERE scope = 'family';

CREATE INDEX IF NOT EXISTS categories_owner_idx
    ON categories (owner_user_id, type, parent_id)
    WHERE scope = 'personal';

CREATE INDEX IF NOT EXISTS categories_family_idx
    ON categories (family_id, type, parent_id)
    WHERE scope = 'family';

CREATE TABLE IF NOT EXISTS transactions (
    id BIGSERIAL PRIMARY KEY,
    scope VARCHAR(10) NOT NULL,
    family_id BIGINT REFERENCES families(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    category_id BIGINT NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    type VARCHAR(10) NOT NULL CHECK (type IN ('income', 'expense')),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    transaction_date DATE NOT NULL,
    description VARCHAR(200) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT transactions_scope_check CHECK (
        (scope = 'personal' AND family_id IS NULL)
        OR
        (scope = 'family' AND family_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS transactions_user_date_idx
    ON transactions (user_id, transaction_date DESC)
    WHERE scope = 'personal';

CREATE INDEX IF NOT EXISTS transactions_family_date_idx
    ON transactions (family_id, transaction_date DESC)
    WHERE scope = 'family';

CREATE INDEX IF NOT EXISTS transactions_category_idx
    ON transactions (category_id);

CREATE TABLE IF NOT EXISTS savings_entries (
    id BIGSERIAL PRIMARY KEY,
    scope VARCHAR(10) NOT NULL,
    family_id BIGINT REFERENCES families(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    entry_type VARCHAR(12) NOT NULL CHECK (entry_type IN ('deposit', 'withdrawal')),
    amount NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    entry_date DATE NOT NULL DEFAULT CURRENT_DATE,
    reason VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT savings_entries_scope_check CHECK (
        (scope = 'personal' AND family_id IS NULL)
        OR
        (scope = 'family' AND family_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS savings_entries_user_date_idx
    ON savings_entries (user_id, entry_date DESC)
    WHERE scope = 'personal';

CREATE INDEX IF NOT EXISTS savings_entries_family_date_idx
    ON savings_entries (family_id, entry_date DESC)
    WHERE scope = 'family';

CREATE TABLE IF NOT EXISTS monthly_budgets (
    id BIGSERIAL PRIMARY KEY,
    scope VARCHAR(10) NOT NULL,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    family_id BIGINT REFERENCES families(id) ON DELETE CASCADE,
    month DATE NOT NULL CHECK (EXTRACT(DAY FROM month) = 1),
    spending_limit NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (spending_limit >= 0),
    updated_by BIGINT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT monthly_budgets_scope_check CHECK (
        (scope = 'personal' AND user_id IS NOT NULL AND family_id IS NULL)
        OR
        (scope = 'family' AND user_id IS NULL AND family_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS monthly_budgets_personal_unique
    ON monthly_budgets (user_id, month)
    WHERE scope = 'personal';

CREATE UNIQUE INDEX IF NOT EXISTS monthly_budgets_family_unique
    ON monthly_budgets (family_id, month)
    WHERE scope = 'family';
