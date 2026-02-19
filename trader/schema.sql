-- Trader Database Schema
-- SQLite database for storing scraped trader data

-- Items table for storing scraped item data
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL,
    url TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for duplicate detection based on URL
CREATE INDEX IF NOT EXISTS idx_items_url ON items(url);
