## 2024-05-24 - Missing SQLite Index for Course Progress

**Learning:** The `course_progress` table had a `UNIQUE (user_id, course_id, lesson_id)` constraint, which creates a composite index. However, queries filtering or joining solely by `lesson_id` (like the admin dashboard's query calculating completions per lesson) cannot use this index because `lesson_id` is not the first column in the composite index. This forces a full table scan on `course_progress`, causing an N+1 query problem or slow sequential scans on large datasets.

**Action:** Added a dedicated index `idx_course_progress_lesson_id` on the `lesson_id` column. Next time, always check if foreign keys or columns used independently in JOIN/WHERE clauses have dedicated indexes, especially when they are part of a larger composite index where they aren't the prefix.

## 2026-08-18 - Missing SQLite Index for Enrollments Payment Status

**Learning:** The `enrollments` table is heavily queried in analytics and dashboard features (calculating revenue, counting completed enrollments, etc.) using `WHERE payment_status = 'completed'`. Without an index on `payment_status`, these queries require full sequential table scans, severely impacting dashboard load times as the enrollments table grows.

**Action:** Added a dedicated index `idx_enrollments_payment_status` on the `payment_status` column to avoid full table scans. In the future, explicitly look for low-cardinality status columns frequently used in filtering for aggregate/analytic queries and ensure they are indexed if queried extensively.
