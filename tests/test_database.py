"""Tests for the database schema and items table."""

import os
import sqlite3
import tempfile
import unittest


class TestDatabaseSchema(unittest.TestCase):
    """Test cases for the database schema."""

    def setUp(self) -> None:
        """Set up a temporary database for each test."""
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.addCleanup(os.close, self.db_fd)
        self.addCleanup(os.unlink, self.db_path)

    def _load_schema(self) -> None:
        """Load the schema into the temporary database."""
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'trader', 'schema.sql'
        )
        with sqlite3.connect(self.db_path) as conn:
            with open(schema_path, 'r') as f:
                conn.executescript(f.read())

    def test_schema_file_exists(self) -> None:
        """Test that the schema.sql file exists at trader/schema.sql."""
        schema_path = os.path.join(
            os.path.dirname(__file__), '..', 'trader', 'schema.sql'
        )
        self.assertTrue(os.path.exists(schema_path), "schema.sql file should exist")

    def test_schema_creates_valid_database(self) -> None:
        """Test that the schema can be executed to create a valid SQLite database."""
        self._load_schema()
        # Verify database is valid by executing a simple query
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn('items', tables)

    def test_items_table_has_required_columns(self) -> None:
        """Test that items table has all required columns."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(items)")
            columns = {row[1]: row for row in cursor.fetchall()}

            # Check all required columns exist
            required_columns = ['id', 'name', 'price', 'url', 'scraped_at']
            for col in required_columns:
                self.assertIn(col, columns, f"Column {col} should exist")

            # Check column types and constraints
            # id: INTEGER PRIMARY KEY AUTOINCREMENT
            self.assertEqual(columns['id'][2], 'INTEGER')
            self.assertEqual(columns['id'][5], 1)  # primary key

            # name: TEXT NOT NULL
            self.assertEqual(columns['name'][2], 'TEXT')
            self.assertEqual(columns['name'][3], 1)  # not null

            # price: REAL
            self.assertEqual(columns['price'][2], 'REAL')
            self.assertEqual(columns['price'][3], 0)  # nullable

            # url: TEXT
            self.assertEqual(columns['url'][2], 'TEXT')
            self.assertEqual(columns['url'][3], 0)  # nullable

            # scraped_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            self.assertEqual(columns['scraped_at'][2], 'TIMESTAMP')
            self.assertEqual(columns['scraped_at'][4], 'CURRENT_TIMESTAMP')

    def test_items_url_index_exists(self) -> None:
        """Test that idx_items_url index exists for duplicate detection."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_items_url'"
            )
            index = cursor.fetchone()
            self.assertIsNotNone(index, "idx_items_url index should exist")

    def test_items_table_accepts_valid_data(self) -> None:
        """Test that the items table can accept valid insert statements."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            # Insert minimal valid data (name is required)
            conn.execute(
                "INSERT INTO items (name) VALUES (?)",
                ("Test Item",)
            )

            # Insert full data
            conn.execute(
                "INSERT INTO items (name, price, url) VALUES (?, ?, ?)",
                ("Another Item", 19.99, "http://example.com/item/1")
            )

            conn.commit()

            cursor = conn.execute("SELECT * FROM items ORDER BY id")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 2)

            # Check first row (minimal)
            self.assertEqual(rows[0][1], "Test Item")  # name
            self.assertIsNone(rows[0][2])  # price
            self.assertIsNone(rows[0][3])  # url
            self.assertIsNotNone(rows[0][4])  # scraped_at (auto-generated)

            # Check second row (full)
            self.assertEqual(rows[1][1], "Another Item")  # name
            self.assertEqual(rows[1][2], 19.99)  # price
            self.assertEqual(rows[1][3], "http://example.com/item/1")  # url

    def test_items_table_rejects_null_name(self) -> None:
        """Test that the items table rejects NULL name values."""
        self._load_schema()
        with sqlite3.connect(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO items (name, price) VALUES (?, ?)",
                    (None, 10.00)
                )


if __name__ == '__main__':
    unittest.main()
