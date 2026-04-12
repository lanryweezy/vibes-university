import sqlite3
import json
import os

def seed():
    conn = sqlite3.connect('vibes_university.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            excerpt TEXT,
            image_url TEXT,
            author_name TEXT,
            author_linkedin TEXT,
            author_twitter TEXT,
            author_ig TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    if os.path.exists('scripts/blogs_data.json'):
        with open('scripts/blogs_data.json', 'r') as f:
            blogs = json.load(f)

        for blog in blogs:
            try:
                cursor.execute('''
                    INSERT INTO blogs (title, slug, content, excerpt, image_url, author_name, author_linkedin, author_twitter, author_ig)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    blog['title'], blog['slug'], blog['content'], blog['excerpt'],
                    blog['image_url'], blog['author_name'], blog['author_linkedin'],
                    blog['author_twitter'], blog['author_ig']
                ))
            except sqlite3.IntegrityError:
                continue # Skip duplicates

        conn.commit()
        print(f"Successfully seeded {len(blogs)} blogs.")
    else:
        print("Error: scripts/blogs_data.json not found.")

    conn.close()

if __name__ == '__main__':
    seed()
