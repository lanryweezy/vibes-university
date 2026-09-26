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

## 2026-08-30 - Missing SQLite Indices for Sorting by Created_at

**Learning:** Tables like `courses` and `blogs` are frequently queried and sorted by `created_at DESC` to show the most recent items. Without indices on these columns, SQLite performs a full table scan (`SCAN table`) and then sorts the entire result set in memory using a temporary B-tree (`USE TEMP B-TREE FOR ORDER BY`). This `O(N log N)` sorting process can become very slow as the number of rows increases, particularly when only the top few rows are needed (e.g., `LIMIT 3`).

**Action:** Added dedicated indices `idx_courses_created_at` and `idx_blogs_created_at` on the `created_at` columns in the `courses` and `blogs` tables respectively. In the future, actively look for columns used in `ORDER BY` operations combined with `LIMIT` on large tables, and create indices to enable faster `SCAN USING INDEX` operations and avoid in-memory sorting bottlenecks.
## 2024-03-24 - Missing Indexes on Frequently Grouped Columns
**Learning:** In SQLite, queries that use `GROUP BY column_name` or `WHERE column_name IN (...)` (such as analytics or reporting queries) can trigger full table scans if the column is not indexed, even if the primary key and foreign keys are. The `enrollments` table lacked an index on `course_type`, leading to slow analytics queries as data grows.
**Action:** Always verify that columns frequently used for aggregation (`GROUP BY`), filtering, or large `IN` clauses have appropriate indexes created during database initialization, especially for tables that grow rapidly like `enrollments`.

## 2026-09-01 - Replace Dynamic IN Clauses with SQL JOINs

**Learning:** The `teacher_dashboard`, `view_earnings`, and `manage_students` routes originally queried a teacher's courses, constructed a dynamic list of `IN ({placeholders})` in Python, and executed a secondary query to find related enrollments. This creates memory allocations for lists/strings in Python application memory and can scale poorly when the number of courses or enrollments grows (triggering N+1-style intermediate memory bottlenecks).
**Action:** Replaced the intermediate python-based dynamic string formatting and list lookups with a single efficient SQL query. By doing `JOIN courses c ON e.course_type = c.name WHERE c.teacher_id = ?`, the database natively handles the relation, maintaining code simplicity, drastically lowering application memory footprints, and providing the SQL optimizer full context for indexing.

## 2024-05-19 - [Subquery optimization in SQL to fix N+1 performance bottlenecks]
**Learning:** In SQLite, queries joining a large table (like `users` or `lessons`) with a detailed table (`enrollments` or `course_progress`) and then grouping by the main table's ID perform very poorly. The database creates a large intermediate table with all combinations before aggregating (an O(N*M) operation). This acts as a massive performance bottleneck on large datasets.
**Action:** Replace standard joined group-bys (e.g., `SELECT u.*, COUNT(e.id) ... FROM users u LEFT JOIN enrollments e ON u.id = e.user_id GROUP BY u.id`) with pre-aggregated subqueries (e.g., `SELECT u.*, e.enrollment_count ... FROM users u LEFT JOIN (SELECT user_id, COUNT(id) as enrollment_count ... FROM enrollments GROUP BY user_id) e ON u.id = e.user_id`). This aggregates the detail table once and then joins, reducing complexity to O(N). Always use `COALESCE(val, 0)` on the joined aggregates to ensure functional parity with the original grouped query.

## 2024-05-24 - Missing SQLite Indexes for Foreign Keys and Lookups
**Learning:** SQLite does not automatically index foreign keys (`courses.teacher_id`, `modules.course_id`) or columns frequently used for specific lookups (`enrollments.payment_reference`). Queries that filter or join by these columns perform full table scans without an explicit index, resulting in significant performance bottlenecks as the application scales.
**Action:** Always explicitly verify that foreign keys and lookup columns used in `WHERE` and `JOIN` clauses have explicit database indexes created during schema initialization in `utils/db_utils.py`.
