## 2024-05-24 - Missing SQLite Index for Course Progress

**Learning:** The `course_progress` table had a `UNIQUE (user_id, course_id, lesson_id)` constraint, which creates a composite index. However, queries filtering or joining solely by `lesson_id` (like the admin dashboard's query calculating completions per lesson) cannot use this index because `lesson_id` is not the first column in the composite index. This forces a full table scan on `course_progress`, causing an N+1 query problem or slow sequential scans on large datasets.

**Action:** Added a dedicated index `idx_course_progress_lesson_id` on the `lesson_id` column. Next time, always check if foreign keys or columns used independently in JOIN/WHERE clauses have dedicated indexes, especially when they are part of a larger composite index where they aren't the prefix.

## 2026-08-18 - Missing SQLite Index for Enrollments Payment Status

**Learning:** The `enrollments` table is heavily queried in analytics and dashboard features (calculating revenue, counting completed enrollments, etc.) using `WHERE payment_status = 'completed'`. Without an index on `payment_status`, these queries require full sequential table scans, severely impacting dashboard load times as the enrollments table grows.

**Action:** Added a dedicated index `idx_enrollments_payment_status` on the `payment_status` column to avoid full table scans. In the future, explicitly look for low-cardinality status columns frequently used in filtering for aggregate/analytic queries and ensure they are indexed if queried extensively.

## 2026-08-20 - Inefficient In-Memory Aggregation for Dashboard Stats

**Learning:** The teacher dashboard previously calculated student counts and total earnings by fetching all related rows from the `enrollments` table using `.fetchall()` and then iterating over the list in Python (using `len()` and `sum()`). This is highly inefficient (O(N) memory and processing) and can become a significant bottleneck as the enrollments table grows, leading to slow dashboard load times and high memory usage.

**Action:** Replaced the in-memory calculations with database-level aggregation using `COUNT(*)` and `SUM(price)` in a `.fetchone()` query. In the future, always use database aggregation functions instead of retrieving full datasets to aggregate in application code.

## 2026-08-25 - Missing SQLite Index for Enrollments Enrolled At Sorting

**Learning:** The `admin_dashboard` and analytics routes frequently query the `enrollments` table and sort the results by `enrolled_at DESC` (e.g., to get recent enrollments). Without an index on `enrolled_at`, SQLite performs a full table scan and uses a temporary B-tree to sort the entire dataset before applying `LIMIT 10`. This O(N log N) sorting process becomes a significant bottleneck as the enrollments table grows.

**Action:** Added a dedicated index `idx_enrollments_enrolled_at` on the `enrolled_at` column. In the future, explicitly look for columns used in `ORDER BY` clauses combined with `LIMIT` on large tables, and ensure they are indexed to allow for O(1) index scans instead of full table temporary B-tree sorts.

## 2024-06-15 - Missing SQLite Index for Enrollments Payment Reference
**Learning:** The `enrollments` table is frequently queried during payment webhooks and verifications using `WHERE payment_reference = ?`. Without a dedicated index on `payment_reference`, these lookups trigger a full sequential table scan. As the enrollments table grows, this O(N) scan becomes a significant bottleneck during high-volume payment processing, potentially leading to webhook timeouts and delayed course access.
**Action:** Added a dedicated index `idx_enrollments_payment_reference` on the `payment_reference` column. In the future, explicitly look for columns used as unique identifiers in third-party integrations (like payment references or transaction IDs) and ensure they are indexed for O(1) lookups.
