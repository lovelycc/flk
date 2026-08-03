PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS laws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    short_name TEXT NOT NULL DEFAULT '',
    issuing_authority TEXT NOT NULL DEFAULT '',
    jurisdiction TEXT NOT NULL DEFAULT '中国',
    category TEXT NOT NULL DEFAULT '法律',
    status TEXT NOT NULL DEFAULT 'effective',
    promulgation_date TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    source_url TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS law_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    law_id INTEGER NOT NULL,
    version_label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'effective',
    promulgation_date TEXT,
    effective_date TEXT,
    expiry_date TEXT,
    source_url TEXT NOT NULL DEFAULT '',
    source_record_id TEXT NOT NULL DEFAULT '',
    source_hash TEXT NOT NULL DEFAULT '',
    is_current INTEGER NOT NULL DEFAULT 0 CHECK (is_current IN (0, 1)),
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE,
    UNIQUE (law_id, version_label)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_law_versions_one_current
    ON law_versions(law_id) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS idx_law_versions_law ON law_versions(law_id);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    law_version_id INTEGER NOT NULL,
    article_no INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    book TEXT NOT NULL DEFAULT '',
    chapter TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    related_articles TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (law_version_id) REFERENCES law_versions(id) ON DELETE CASCADE,
    UNIQUE (law_version_id, article_no)
);

CREATE INDEX IF NOT EXISTS idx_articles_version_number ON articles(law_version_id, article_no);
CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title);
CREATE INDEX IF NOT EXISTS idx_articles_book ON articles(book);
CREATE INDEX IF NOT EXISTS idx_articles_chapter ON articles(chapter);

CREATE TABLE IF NOT EXISTS notes (
    law_id INTEGER NOT NULL,
    article_no INTEGER NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (law_id, article_no),
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorites (
    law_id INTEGER NOT NULL,
    article_no INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (law_id, article_no),
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS browsing_history (
    law_id INTEGER NOT NULL,
    article_no INTEGER NOT NULL,
    view_count INTEGER NOT NULL DEFAULT 1,
    viewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (law_id, article_no),
    FOREIGN KEY (law_id) REFERENCES laws(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_browsing_history_recent
    ON browsing_history(viewed_at DESC);

CREATE TABLE IF NOT EXISTS update_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT ''
);
