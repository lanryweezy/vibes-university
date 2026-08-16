## 2024-05-24 - Missing SQLite Index for Course Progress

**Learning:** The `course_progress` table had a `UNIQUE (user_id, course_id, lesson_id)` constraint, which creates a composite index. However, queries filtering or joining solely by `lesson_id` (like the admin dashboard's query calculating completions per lesson) cannot use this index because `lesson_id` is not the first column in the composite index. This forces a full table scan on `course_progress`, causing an N+1 query problem or slow sequential scans on large datasets.

**Action:** Added a dedicated index `idx_course_progress_lesson_id` on the `lesson_id` column. Next time, always check if foreign keys or columns used independently in JOIN/WHERE clauses have dedicated indexes, especially when they are part of a larger composite index where they aren't the prefix.
