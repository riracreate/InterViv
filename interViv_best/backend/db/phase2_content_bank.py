"""Verified Phase 2 MCQ and SQL Problem Content Banks.

Approved distribution:
- 150 MCQs across 9 skills:
  * DBMS: 30 (12 easy, 12 medium, 6 hard)
  * System Design: 22 (9 easy, 9 medium, 4 hard)
  * Machine Learning: 22 (9 easy, 9 medium, 4 hard)
  * Computer Networks: 18 (7 easy, 7 medium, 4 hard)
  * DSA: 16 (6 easy, 7 medium, 3 hard)
  * Python: 14 (6 easy, 5 medium, 3 hard)
  * OOP: 10 (4 easy, 4 medium, 2 hard)
  * Operating Systems: 10 (4 easy, 4 medium, 2 hard)
  * HR/Professional Judgment: 8 (3 easy, 3 medium, 2 hard)
  Total: 60 easy, 60 medium, 30 hard = 150 questions.

- 30 SQL problems:
  * 10 easy, 12 medium, 8 hard = 30 problems.
  * 1 visible sample case + 2 hidden evaluation cases each = 90 cases.
  * Reference queries pass at 100% across all cases.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import (
    MCQQuestionRow,
    SQLProblemCaseRow,
    SQLProblemRow,
    SkillRow,
)

PHASE2_MCQ_BANK: list[dict[str, Any]] = [   {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'B+ tree leaves form a doubly linked list, enabling efficient range scans and sorted '
                       'traversals, unlike hash indexes which only support equality lookups.',
        'id': 'mcq_dbms_001',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'B+ trees efficiently support range queries and ordered scans because leaf '
                                        'nodes are linked in sequential order.'},
                            {   'id': 'b',
                                'text': 'B+ trees execute exact-match lookups in strictly O(1) time complexity.'},
                            {   'id': 'c',
                                'text': 'B+ trees require zero storage overhead on disk compared to the underlying '
                                        'table heap.'},
                            {'id': 'd', 'text': 'B+ trees avoid hash collisions by eliminating disk read operations.'}],
        'skill': 'DBMS',
        'stem': 'What is the primary operational advantage of a B+ tree index over a hash index in relational '
                'databases?',
        'sub_domain': 'indexing'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'A primary key constraint uniquely identifies each record in a table and automatically enforces '
                       'both uniqueness and non-nullability.',
        'id': 'mcq_dbms_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Foreign Key constraint'},
                            {'id': 'b', 'text': 'Primary Key constraint'},
                            {'id': 'c', 'text': 'Check constraint'},
                            {'id': 'd', 'text': 'Default constraint'}],
        'skill': 'DBMS',
        'stem': 'Which database constraint guarantees that every tuple in a table possesses a distinct non-null '
                'identifier?',
        'sub_domain': 'keys'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': "Atomicity ensures an 'all-or-nothing' execution model where partial transactions leave no "
                       'trace in the database state.',
        'id': 'mcq_dbms_003',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Isolation'},
                            {'id': 'b', 'text': 'Consistency'},
                            {'id': 'c', 'text': 'Atomicity'},
                            {'id': 'd', 'text': 'Durability'}],
        'skill': 'DBMS',
        'stem': 'Which ACID property guarantees that all operations within a transaction complete successfully or all '
                'their changes are rolled back?',
        'sub_domain': 'transactions'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Referential integrity uses foreign keys to ensure that relationships between tables remain '
                       'consistent and prevent orphaned records.',
        'id': 'mcq_dbms_004',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'User-defined integrity via Triggers only'},
                            {'id': 'b', 'text': 'Domain integrity via Check constraint'},
                            {'id': 'c', 'text': 'Entity integrity via Primary Key'},
                            {'id': 'd', 'text': 'Referential integrity via Foreign Key'}],
        'skill': 'DBMS',
        'stem': 'Which integrity mechanism enforces relational consistency between a child table column and a parent '
                'table primary key?',
        'sub_domain': 'relationships'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': '1NF requires that each column contain only atomic values and that the relation contains no '
                       'repeating groups or multivalued attributes.',
        'id': 'mcq_dbms_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'All attributes must contain atomic, indivisible values with no repeating '
                                        'groups.'},
                            {   'id': 'b',
                                'text': 'All non-key attributes must be fully functionally dependent on the entire '
                                        'primary key.'},
                            {   'id': 'c',
                                'text': 'Transitive dependencies between non-prime attributes must be eliminated.'},
                            {'id': 'd', 'text': 'Every functional dependency determinant must be a candidate key.'}],
        'skill': 'DBMS',
        'stem': 'What requirement characterizes First Normal Form (1NF) in relational schema design?',
        'sub_domain': 'normalization'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'INNER JOIN selects records that have matching values in both tables, filtering out '
                       'non-matching rows from both sides.',
        'id': 'mcq_dbms_006',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'LEFT OUTER JOIN'},
                            {'id': 'b', 'text': 'INNER JOIN'},
                            {'id': 'c', 'text': 'FULL OUTER JOIN'},
                            {'id': 'd', 'text': 'CROSS JOIN'}],
        'skill': 'DBMS',
        'stem': 'Which SQL JOIN returns exclusively the rows where matching values exist in both participating tables?',
        'sub_domain': 'querying'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'A clustered index organizes the physical storage order of the data pages on disk, meaning each '
                       'table can have at most one clustered index.',
        'id': 'mcq_dbms_007',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A clustered index stores pointers to rows rather than table data itself.'},
                            {'id': 'b', 'text': 'A table can possess up to 16 clustered indexes simultaneously.'},
                            {   'id': 'c',
                                'text': 'A clustered index dictates the physical sorting order of table rows on disk.'},
                            {'id': 'd', 'text': 'A clustered index is stored exclusively in RAM cache memory.'}],
        'skill': 'DBMS',
        'stem': 'What distinguishes a clustered index from a non-clustered index in a relational storage engine?',
        'sub_domain': 'indexing'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'DDL commands define and modify the schema structure of database objects, including tables, '
                       'indexes, and constraints.',
        'id': 'mcq_dbms_008',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Transaction Control Language (TCL)'},
                            {'id': 'b', 'text': 'Data Manipulation Language (DML)'},
                            {'id': 'c', 'text': 'Data Control Language (DCL)'},
                            {'id': 'd', 'text': 'Data Definition Language (DDL)'}],
        'skill': 'DBMS',
        'stem': 'Which SQL statement category includes commands such as CREATE, ALTER, and DROP?',
        'sub_domain': 'sql'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'A standard view is a virtual relation whose contents are dynamically computed by executing its '
                       'underlying query upon invocation.',
        'id': 'mcq_dbms_009',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A virtual table defined by a stored SELECT query without persisting '
                                        'duplicated row data.'},
                            {   'id': 'b',
                                'text': 'A physically materialized snapshot duplicated across cluster worker nodes.'},
                            {   'id': 'c',
                                'text': 'A temporary table created in tempdb that drops automatically upon session '
                                        'disconnect.'},
                            {'id': 'd', 'text': 'An append-only transaction log stream.'}],
        'skill': 'DBMS',
        'stem': 'What is the primary nature of a standard SQL VIEW in a relational database management system?',
        'sub_domain': 'views'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'WAL guarantees durability by appending all state modifications to durable non-volatile storage '
                       'prior to marking the transaction committed.',
        'id': 'mcq_dbms_010',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Periodic volatile memory dumps to operating system swap space.'},
                            {   'id': 'b',
                                'text': 'Write-Ahead Logging (WAL) flushed to stable storage before transaction commit '
                                        'confirmation.'},
                            {'id': 'c', 'text': 'Read-committed transaction isolation locks held in RAM.'},
                            {'id': 'd', 'text': 'Dynamic query recompilation at database startup.'}],
        'skill': 'DBMS',
        'stem': 'Which mechanism ensures the Durability property of committed transactions during sudden server power '
                'loss?',
        'sub_domain': 'recovery'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Foreign keys enforce referential integrity between tables, preventing orphan records and '
                       'ensuring that referenced entities exist.',
        'id': 'mcq_dbms_031',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Automatically convert single-node databases into multi-region clusters.'},
                            {   'id': 'b',
                                'text': 'Compress foreign language text strings into binary representations on disk.'},
                            {   'id': 'c',
                                'text': 'Ensure referential integrity by enforcing that a child column value must '
                                        'exist in a referenced parent table primary key.'},
                            {   'id': 'd',
                                'text': 'Execute cross-table analytical aggregation queries in strictly constant '
                                        'time.'}],
        'skill': 'DBMS',
        'stem': 'What is the primary role of a foreign key constraint in relational databases?',
        'sub_domain': 'referential_integrity'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Atomicity (all-or-nothing) ensures that if any statement in a transaction fails, the entire '
                       'transaction aborts and any partial mutations are rolled back.',
        'id': 'mcq_dbms_032',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Database reads are always served from high-speed CPU L1 cache memory.'},
                            {   'id': 'b',
                                'text': 'Transactions execute in strictly isolated hardware threads without context '
                                        'switching.'},
                            {'id': 'c', 'text': 'Committed data is replicated to at least three physical datacenters.'},
                            {   'id': 'd',
                                'text': 'All operations within a transaction complete successfully, or all changes are '
                                        'completely rolled back.'}],
        'skill': 'DBMS',
        'stem': 'What does the Atomicity property in ACID database transactions guarantee?',
        'sub_domain': 'transactions'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Read Committed prevents dirty reads by only reading committed rows, but permits non-repeatable '
                       'reads because rows read earlier can change upon subsequent reads.',
        'id': 'mcq_dbms_011',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Non-repeatable read: re-reading the same row returns modified values '
                                        'committed by another transaction.'},
                            {   'id': 'b',
                                'text': 'Dirty read: reading uncommitted data written by a concurrent transaction.'},
                            {   'id': 'c',
                                'text': "Dirty write: concurrent uncommitted transactions overwriting each other's "
                                        'uncommitted rows.'},
                            {'id': 'd', 'text': 'Cascading aborts caused by uncommitted dependency chains.'}],
        'skill': 'DBMS',
        'stem': 'Under the ANSI SQL Read Committed isolation level, what concurrency phenomenon remains possible '
                'during concurrent transaction execution?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': '3NF requires a relation to be in 2NF and contain no transitive functional dependencies of '
                       'non-prime attributes on candidate keys.',
        'id': 'mcq_dbms_012',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It is in 1NF and all non-key columns depend on part of a composite primary '
                                        'key.'},
                            {   'id': 'b',
                                'text': 'It is in 2NF and every non-prime attribute is non-transitively dependent on '
                                        'every candidate key.'},
                            {'id': 'c', 'text': 'Every multi-valued dependency is a functional dependency.'},
                            {'id': 'd', 'text': 'No candidate key contains more than a single column attribute.'}],
        'skill': 'DBMS',
        'stem': 'What condition must a relation satisfy to achieve Third Normal Form (3NF)?',
        'sub_domain': 'normalization'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'BCNF eliminates anomalies where a determinant in a functional dependency is not a candidate '
                       'key/superkey.',
        'id': 'mcq_dbms_013',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Every join operation must be lossless without preserving functional '
                                        'dependencies.'},
                            {   'id': 'b',
                                'text': 'For every functional dependency X -> Y, Y must belong to a prime attribute.'},
                            {   'id': 'c',
                                'text': 'For every non-trivial functional dependency X -> Y, X must be a superkey.'},
                            {'id': 'd', 'text': 'Composite candidate keys are strictly forbidden.'}],
        'skill': 'DBMS',
        'stem': 'What specific criterion defines Boyce-Codd Normal Form (BCNF) relative to standard 3NF?',
        'sub_domain': 'normalization'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'In 2PL, the shrinking phase permits releasing locks but strictly forbids acquiring new locks, '
                       'guaranteeing conflict serializability.',
        'id': 'mcq_dbms_014',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A transaction acquires additional locks only after verifying that deadlocks '
                                        'cannot occur.'},
                            {'id': 'b', 'text': 'A transaction must convert all shared locks into exclusive locks.'},
                            {   'id': 'c',
                                'text': 'A transaction must release all locks simultaneously at the moment of commit.'},
                            {   'id': 'd',
                                'text': 'A transaction may release locks, but cannot acquire any new locks once lock '
                                        'release begins.'}],
        'skill': 'DBMS',
        'stem': 'What rule governs the shrinking phase of the Two-Phase Locking (2PL) protocol?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'A covering index contains all attributes necessary to fulfill the query, allowing the engine '
                       'to satisfy the request directly from index pages.',
        'id': 'mcq_dbms_015',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'An index containing all columns referenced in the SELECT, WHERE, and JOIN '
                                        'clauses, eliminating table heap lookups.'},
                            {   'id': 'b',
                                'text': 'An index that indexes every column present in the underlying physical table.'},
                            {'id': 'c', 'text': 'A primary key index that covers all foreign key constraints.'},
                            {'id': 'd', 'text': 'A hash index mapped over all numeric columns in a table.'}],
        'skill': 'DBMS',
        'stem': 'What constitutes a covering index for an executing SELECT query?',
        'sub_domain': 'query_optimization'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Hash join builds an in-memory hash table on the smaller build relation and probes it via a '
                       'sequential scan of the probe relation, avoiding random I/O.',
        'id': 'mcq_dbms_016',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Nested Loop Join'},
                            {'id': 'b', 'text': 'Hash Join'},
                            {'id': 'c', 'text': 'Cartesian Product Scan'},
                            {'id': 'd', 'text': 'Index Scan Join'}],
        'skill': 'DBMS',
        'stem': 'When evaluating equi-joins over two large unsorted tables without existing indexes, which join '
                'algorithm typically minimizes random disk I/O?',
        'sub_domain': 'query_optimization'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Snapshot Isolation prevents dirty reads and lost updates on identical rows, but permits write '
                       'skew because transactions update distinct rows based on overlapping read snapshots.',
        'id': 'mcq_dbms_017',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Lost Update on the exact same row when first-committer-wins is enabled.'},
                            {'id': 'b', 'text': 'Dirty Read: transactions observing uncommitted row states.'},
                            {   'id': 'c',
                                'text': 'Write Skew: concurrent transactions read overlapping data sets and '
                                        'concurrently make disjoint updates violating integrity constraints.'},
                            {'id': 'd', 'text': 'Cascading rollbacks across multiple committed sessions.'}],
        'skill': 'DBMS',
        'stem': 'Which anomaly can emerge under Snapshot Isolation that cannot occur under true Serializable '
                'isolation?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'A deadlock in a Wait-For Graph corresponds directly to a directed cycle, where each '
                       'transaction in the cycle is waiting for a resource held by another.',
        'id': 'mcq_dbms_018',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'By monitoring operating system thread preemption queues.'},
                            {   'id': 'b',
                                'text': 'By checking if the total count of active transactions exceeds the configured '
                                        'lock pool capacity.'},
                            {   'id': 'c',
                                'text': 'By verifying whether shared locks outnumber exclusive locks across database '
                                        'tables.'},
                            {   'id': 'd',
                                'text': 'By detecting directed cycles within the graph where vertices represent '
                                        'transactions and edges represent lock dependencies.'}],
        'skill': 'DBMS',
        'stem': 'How does a database engine detect deadlocks among concurrent transactions using a Wait-For Graph?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Composite indexes observe the leftmost prefix rule; filtering on leading column A allows the '
                       'engine to seek and range scan on B.',
        'id': 'mcq_dbms_019',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'WHERE A = 10 AND B > 20'},
                            {'id': 'b', 'text': 'WHERE B = 20 AND C = 30'},
                            {'id': 'c', 'text': 'WHERE C = 30'},
                            {'id': 'd', 'text': 'WHERE B > 20'}],
        'skill': 'DBMS',
        'stem': 'Given a composite B-tree index on columns (A, B, C), which WHERE clause predicate leverages the index '
                'structure via range scan?',
        'sub_domain': 'indexing'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Checkpoints synchronize dirty in-memory pages with disk storage, establishing a safe horizon '
                       'before which log records need no recovery replay.',
        'id': 'mcq_dbms_020',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'To drop all inactive user sessions and reset transaction IDs to zero.'},
                            {   'id': 'b',
                                'text': 'To flush dirty buffer pool pages to disk, bounding the volume of log records '
                                        'to replay during crash recovery.'},
                            {'id': 'c', 'text': 'To convert row-oriented table heaps into columnar formats.'},
                            {'id': 'd', 'text': 'To recalculate table cardinality statistics for the query planner.'}],
        'skill': 'DBMS',
        'stem': 'What is the purpose of the checkpoint operation in write-ahead logging database engines?',
        'sub_domain': 'storage'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Read Committed prevents dirty reads by only reading committed rows. However, non-repeatable '
                       'reads (and phantom reads) can still occur if another transaction commits changes between two '
                       'reads.',
        'id': 'mcq_dbms_033',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Catastrophic loss of database transaction log files on clean shutdown.'},
                            {   'id': 'b',
                                'text': 'Dirty reads, where uncommitted changes from another transaction are read.'},
                            {   'id': 'c',
                                'text': 'Non-repeatable reads, where re-reading a row within the same transaction '
                                        'yields modified values committed by another transaction.'},
                            {   'id': 'd',
                                'text': 'Permanent deadlocks between read-only SELECT queries on empty tables.'}],
        'skill': 'DBMS',
        'stem': 'Which concurrency anomaly can still occur under the standard Read Committed isolation level?',
        'sub_domain': 'concurrency_control'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Connection pools maintain a warm set of active connections, eliminating TCP handshake and '
                       'authentication overhead for each individual incoming HTTP request.',
        'id': 'mcq_dbms_034',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Compressing SQL query strings into MD5 hashes before transmission.'},
                            {   'id': 'b',
                                'text': 'Allowing client web browsers to execute raw SQL statements directly without '
                                        'backend authentication.'},
                            {   'id': 'c',
                                'text': 'Eliminating the need to define primary keys on relational database tables.'},
                            {   'id': 'd',
                                'text': 'Reusing pre-established TCP database connections, avoiding the latency and '
                                        'resource overhead of repeated connection handshakes.'}],
        'skill': 'DBMS',
        'stem': 'What is the primary performance benefit of implementing a database connection pool in a web backend?',
        'sub_domain': 'connection_management'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'ARIES operates in three distinct phases: Analysis determines dirty pages and active '
                       'transactions, Redo repeats history, and Undo rolls back active transactions.',
        'id': 'mcq_dbms_021',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Analysis, Redo, and Undo'},
                            {'id': 'b', 'text': 'Scan, Filter, and Aggregate'},
                            {'id': 'c', 'text': 'Validate, Write, and Purge'},
                            {'id': 'd', 'text': 'Snapshot, Replay, and Flush'}],
        'skill': 'DBMS',
        'stem': 'What are the three sequential execution phases of the ARIES crash recovery algorithm?',
        'sub_domain': 'recovery'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'Strict 2PL retains all exclusive locks until transaction completion, ensuring dirty values are '
                       'never exposed to concurrent transactions and preventing cascading rollbacks.',
        'id': 'mcq_dbms_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It completely eliminates all deadlocks without requiring timeouts or cycle '
                                        'detection.'},
                            {   'id': 'b',
                                'text': 'It holds exclusive locks until transaction commit or abort, preventing '
                                        'cascading aborts.'},
                            {   'id': 'c',
                                'text': 'It allows transactions to read uncommitted rows safely without locking.'},
                            {'id': 'd', 'text': 'It eliminates the need for write-ahead logging on storage devices.'}],
        'skill': 'DBMS',
        'stem': 'What property makes Strict Two-Phase Locking (Strict 2PL) widely preferred over basic 2PL in '
                'commercial database engines?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': 'In an index-range-locking implementation, record locks alone leave insertion gaps '
                       'unprotected. Next-key or range locks cover both matching records and the adjacent key gaps, '
                       'so a concurrent insert into the scanned predicate range must wait or conflict.',
        'id': 'mcq_dbms_023',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Record locks only on rows that already matched the predicate when the scan '
                                        'began.'},
                            {   'id': 'b',
                                'text': 'A repeatable snapshot with no range-conflict tracking for concurrent '
                                        'inserts.'},
                            {   'id': 'c',
                                'text': 'Next-key or range locks covering matching index records and the gaps where '
                                        'new matching keys could be inserted.'},
                            {   'id': 'd',
                                'text': 'A commit-time predicate recheck that never blocks or aborts a concurrent '
                                        'inserter.'}],
        'skill': 'DBMS',
        'stem': 'In a lock-based DBMS that implements Serializable isolation with index-range locking, which mechanism '
                'prevents a concurrent transaction from inserting phantom rows into a scanned predicate range?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': 'After the typically overlapping Level-0 files, leveled compaction generally maintains '
                       'non-overlapping key ranges within each later level. This lowers read and space amplification, '
                       'but repeated movement and rewriting across levels increases write amplification.',
        'id': 'mcq_dbms_024',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Size-Tiered Compaction uses zero auxiliary disk space during compaction '
                                        'runs.'},
                            {   'id': 'b',
                                'text': 'Leveled Compaction executes writes in memory without persisting write-ahead '
                                        'logs.'},
                            {   'id': 'c',
                                'text': 'Size-Tiered Compaction guarantees strictly O(1) point lookups across all '
                                        'levels.'},
                            {   'id': 'd',
                                'text': 'Leveled Compaction provides lower read amplification and lower space '
                                        'amplification at the expense of higher write amplification.'}],
        'skill': 'DBMS',
        'stem': 'In Log-Structured Merge (LSM) tree architectures, what trade-off distinguishes Leveled Compaction '
                'from Size-Tiered Compaction?',
        'sub_domain': 'storage'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'Standard VACUUM (and autovacuum) scans the relation, removes dead row versions whose '
                       'transaction horizons have passed, and marks that space reusable within the same relation. '
                       'Only VACUUM FULL rewrites the relation and can return space to the operating system.',
        'id': 'mcq_dbms_025',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'VACUUM processing'},
                            {'id': 'b', 'text': 'Write-Ahead Log checkpointing'},
                            {'id': 'c', 'text': 'Buffer pool page eviction'},
                            {'id': 'd', 'text': 'Transaction rollback journal truncation'}],
        'skill': 'DBMS',
        'stem': 'In PostgreSQL MVCC, which maintenance process marks space occupied by dead tuples as reusable '
                'within the same relation?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'External merge sort reserves 1 buffer page for the output block and uses the remaining B - 1 '
                       'buffer pages as input buffers for B - 1 runs.',
        'id': 'mcq_dbms_026',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'B runs'},
                            {'id': 'b', 'text': 'B - 1 runs'},
                            {'id': 'c', 'text': 'B / 2 runs'},
                            {'id': 'd', 'text': '2 runs'}],
        'skill': 'DBMS',
        'stem': 'In external merge sort with B buffer pages available, how many sorted runs can be merged together in '
                'a single pass during the merge phase?',
        'sub_domain': 'algorithms'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'A CDN distributes and caches static assets (images, CSS, JS, video) across edge servers '
                       'globally, reducing origin server load and client latency.',
        'id': 'mcq_sd_001',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Execute backend database write transactions directly.'},
                            {'id': 'b', 'text': 'Generate relational database schemas automatically.'},
                            {   'id': 'c',
                                'text': 'Cache static assets geographically closer to users to reduce latency.'},
                            {'id': 'd', 'text': 'Compile client-side frontend code into bytecode.'}],
        'skill': 'System Design',
        'stem': 'What is the primary function of a Content Delivery Network (CDN) in web architecture?',
        'sub_domain': 'caching'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Horizontal scaling (scaling out) adds more commodity nodes to a cluster, enabling growth '
                       "beyond the physical limits of a single machine's CPU and RAM.",
        'id': 'mcq_sd_002',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Horizontal scaling ensures every server shares the exact same physical CPU '
                                        'socket.'},
                            {   'id': 'b',
                                'text': 'Horizontal scaling eliminates the need for network communication between '
                                        'nodes.'},
                            {'id': 'c', 'text': 'Horizontal scaling guarantees strictly zero operational complexity.'},
                            {   'id': 'd',
                                'text': 'Horizontal scaling adds more machines, allowing continuous expansion beyond '
                                        'single-machine hardware limits.'}],
        'skill': 'System Design',
        'stem': 'What is the key advantage of horizontal scaling over vertical scaling?',
        'sub_domain': 'load_balancing'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'A reverse proxy sits in front of web servers and forwards client requests to backend services, '
                       'handling SSL termination, compression, caching, and routing.',
        'id': 'mcq_sd_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Act as an intermediary that routes client requests, terminates SSL, and '
                                        'balances load across backend servers.'},
                            {'id': 'b', 'text': 'Directly execute complex SQL analytical aggregation queries.'},
                            {'id': 'c', 'text': 'Serve as a persistent hardware storage medium for user databases.'},
                            {'id': 'd', 'text': 'Manage virtual memory paging inside the Linux kernel.'}],
        'skill': 'System Design',
        'stem': 'Which capability is primarily provided by a reverse proxy in modern web systems?',
        'sub_domain': 'load_balancing'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Stateless application servers store session state externally (e.g. in Redis or a DB), enabling '
                       'any server to handle any incoming request and allowing simple dynamic scaling.',
        'id': 'mcq_sd_004',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Stateless servers store all user sessions entirely in local server RAM '
                                        'without external storage.'},
                            {   'id': 'b',
                                'text': 'Any request can be routed to any server instance, simplifying horizontal '
                                        'autoscaling.'},
                            {'id': 'c', 'text': 'Stateless servers reduce database read performance.'},
                            {   'id': 'd',
                                'text': 'Stateless servers restrict clients to using single persistent socket '
                                        'connections.'}],
        'skill': 'System Design',
        'stem': 'Why do distributed architectures prioritize stateless application servers?',
        'sub_domain': 'statelessness'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Round-robin distributes incoming requests cyclically across a pool of backend servers in '
                       'sequential order.',
        'id': 'mcq_sd_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It calculates a cryptographic hash of the client payload before routing.'},
                            {'id': 'b', 'text': 'It always routes requests to the server with the lowest IP address.'},
                            {   'id': 'c',
                                'text': 'It assigns requests sequentially across the list of available healthy '
                                        'servers.'},
                            {   'id': 'd',
                                'text': 'It routes all traffic exclusively to one primary server until it crashes.'}],
        'skill': 'System Design',
        'stem': 'How does a standard round-robin load balancer allocate incoming network requests?',
        'sub_domain': 'load_balancing'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'In write-through caching, write operations write to the cache and the permanent database store '
                       'synchronously, ensuring strong cache consistency at the cost of higher write latency.',
        'id': 'mcq_sd_006',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Data is written directly to disk bypassing both memory and cache tiers.'},
                            {   'id': 'b',
                                'text': 'Data is written only to the database, and the cache is updated lazily on '
                                        'subsequent reads.'},
                            {   'id': 'c',
                                'text': 'Data is written to the cache first and flushed to the database asynchronously '
                                        'after a delay.'},
                            {   'id': 'd',
                                'text': 'Data is written simultaneously to the cache and the primary database before '
                                        'confirming success.'}],
        'skill': 'System Design',
        'stem': 'Which statement describes the write-through caching strategy?',
        'sub_domain': 'caching'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Read replicas copy changes from the primary database and serve read-only queries, reducing CPU '
                       'and I/O pressure on the primary writer node.',
        'id': 'mcq_sd_007',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Distribute read query load away from the primary database node.'},
                            {   'id': 'b',
                                'text': 'Allow write queries to execute across all replicas without synchronization.'},
                            {'id': 'c', 'text': 'Eliminate the need for primary database backup snapshots.'},
                            {'id': 'd', 'text': 'Enforce continuous schema migrations on the client browser.'}],
        'skill': 'System Design',
        'stem': 'What is the primary benefit of deploying read replicas in a relational database cluster?',
        'sub_domain': 'replication'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Message queues decouple producers and consumers, enabling asynchronous work processing, '
                       'smoothing out traffic bursts, and enhancing fault isolation.',
        'id': 'mcq_sd_008',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'It forces synchronous blocking calls for every request.'},
                            {   'id': 'b',
                                'text': 'It enables asynchronous communication and buffers traffic spikes between '
                                        'producer and consumer.'},
                            {'id': 'c', 'text': 'It converts relational database tables into binary executable files.'},
                            {   'id': 'd',
                                'text': 'It replaces network routers by handling physical Ethernet packet switching.'}],
        'skill': 'System Design',
        'stem': 'What is the primary architectural advantage of using a message queue between decoupled microservices?',
        'sub_domain': 'messaging'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Heartbeats are periodic ping messages exchanged between cluster nodes to monitor health and '
                       'trigger failover if a node stops responding.',
        'id': 'mcq_sd_009',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Encrypt all incoming client HTTP payloads using TLS certificates.'},
                            {'id': 'b', 'text': 'Compress database transaction logs onto physical storage media.'},
                            {   'id': 'c',
                                'text': 'Periodically confirm node availability and detect server failures promptly.'},
                            {   'id': 'd',
                                'text': 'Calculate the financial operational cost of running cloud instances.'}],
        'skill': 'System Design',
        'stem': 'What is the operational purpose of heartbeat signals in distributed server clusters?',
        'sub_domain': 'high_availability'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'In consistent hashing, nodes and keys map to a logical ring; adding a node only requires '
                       'migrating keys from the immediate successor node, moving on average K/N keys.',
        'id': 'mcq_sd_010',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'It stores all keys on a centralized master index without hashing.'},
                            {   'id': 'b',
                                'text': 'Every key across the entire cluster is uniformly rehashed to a new physical '
                                        'server.'},
                            {   'id': 'c',
                                'text': 'It copies all data partitions to every node simultaneously via broadcasting.'},
                            {   'id': 'd',
                                'text': 'Only keys falling between the new node and its immediate predecessor on the '
                                        'ring are remapped.'}],
        'skill': 'System Design',
        'stem': 'How does consistent hashing minimize data migration when a new node joins a storage cluster?',
        'sub_domain': 'partitioning'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'An AP system prioritizes availability over strict consistency; during a network partition, '
                       'each isolated partition accepts requests, accepting that replicas may temporarily diverge.',
        'id': 'mcq_sd_011',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It continues processing reads and writes, potentially returning stale data '
                                        'from isolated partitions.'},
                            {   'id': 'b',
                                'text': 'It immediately blocks all read and write requests until the partition '
                                        'resolves.'},
                            {   'id': 'c',
                                'text': 'It guarantees linearizable consistency across all nodes at all times.'},
                            {   'id': 'd',
                                'text': 'It terminates all active database connections and deletes partitioned '
                                        'records.'}],
        'skill': 'System Design',
        'stem': 'Under the CAP theorem, how does an AP (Availability and Partition tolerance) system behave during a '
                'network split?',
        'sub_domain': 'consistency'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Token Bucket accumulates tokens up to its capacity to support bursty traffic, while Leaky '
                       'Bucket processes requests at an unvarying, smoothed outflow rate.',
        'id': 'mcq_sd_012',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Token Bucket drops all requests during bursts, whereas Leaky Bucket queues '
                                        'infinite requests.'},
                            {   'id': 'b',
                                'text': 'Token Bucket allows short traffic bursts up to bucket capacity, whereas Leaky '
                                        'Bucket smooths output to a constant rate.'},
                            {   'id': 'c',
                                'text': 'Token Bucket operates exclusively at the transport layer, whereas Leaky '
                                        'Bucket is an application layer protocol.'},
                            {   'id': 'd',
                                'text': 'Token Bucket requires persistent disk writes for each token calculation.'}],
        'skill': 'System Design',
        'stem': 'What is the primary operational difference between the Token Bucket and Leaky Bucket rate-limiting '
                'algorithms?',
        'sub_domain': 'rate_limiting'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Sequential timestamps alone route all current writes to the single newest shard. Combining an '
                       'entity ID with hashing distributes writes evenly across physical shards.',
        'id': 'mcq_sd_013',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Directing all writes to a single static shard until it reaches maximum disk '
                                        'capacity.'},
                            {'id': 'b', 'text': 'Sharding directly on a monotonically increasing timestamp column.'},
                            {   'id': 'c',
                                'text': 'Hashing a compound key combining an entity identifier with a coarse time '
                                        'bucket.'},
                            {   'id': 'd',
                                'text': 'Using an unindexed auto-incrementing integer as the partition boundary.'}],
        'skill': 'System Design',
        'stem': 'Which sharding key strategy most effectively avoids hotspotting when write traffic exhibits '
                'sequential timestamps?',
        'sub_domain': 'partitioning'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'A Bloom filter guarantees no false negatives: a negative lookup confirms the key was never '
                       'inserted. Positive lookups can have a controllable false positive rate.',
        'id': 'mcq_sd_014',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Deterministic deletion of arbitrary items without bit degradation.'},
                            {   'id': 'b',
                                'text': 'Zero false positives: if the filter reports an element is present, it is '
                                        'guaranteed present.'},
                            {'id': 'c', 'text': 'Exact retrieval of original keys from the underlying bit array.'},
                            {   'id': 'd',
                                'text': 'Zero false negatives: if the filter reports an element is absent, it is '
                                        'definitively absent.'}],
        'skill': 'System Design',
        'stem': 'Which probabilistic property is guaranteed by a standard Bloom Filter data structure?',
        'sub_domain': 'caching'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Idempotency keys allow the server to identify repeated attempts of the same financial '
                       'mutation; if a request with the same key was already processed, the saved response is returned '
                       'without executing the charge again.',
        'id': 'mcq_sd_015',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Prevent duplicate charges when a client retries a request after a network '
                                        'timeout.'},
                            {'id': 'b', 'text': 'Encrypt credit card numbers using symmetric AES-256 keys.'},
                            {'id': 'c', 'text': 'Authorize administrative users to delete user payment records.'},
                            {'id': 'd', 'text': 'Compress the HTTP request payload into gzip format.'}],
        'skill': 'System Design',
        'stem': 'What is the primary role of an Idempotency-Key header in payment processing APIs?',
        'sub_domain': 'api_design'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'The Saga pattern orchestrates distributed workflows as a series of local transactions. If a '
                       'step fails, the saga executes compensating transactions to revert prior actions.',
        'id': 'mcq_sd_016',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'By holding global database row locks across all participating services until '
                                        'commit.'},
                            {   'id': 'b',
                                'text': 'Through a sequence of local transactions where failures trigger explicit '
                                        'compensating transactions.'},
                            {   'id': 'c',
                                'text': 'By relying on synchronous Two-Phase Commit coordinators across all network '
                                        'boundaries.'},
                            {   'id': 'd',
                                'text': 'By executing all distributed operations on a single unified database '
                                        'server.'}],
        'skill': 'System Design',
        'stem': 'How does the Saga pattern manage distributed transaction consistency across microservices?',
        'sub_domain': 'consistency'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Write-ahead logging records mutations sequentially to non-volatile storage before applying '
                       'them in memory. On crash, the engine replays the log to restore state.',
        'id': 'mcq_sd_017',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Replace the need for primary and secondary indexes in database tables.'},
                            {   'id': 'b',
                                'text': 'Generate analytical business intelligence dashboards directly from raw socket '
                                        'packets.'},
                            {   'id': 'c',
                                'text': 'Append changes sequentially to durable storage before modifying in-memory '
                                        'data structures, ensuring crash recovery.'},
                            {'id': 'd', 'text': 'Store user authentication passwords in plaintext for fast lookup.'}],
        'skill': 'System Design',
        'stem': 'What is the core purpose of a Write-Ahead Log (WAL) in distributed storage engines?',
        'sub_domain': 'storage'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Mutex locking (or probabilistic early expiration) ensures only one process fetches from the DB '
                       'to refresh an expired hot key, preventing database overload from thousands of concurrent '
                       'misses.',
        'id': 'mcq_sd_018',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Routing all read requests directly to the database during peak hours.'},
                            {'id': 'b', 'text': 'Setting cache TTL to zero for all high-traffic keys.'},
                            {'id': 'c', 'text': 'Evicting all keys simultaneously across the entire cache cluster.'},
                            {   'id': 'd',
                                'text': 'Using mutual exclusion locks so only one request regenerates the cached entry '
                                        'while others wait or read stale data.'}],
        'skill': 'System Design',
        'stem': 'Which technique effectively mitigates a cache stampede (thundering herd) when a popular key expires?',
        'sub_domain': 'caching'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'Joint consensus requires a quorum under both the old and new configurations while membership '
                       'is changing. The overlapping quorum requirement prevents disjoint groups from independently '
                       'committing entries or electing leaders before the transition to the new configuration commits.',
        'id': 'mcq_sd_019',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A transition entry is committed only with quorums from both the old and new '
                                        'configurations, preserving quorum overlap during the change.'},
                            {   'id': 'b',
                                'text': 'The leader activates the new configuration locally before replication, while '
                                        'followers continue voting under whichever configuration they last observed.'},
                            {   'id': 'c',
                                'text': 'The old configuration is discarded as soon as every new server has received '
                                        'the latest snapshot, without committing a configuration entry.'},
                            {   'id': 'd',
                                'text': 'Election timeouts are disabled for the duration of the change so only the '
                                        'current leader can determine the final membership.'}],
        'skill': 'System Design',
        'stem': 'Why does Raft use joint consensus rather than switching directly from an old cluster membership to a '
                'new membership?',
        'sub_domain': 'consensus'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'Lamport clocks preserve happened-before in one direction: if A happened before B, then L(A) is '
                       'less than L(B), but the reverse implication does not hold. A separate tie-break rule can extend '
                       'Lamport timestamps to a total order. Vector-clock component comparisons distinguish causal '
                       'precedence from concurrency because concurrent vectors are incomparable.',
        'id': 'mcq_sd_020',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Vector Clocks require strictly less network bandwidth than scalar integers.'},
                            {   'id': 'b',
                                'text': 'Vector-clock comparisons distinguish causal precedence from concurrency, '
                                        'whereas comparing scalar Lamport timestamps alone cannot tell those cases '
                                        'apart.'},
                            {   'id': 'c',
                                'text': 'Vector Clocks rely on perfectly synchronized physical atomic clocks like GPS '
                                        'receivers.'},
                            {   'id': 'd',
                                'text': 'Vector Clocks eliminate the need to store data replicas on different nodes.'}],
        'skill': 'System Design',
        'stem': 'What is the primary advantage of Vector Clocks over scalar Lamport Timestamps in multi-master '
                'distributed databases?',
        'sub_domain': 'consistency'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': 'A state-based CRDT evolves monotonically in a join-semilattice, and merge computes the least '
                       'upper bound. That merge is associative, commutative, and idempotent, so duplicated or reordered '
                       'state deliveries still converge.',
        'id': 'mcq_sd_021',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Replica states form a total order, and merge always selects the state with the '
                                        'largest physical timestamp.'},
                            {   'id': 'b',
                                'text': 'Merge is associative and commutative but intentionally not idempotent, so '
                                        'receiving the same state twice records both updates.'},
                            {   'id': 'c',
                                'text': 'Replica states form a join-semilattice, updates move monotonically upward, and '
                                        'merge computes an associative, commutative, idempotent least upper bound.'},
                            {   'id': 'd',
                                'text': 'Concurrent operations commute when delivered exactly once in causal order, '
                                        'without requiring a state-merge semilattice.'}],
        'skill': 'System Design',
        'stem': 'For a state-based (convergent) CRDT, which algebraic structure and update rule are sufficient for '
                'replicas to converge despite duplicated or reordered state delivery?',
        'sub_domain': 'consistency'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': 'Twitter Snowflake assigns bit segments: high bits for epoch-relative timestamp (providing '
                       'sortability), middle bits for machine/datacenter ID (providing uniqueness across nodes), and '
                       'low bits for a per-millisecond sequence counter.',
        'id': 'mcq_sd_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Querying a single centralized Redis counter through synchronous RPC for every '
                                        'ID.'},
                            {   'id': 'b',
                                'text': 'Executing an atomic database auto-increment query over a cross-region '
                                        'consensus quorum.'},
                            {   'id': 'c',
                                'text': 'Generating random 128-bit UUIDs and truncating them to 64 bits using '
                                        'SHA-256.'},
                            {   'id': 'd',
                                'text': 'Bit-packing a millisecond timestamp, a worker node ID, and a local '
                                        'per-millisecond sequence counter.'}],
        'skill': 'System Design',
        'stem': 'How does a decentralized Snowflake-style ID generator produce roughly chronological 64-bit unique '
                'identifiers without coordination?',
        'sub_domain': 'id_generation'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Supervised learning uses labelled pairs (x, y) where the algorithm learns a mapping function '
                       'from input features to target labels.',
        'id': 'mcq_ml_001',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Supervised learning trains models using explicit ground-truth input-output '
                                        'target labels.'},
                            {'id': 'b', 'text': 'Supervised learning requires strictly zero training data samples.'},
                            {'id': 'c', 'text': 'Supervised learning can only process unlabelled clustering datasets.'},
                            {   'id': 'd',
                                'text': 'Supervised learning always runs on graphical processing units (GPUs).'}],
        'skill': 'Machine Learning',
        'stem': 'What is the primary characteristic that distinguishes supervised learning from unsupervised learning?',
        'sub_domain': 'supervised_learning'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Overfitting occurs when a model memorizes noise and specific patterns in the training data, '
                       'achieving low training error but failing to generalize to validation or test data.',
        'id': 'mcq_ml_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Equal and low accuracy across both training and validation datasets.'},
                            {   'id': 'b',
                                'text': 'High accuracy on the training dataset paired with poor generalization on '
                                        'unseen validation data.'},
                            {'id': 'c', 'text': 'Extremely fast inference latency on embedded mobile hardware.'},
                            {   'id': 'd',
                                'text': 'Total convergence of training loss to zero on every random initialization.'}],
        'skill': 'Machine Learning',
        'stem': 'What indicates that a machine learning model is suffering from overfitting?',
        'sub_domain': 'model_evaluation'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Precision measures the proportion of positive predictions that were correct: TP / (TP + FP). '
                       'Recall is TP / (TP + FN).',
        'id': 'mcq_ml_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'True Negatives divided by the total number of evaluation samples (TN / '
                                        'Total).'},
                            {   'id': 'b',
                                'text': 'True Positives divided by the sum of True Positives and False Negatives (TP / '
                                        '(TP + FN)).'},
                            {   'id': 'c',
                                'text': 'True Positives divided by the sum of True Positives and False Positives (TP / '
                                        '(TP + FP)).'},
                            {'id': 'd', 'text': 'False Positives divided by True Positives (FP / TP).'}],
        'skill': 'Machine Learning',
        'stem': 'In binary classification, what is the mathematical formula for Precision?',
        'sub_domain': 'evaluation_metrics'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'L2 regularization adds lambda * sum(w_i^2) to the loss function, penalizing large weights and '
                       'shrinking them continuously toward zero to reduce model variance.',
        'id': 'mcq_ml_004',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It converts continuous regression outputs into discrete categorical classes.'},
                            {   'id': 'b',
                                'text': 'It forces exactly half of the feature weights to become absolute zero.'},
                            {'id': 'c', 'text': 'It increases the variance of predictions on the test set.'},
                            {   'id': 'd',
                                'text': 'It shrinks weight magnitudes smoothly toward zero by adding a squared weight '
                                        'penalty to the loss.'}],
        'skill': 'Machine Learning',
        'stem': 'What is the primary effect of L2 regularization (Ridge regression) on linear model coefficients?',
        'sub_domain': 'regularization'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'The learning rate (eta) scales the gradient step size: w_new = w_old - eta * grad(L). A small '
                       'rate causes slow convergence; a large rate can cause divergence.',
        'id': 'mcq_ml_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It scales the step size taken in the direction of the negative gradient '
                                        'during weight updates.'},
                            {'id': 'b', 'text': 'It dictates the number of layers in a convolutional neural network.'},
                            {   'id': 'c',
                                'text': 'It determines the physical number of CPU cores allocated for training.'},
                            {'id': 'd', 'text': 'It sets the maximum depth of a classification decision tree.'}],
        'skill': 'Machine Learning',
        'stem': 'What is the primary role of the learning rate hyperparameter in gradient descent?',
        'sub_domain': 'optimization'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'The validation set guides model selection and hyperparameter tuning. The test set is evaluated '
                       'only once at the end to provide an unbiased estimate of generalization error.',
        'id': 'mcq_ml_006',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'To provide extra training labels for semi-supervised clustering algorithms.'},
                            {   'id': 'b',
                                'text': 'To tune hyperparameters and perform model selection without biasing the final '
                                        'unbiased performance assessment on the test set.'},
                            {'id': 'c', 'text': 'To store backup copies of raw input feature vectors on disk.'},
                            {'id': 'd', 'text': 'To format tabular data into relational SQL database tables.'}],
        'skill': 'Machine Learning',
        'stem': 'Why is a validation dataset held out separately from the final test dataset?',
        'sub_domain': 'model_evaluation'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'A False Negative occurs when the true class is positive (patient has disease) but the '
                       'classifier predicts negative (healthy), which is critical in healthcare.',
        'id': 'mcq_ml_007',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'A healthy patient is correctly classified as healthy.'},
                            {'id': 'b', 'text': 'A healthy patient is classified as having cancer.'},
                            {'id': 'c', 'text': 'A patient who has cancer is classified as healthy.'},
                            {'id': 'd', 'text': 'A patient with cancer is correctly classified as having cancer.'}],
        'skill': 'Machine Learning',
        'stem': 'In a cancer screening diagnostic model, what does a False Negative represent?',
        'sub_domain': 'evaluation_metrics'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'K-Means minimizes inertia (within-cluster sum of squares): sum_{i=1}^k sum_{x in S_i} ||x - '
                       'mu_i||^2.',
        'id': 'mcq_ml_008',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'The determinant of the feature correlation matrix.'},
                            {'id': 'b', 'text': 'The total number of input features in the tabular dataset.'},
                            {   'id': 'c',
                                'text': 'The cross-entropy loss between predicted and actual class probability '
                                        'distributions.'},
                            {   'id': 'd',
                                'text': 'Within-cluster sum of squared Euclidean distances between points and their '
                                        'assigned cluster centroid.'}],
        'skill': 'Machine Learning',
        'stem': 'What objective function is minimized by the standard K-Means clustering algorithm?',
        'sub_domain': 'unsupervised_learning'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Gini Impurity = 1 - sum(p_i^2). When all samples belong to a single class (p_1 = 1.0), Gini '
                       'Impurity is 1 - 1.0 = 0.0, indicating maximum purity.',
        'id': 'mcq_ml_009',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'The node is completely pure, containing samples from only one class.'},
                            {   'id': 'b',
                                'text': 'The node contains an equal distribution across all possible target classes.'},
                            {'id': 'c', 'text': 'The node has zero training samples assigned to it.'},
                            {'id': 'd', 'text': 'The tree has reached its maximum allowed pruning depth.'}],
        'skill': 'Machine Learning',
        'stem': 'What does a Gini Impurity value of 0.0 indicate for a candidate node in a classification tree?',
        'sub_domain': 'decision_trees'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': "The maximum derivative of the sigmoid function sigma'(z) is 0.25 (at z=0). By the chain rule, "
                       'multiplying terms <= 0.25 across deep layers shrinks gradients toward zero.',
        'id': 'mcq_ml_010',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Its outputs can exceed positive infinity during standard forward passes.'},
                            {   'id': 'b',
                                'text': 'Its derivative peaks at 0.25, causing backpropagated gradients to diminish '
                                        'exponentially across multiple layers.'},
                            {'id': 'c', 'text': 'It cannot be differentiated with respect to input weights.'},
                            {'id': 'd', 'text': 'It forces all hidden layer activations to strictly equal zero.'}],
        'skill': 'Machine Learning',
        'stem': 'Why does using the sigmoid activation function in deep multilayer networks often cause the vanishing '
                'gradient problem?',
        'sub_domain': 'deep_learning'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'ROC-AUC evaluates ranking quality across all possible thresholds; mathematically it equals the '
                       'probability that a random positive instance is scored higher than a random negative instance.',
        'id': 'mcq_ml_011',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'The ratio of true positive rate to false negative rate at the point of '
                                        'maximum profit.'},
                            {   'id': 'b',
                                'text': 'The accuracy of the model evaluated strictly at a classification threshold of '
                                        '0.5.'},
                            {   'id': 'c',
                                'text': 'The probability that the model ranks a randomly chosen positive sample higher '
                                        'than a randomly chosen negative sample.'},
                            {   'id': 'd',
                                'text': 'The percentage of feature variance captured by the first principal '
                                        'component.'}],
        'skill': 'Machine Learning',
        'stem': 'How is the Area Under the Receiver Operating Characteristic (ROC-AUC) curve interpreted for binary '
                'classification?',
        'sub_domain': 'evaluation_metrics'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Random Forests combine bootstrap sampling (bagging) with random feature sub-selection at each '
                       'split, decorrelating the individual trees so their average has substantially lower variance.',
        'id': 'mcq_ml_012',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Sharing identical node split thresholds across every tree in the forest.'},
                            {   'id': 'b',
                                'text': 'Sequentially fitting each tree to the residual errors of prior trees with '
                                        'gradient descent.'},
                            {   'id': 'c',
                                'text': 'Pruning all trees down to depth 1 (decision stumps) before averaging.'},
                            {   'id': 'd',
                                'text': 'Bootstrap aggregation (bagging) of training data combined with random feature '
                                        'subset selection at each split.'}],
        'skill': 'Machine Learning',
        'stem': 'Which combination of techniques allows Random Forests to achieve lower variance than individual '
                'decision trees?',
        'sub_domain': 'ensemble_methods'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Batch Normalization normalizes activation distributions within each mini-batch, reducing '
                       'internal covariate shift, smoothing the optimization landscape, and accelerating convergence.',
        'id': 'mcq_ml_013',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Normalizing layer inputs by mini-batch mean and variance, stabilizing '
                                        'training and allowing higher learning rates.'},
                            {'id': 'b', 'text': 'Permanently setting all bias parameters in linear layers to zero.'},
                            {   'id': 'c',
                                'text': 'Sorting incoming training samples in ascending order of target values.'},
                            {   'id': 'd',
                                'text': 'Replacing backpropagation with stochastic genetic algorithm updates.'}],
        'skill': 'Machine Learning',
        'stem': 'What is the primary operational effect of Batch Normalization during deep neural network training?',
        'sub_domain': 'deep_learning'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'SMOTE creates synthetic samples by interpolating between neighboring minority instances in '
                       'feature space: x_new = x_i + lambda * (x_zi - x_i), avoiding exact duplicate overfitting.',
        'id': 'mcq_ml_014',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Randomly duplicating identical minority samples with replacement.'},
                            {   'id': 'b',
                                'text': 'Synthesizing new minority instances along line segments connecting existing '
                                        'minority k-nearest neighbors.'},
                            {   'id': 'c',
                                'text': 'Deleting majority class samples until both classes have identical sample '
                                        'counts.'},
                            {'id': 'd', 'text': 'Inverting the sign of majority class feature vectors.'}],
        'skill': 'Machine Learning',
        'stem': 'How does the Synthetic Minority Over-sampling Technique (SMOTE) address severe class imbalance?',
        'sub_domain': 'feature_engineering'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Adam maintains exponentially decaying running averages of the first moment (mean of gradients) '
                       'and second moment (uncentered variance of gradients), with bias correction for initialization.',
        'id': 'mcq_ml_015',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Keeping learning rates fixed and constant throughout the entire training '
                                        'process.'},
                            {   'id': 'b',
                                'text': 'Computing the exact inverse Hessian matrix using second-order Newton-Raphson '
                                        'iterations.'},
                            {   'id': 'c',
                                'text': 'Combining exponentially decaying averages of past gradients (momentum) and '
                                        'past squared gradients (adaptive learning rates).'},
                            {'id': 'd', 'text': 'Updating only one randomly chosen weight per training epoch.'}],
        'skill': 'Machine Learning',
        'stem': 'How does the Adam optimizer compute parameter updates?',
        'sub_domain': 'optimization'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'PCA diagonalizes the sample covariance matrix; the eigenvectors define orthogonal axes of '
                       'maximum variance, ordered by their corresponding eigenvalues.',
        'id': 'mcq_ml_016',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Random orthogonal projection matrices sampled from a Gaussian distribution.'},
                            {'id': 'b', 'text': 'The cluster centroids calculated by unsupervised K-Means iterations.'},
                            {   'id': 'c',
                                'text': 'The weights of the output layer of a multi-class logistic regression model.'},
                            {   'id': 'd',
                                'text': 'The eigenvectors of the feature covariance matrix corresponding to the '
                                        'largest eigenvalues.'}],
        'skill': 'Machine Learning',
        'stem': 'In Principal Component Analysis (PCA), how are the principal component directions determined '
                'mathematically?',
        'sub_domain': 'dimensionality_reduction'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'During training, units are dropped with probability p to prevent co-adaptation. During '
                       'inference, all units are active, and outputs are scaled (or inverted dropout scales by 1/(1-p) '
                       'during training).',
        'id': 'mcq_ml_017',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'During training, units are randomly deactivated with probability p; during '
                                        'inference, all units remain active with scaled activations.'},
                            {   'id': 'b',
                                'text': 'During training, all units remain active; during inference, units are '
                                        'randomly deactivated.'},
                            {   'id': 'c',
                                'text': 'Dropout permanently deletes weights from memory so they are absent during '
                                        'inference.'},
                            {'id': 'd', 'text': 'Dropout doubles the learning rate during validation passes.'}],
        'skill': 'Machine Learning',
        'stem': 'How does Dropout regularization behave during evaluation/inference compared to training?',
        'sub_domain': 'regularization'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Support vectors lie on the margin boundaries; the optimal separating hyperplane depends '
                       'strictly on these critical points, while all other data points can be moved without altering '
                       'the decision boundary.',
        'id': 'mcq_ml_018',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'They are outlier samples that are discarded before computing the margin.'},
                            {   'id': 'b',
                                'text': 'They are the training points closest to the decision boundary that uniquely '
                                        'define the maximum-margin hyperplane.'},
                            {   'id': 'c',
                                'text': 'They represent the average centroid of all negative class training points.'},
                            {'id': 'd', 'text': 'They determine the number of trees generated in an ensemble model.'}],
        'skill': 'Machine Learning',
        'stem': 'What is the primary role of the support vectors in a Support Vector Machine (SVM) classifier?',
        'sub_domain': 'supervised_learning'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': 'Dense projections cost O(N*d^2). Computing and applying attention across h heads costs '
                       'O(N^2*d), because each head has width d/h, while materializing every head\'s attention matrix '
                       'requires O(h*N^2) score memory. The combined time is O(N*d^2 + N^2*d).',
        'id': 'mcq_ml_019',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Time O(N*d^2) and attention-score memory O(N*d), because splitting into heads '
                                        'removes pairwise token interactions.'},
                            {   'id': 'b',
                                'text': 'Time O(N*d^2 + h*N^2*d) and attention-score memory O(N^2*d), because every head '
                                        'retains the full model width d.'},
                            {   'id': 'c',
                                'text': 'Time O(N*d^2 + N^2*d) and attention-score memory O(h*N^2), because each of h '
                                        'heads materializes an N by N score matrix with head width d/h.'},
                            {   'id': 'd',
                                'text': 'Time O(N^2*d^2) and attention-score memory O(h*N*d), because every token pair '
                                        'requires a full d by d matrix multiplication.'}],
        'skill': 'Machine Learning',
        'stem': 'For a standard dense multi-head self-attention layer with sequence length N, model width d, and h '
                'heads, which complexity statement includes both linear projections and materialized attention scores '
                '(ignoring batch size)?',
        'sub_domain': 'deep_learning'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': 'In double descent, test risk can peak near the interpolation threshold, defined by the model '
                       'first achieving essentially zero training error, and then decrease as effective model capacity '
                       'grows further. In deep networks that threshold is not generally determined by raw parameter '
                       'count approximately equalling the number of samples.',
        'id': 'mcq_ml_020',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Test risk oscillates randomly without any observable statistical trend.'},
                            {   'id': 'b',
                                'text': 'Test risk increases monotonically to infinity as model parameters exceed the '
                                        'number of training samples.'},
                            {   'id': 'c',
                                'text': 'Test risk drops immediately to zero and remains exactly zero for all larger '
                                        'models.'},
                            {   'id': 'd',
                                'text': 'Test risk peaks at the interpolation threshold where training error reaches '
                                        'zero, then decreases as parameter count grows further.'}],
        'skill': 'Machine Learning',
        'stem': 'In modern overparameterized deep learning, how does test risk behave beyond the interpolation '
                'threshold in the Double Descent phenomenon?',
        'sub_domain': 'statistical_learning'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'Gradient clipping scales the entire gradient vector proportionally when ||g|| > c, preserving '
                       'gradient direction while preventing catastrophic exploding gradient updates.',
        'id': 'mcq_ml_021',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'If the L2 norm of the global gradient vector exceeds a threshold c, the '
                                        'vector is rescaled by c / ||g||.'},
                            {   'id': 'b',
                                'text': 'It sets all gradient components exceeding a threshold directly to zero.'},
                            {   'id': 'c',
                                'text': 'It resets all model weight matrices to random values whenever loss '
                                        'increases.'},
                            {'id': 'd', 'text': 'It truncates the backward pass to strictly one time step.'}],
        'skill': 'Machine Learning',
        'stem': 'How does gradient norm clipping prevent numerical instability during Recurrent Neural Network (RNN) '
                'training?',
        'sub_domain': 'deep_learning'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'InfoNCE treats augmented views of the same sample as positive pairs and other batch samples as '
                       'negative pairs, maximizing the mutual information lower bound between positive '
                       'representations.',
        'id': 'mcq_ml_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Predict the exact pixel coordinates of objects using mean squared error.'},
                            {   'id': 'b',
                                'text': 'Maximize agreement between representations of augmented views of the same '
                                        'image while minimizing agreement with negative pairs.'},
                            {   'id': 'c',
                                'text': 'Minimize the number of active hidden neurons in an autoencoder bottleneck.'},
                            {   'id': 'd',
                                'text': 'Ensure that all learned embedding vectors collapse into a single point in '
                                        'latent space.'}],
        'skill': 'Machine Learning',
        'stem': 'In self-supervised contrastive representation learning (such as InfoNCE loss), what is the objective '
                'of the loss function?',
        'sub_domain': 'self_supervised'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'The Transport Layer (e.g. TCP, UDP) is responsible for process-to-process communication, data '
                       'segmentation, flow control, and end-to-end error recovery.',
        'id': 'mcq_cn_001',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Data Link Layer (Layer 2)'},
                            {'id': 'b', 'text': 'Network Layer (Layer 3)'},
                            {'id': 'c', 'text': 'Transport Layer (Layer 4)'},
                            {'id': 'd', 'text': 'Session Layer (Layer 5)'}],
        'skill': 'Computer Networks',
        'stem': 'Which layer of the OSI model provides end-to-end communication, segmentation, and reliability '
                'services between application processes?',
        'sub_domain': 'osi_model'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'TCP establishes a stateful connection with handshakes, sequence numbers, and retransmissions, '
                       'whereas UDP sends datagrams without establishing a connection.',
        'id': 'mcq_cn_002',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'TCP encrypts all packet payloads by default, whereas UDP transmits '
                                        'plaintext.'},
                            {   'id': 'b',
                                'text': 'TCP is connectionless and faster, whereas UDP establishes a three-way '
                                        'handshake.'},
                            {   'id': 'c',
                                'text': 'TCP transmits exclusively over optical fiber, whereas UDP operates only on '
                                        'copper wiring.'},
                            {   'id': 'd',
                                'text': 'TCP is connection-oriented and guarantees reliable, ordered packet delivery, '
                                        'whereas UDP is connectionless and best-effort.'}],
        'skill': 'Computer Networks',
        'stem': 'What distinguishes TCP from UDP regarding connection establishment and delivery guarantees?',
        'sub_domain': 'protocols'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'IPv4 uses 32-bit addresses (4 octets), providing ~4.3 billion addresses, while IPv6 uses '
                       '128-bit addresses (16 octets) to provide a vast address space.',
        'id': 'mcq_cn_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'IPv6 addresses are 128 bits long, whereas IPv4 addresses are 32 bits long.'},
                            {   'id': 'b',
                                'text': 'IPv6 addresses are 64 bits long, whereas IPv4 addresses are 16 bits long.'},
                            {   'id': 'c',
                                'text': 'IPv6 addresses are 256 bits long, whereas IPv4 addresses are 64 bits long.'},
                            {   'id': 'd',
                                'text': 'IPv6 addresses are 512 bits long, whereas IPv4 addresses are 128 bits long.'}],
        'skill': 'Computer Networks',
        'stem': 'What is the bit length of an IPv6 address compared to a standard IPv4 address?',
        'sub_domain': 'ip_addressing'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': "DNS serves as the internet's directory service, resolving domain names (like example.com) to "
                       'corresponding IP addresses.',
        'id': 'mcq_cn_004',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Encrypting web pages during transport over HTTP connections.'},
                            {'id': 'b', 'text': 'Translating human-readable domain names into numerical IP addresses.'},
                            {'id': 'c', 'text': 'Allocating physical MAC addresses to network interface cards.'},
                            {'id': 'd', 'text': 'Routing optical signals through undersea telecommunication cables.'}],
        'skill': 'Computer Networks',
        'stem': 'What is the primary role of the Domain Name System (DNS) on the internet?',
        'sub_domain': 'dns'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'HTTPS runs standard HTTP communication over a cryptographically secured TLS session, ensuring '
                       'confidentiality and integrity.',
        'id': 'mcq_cn_005',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Border Gateway Protocol (BGP).'},
                            {'id': 'b', 'text': 'Simple Mail Transfer Protocol (SMTP).'},
                            {   'id': 'c',
                                'text': 'Transport Layer Security (TLS/SSL) providing encryption and server '
                                        'authentication.'},
                            {'id': 'd', 'text': 'Dynamic Host Configuration Protocol (DHCP).'}],
        'skill': 'Computer Networks',
        'stem': 'What security protocol distinguishes HTTPS traffic from standard HTTP traffic?',
        'sub_domain': 'security'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'MAC addresses are physical layer-2 hardware identifiers used by network interface cards and '
                       'local Ethernet switches to deliver frames within a local link.',
        'id': 'mcq_cn_006',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Transport Layer (Layer 4)'},
                            {'id': 'b', 'text': 'Network Layer (Layer 3)'},
                            {'id': 'c', 'text': 'Physical Layer (Layer 1)'},
                            {'id': 'd', 'text': 'Data Link Layer (Layer 2)'}],
        'skill': 'Computer Networks',
        'stem': 'At which layer of the OSI architecture does a 48-bit Media Access Control (MAC) address operate?',
        'sub_domain': 'data_link'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Routers operate at Layer 3 (Network) using IP routing tables, while Layer 2 switches use MAC '
                       'address tables to forward Ethernet frames within a single broadcast domain.',
        'id': 'mcq_cn_007',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A router forwards packets based on Layer 3 IP addresses across networks, '
                                        'whereas a switch forwards frames based on Layer 2 MAC addresses within a '
                                        'network.'},
                            {'id': 'b', 'text': 'A router operates at Layer 7, whereas a switch operates at Layer 1.'},
                            {   'id': 'c',
                                'text': 'A router handles wireless connections only, whereas a switch connects wired '
                                        'fiber.'},
                            {'id': 'd', 'text': 'A router converts digital signals into analog sound waves.'}],
        'skill': 'Computer Networks',
        'stem': 'What primary OSI layer distinction separates a Network Router from a standard Layer 2 Ethernet '
                'Switch?',
        'sub_domain': 'devices'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'The client initiates connection with SYN; the server responds with SYN-ACK; the client '
                       'completes connection establishment with ACK.',
        'id': 'mcq_cn_011',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'ACK -> SYN -> SYN-ACK'},
                            {'id': 'b', 'text': 'SYN -> SYN-ACK -> ACK'},
                            {'id': 'c', 'text': 'SYN -> ACK -> DATA'},
                            {'id': 'd', 'text': 'FIN -> ACK -> FIN-ACK'}],
        'skill': 'Computer Networks',
        'stem': 'What is the exact sequence of flag packets exchanged during the standard TCP Three-Way Handshake?',
        'sub_domain': 'tcp'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'TIME_WAIT keeps the active closer\'s state long enough to retransmit the final ACK if the peer '
                       'retransmits its FIN, and to let delayed duplicate segments expire before the same connection '
                       'tuple is reused. TCP does not send a separate ACK-of-ACK.',
        'id': 'mcq_cn_012',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Keeping the connection writable so the active closer can send additional '
                                        'application data after its FIN.'},
                            {   'id': 'b',
                                'text': 'Preserving the old connection\'s congestion window so a future connection can '
                                        'resume with the same sending rate.'},
                            {   'id': 'c',
                                'text': 'Allowing retransmission of the final ACK if the peer repeats its FIN, while '
                                        'giving delayed duplicate segments time to expire.'},
                            {   'id': 'd',
                                'text': 'Waiting for routing and address-resolution caches to expire before acknowledging '
                                        'the peer\'s FIN.'}],
        'skill': 'Computer Networks',
        'stem': 'What is the primary purpose of the TIME_WAIT state entered by an active TCP endpoint during '
                'connection termination?',
        'sub_domain': 'tcp'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'During Slow Start, TCP doubles its congestion window every round-trip time (incrementing cwnd '
                       'by 1 MSS for each ACK received) until ssthresh is reached.',
        'id': 'mcq_cn_013',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Additive Increase Multiplicative Decrease (AIMD)'},
                            {'id': 'b', 'text': 'Congestion Avoidance algorithm'},
                            {'id': 'c', 'text': 'Fast Recovery algorithm'},
                            {'id': 'd', 'text': 'Slow Start algorithm'}],
        'skill': 'Computer Networks',
        'stem': 'In TCP Tahoe/Reno congestion control, what algorithm governs the initial exponential growth of the '
                'congestion window (cwnd)?',
        'sub_domain': 'congestion_control'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': "NAPT maps private socket pairs (private IP + port) to the router's public IP address with "
                       'distinct translated source port numbers in a NAT translation table.',
        'id': 'mcq_cn_014',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'By translating internal private IP and source port combinations into the '
                                        'single public IP with unique external source ports.'},
                            {   'id': 'b',
                                'text': 'By translating each private source IP to the public IP while preserving every '
                                        'host\'s original source port unchanged.'},
                            {'id': 'c', 'text': 'By compressing all outgoing packets into a single TCP connection.'},
                            {'id': 'd', 'text': 'By converting IPv4 packets into IPv6 tunnels automatically.'}],
        'skill': 'Computer Networks',
        'stem': 'How does Network Address and Port Translation (NAPT/PAT) allow multiple private IP hosts to share a '
                'single public IPv4 address?',
        'sub_domain': 'nat'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': "ARP broadcasts a query asking 'Who has IP X.X.X.X? Tell MAC Y:Y:Y:Y', mapping logical Layer 3 "
                       'addresses to physical Layer 2 link addresses.',
        'id': 'mcq_cn_015',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Assigning dynamic IP addresses to newly booted client machines.'},
                            {   'id': 'b',
                                'text': 'Resolving a known target IPv4 address to its corresponding physical MAC '
                                        'hardware address.'},
                            {'id': 'c', 'text': 'Encrypting local Ethernet broadcast packets.'},
                            {'id': 'd', 'text': 'Determining the optimal internet route across autonomous systems.'}],
        'skill': 'Computer Networks',
        'stem': 'What is the primary function of the Address Resolution Protocol (ARP) within a local network?',
        'sub_domain': 'arp'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Link-State protocols (OSPF, IS-IS) flood LSA states to build a full global topology map and '
                       "run Dijkstra's algorithm locally; Distance-Vector protocols (RIP, BGP) share bellman-ford "
                       'vectors.',
        'id': 'mcq_cn_016',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': "Distance-Vector protocols compute shortest paths using Dijkstra's algorithm."},
                            {'id': 'b', 'text': 'Link-State protocols are limited to 15 hops maximum.'},
                            {   'id': 'c',
                                'text': 'Link-State routers flood topological information so every router builds a '
                                        'complete map of the entire network graph, whereas Distance-Vector routers '
                                        'exchange distance vectors only with immediate neighbors.'},
                            {   'id': 'd',
                                'text': 'Link-State protocols route packets without inspecting destination IP '
                                        'addresses.'}],
        'skill': 'Computer Networks',
        'stem': 'What distinguishes Link-State routing protocols (such as OSPF) from Distance-Vector routing protocols '
                '(such as RIP)?',
        'sub_domain': 'routing'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'TLS 1.3 combines key-share guessing in the ClientHello with cipher selection, reducing full '
                       'handshake latency to 1-RTT, and supports 0-RTT resumption.',
        'id': 'mcq_cn_017',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Enforcing static pre-shared passwords across all websites.'},
                            {'id': 'b', 'text': 'Eliminating symmetric key encryption entirely.'},
                            {   'id': 'c',
                                'text': 'Transferring certificate authority verification to local client disk cache.'},
                            {   'id': 'd',
                                'text': 'Reducing the full cryptographic handshake from two round trips (2-RTT) down '
                                        'to a single round trip (1-RTT).'}],
        'skill': 'Computer Networks',
        'stem': 'What optimization in TLS 1.3 reduces connection latency during initial cryptographic negotiation '
                'compared to TLS 1.2?',
        'sub_domain': 'tls'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'In TCP, a single lost packet halts delivery of all data in the stream buffer. QUIC runs '
                       'streams over UDP, isolating loss recovery so lost packets only block the stream they belong '
                       'to.',
        'id': 'mcq_cn_021',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'By implementing independent stream handling directly over UDP, so a dropped '
                                        'packet delays only the affected stream rather than all streams.'},
                            {'id': 'b', 'text': 'By disabling packet retransmission across all streams.'},
                            {   'id': 'c',
                                'text': 'By guaranteeing 100 percent packet delivery over physical radio waves.'},
                            {   'id': 'd',
                                'text': 'By forcing client devices to connect via multiple physical Ethernet cards.'}],
        'skill': 'Computer Networks',
        'stem': 'How does HTTP/3 / QUIC eliminate transport-layer Head-of-Line (HoL) blocking that persists in HTTP/2 '
                'over TCP?',
        'sub_domain': 'protocols'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'BBR measures bottleneck bandwidth and minimum RTT to establish the optimal inflight data '
                       'volume, preventing bufferbloat and avoiding the loss-driven oscillations of Reno/CUBIC.',
        'id': 'mcq_cn_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It increases the sending rate exponentially until bufferbloat causes 50 '
                                        'percent packet drops.'},
                            {   'id': 'b',
                                'text': 'It constructs an explicit model of the network bottleneck by measuring '
                                        'delivery rate and round-trip time, operating at the Kleinrock optimum without '
                                        'relying on packet loss as a congestion signal.'},
                            {   'id': 'c',
                                'text': 'It requires special hardware support on all intermediate commercial routers.'},
                            {'id': 'd', 'text': 'It operates strictly on local area network switches.'}],
        'skill': 'Computer Networks',
        'stem': "How does Google's BBR (Bottleneck Bandwidth and RTT) congestion control algorithm differ "
                'fundamentally from loss-based algorithms like TCP CUBIC?',
        'sub_domain': 'congestion_control'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': 'SYN cookies calculate a cryptographic hash of client/server IPs, ports, and a secret as the '
                       "server's ISN, deferring SYN queue allocation until the client returns the ACK.",
        'id': 'mcq_cn_023',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'The server allocates double memory buffers in RAM for each pending '
                                        'connection.'},
                            {   'id': 'b',
                                'text': 'The server drops all incoming SYN packets originating from outside its '
                                        'subnet.'},
                            {   'id': 'c',
                                'text': 'The server encodes connection state into the initial sequence number (ISN) '
                                        'and allocates zero kernel state until receiving the valid client ACK.'},
                            {   'id': 'd',
                                'text': 'The server forces the client to compute a proof-of-work cryptographic hash.'}],
        'skill': 'Computer Networks',
        'stem': 'How does the SYN Cookies technique protect a server against TCP SYN flood attacks without exhausting '
                'kernel memory?',
        'sub_domain': 'security'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': 'With Anycast, identical IP addresses are advertised by multiple nodes across different network '
                       'locations; BGP routing directs traffic to the nearest instance according to routing metrics.',
        'id': 'mcq_cn_024',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Clients establish peer-to-peer mesh connections to find nearby servers.'},
                            {   'id': 'b',
                                'text': 'A central DNS server tracks client GPS coordinates and updates IP assignments '
                                        'dynamically.'},
                            {   'id': 'c',
                                'text': 'Packets are duplicated and broadcast across all global data centers '
                                        'simultaneously.'},
                            {   'id': 'd',
                                'text': 'Multiple geographically dispersed servers announce the exact same IP address '
                                        'prefix via BGP, allowing internet routing to direct packets along the '
                                        'shortest AS path.'}],
        'skill': 'Computer Networks',
        'stem': 'How does BGP Anycast routing enable global Content Delivery Networks (CDNs) and DNS root servers to '
                'route users to the topologically nearest point of presence?',
        'sub_domain': 'routing'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'A stack operates on the Last-In, First-Out (LIFO) principle, where the most recently added '
                       'element is the first one removed.',
        'id': 'mcq_dsa_001',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Last-In, First-Out (LIFO)'},
                            {'id': 'b', 'text': 'First-In, First-Out (FIFO)'},
                            {'id': 'c', 'text': 'Priority-ordered access'},
                            {'id': 'd', 'text': 'Random index access'}],
        'skill': 'DSA',
        'stem': 'Which element access order characterizes a standard Stack data structure?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Binary search halves the remaining search space with each comparison, running in O(log n) '
                       'logarithmic time.',
        'id': 'mcq_dsa_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(n)'},
                            {'id': 'b', 'text': 'O(log n)'},
                            {'id': 'c', 'text': 'O(n log n)'},
                            {'id': 'd', 'text': 'O(1)'}],
        'skill': 'DSA',
        'stem': 'What is the worst-case time complexity of Binary Search executed on a sorted array of N elements?',
        'sub_domain': 'algorithms'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'A singly linked list node contains the element value and a single link pointer pointing to the '
                       'next node in the sequence.',
        'id': 'mcq_dsa_003',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'A key, a value, and a hash code.'},
                            {'id': 'b', 'text': 'A data payload, a previous pointer, and a next pointer.'},
                            {'id': 'c', 'text': 'A data payload and a pointer/reference to the subsequent node.'},
                            {'id': 'd', 'text': 'An array of fixed memory addresses.'}],
        'skill': 'DSA',
        'stem': 'What fundamental components comprise a standard node in a Singly Linked List?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Array elements occupy contiguous memory, allowing immediate address computation (base + index '
                       '* element_size) in O(1) time.',
        'id': 'mcq_dsa_004',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(n^2) quadratic time'},
                            {'id': 'b', 'text': 'O(log n) logarithmic time'},
                            {'id': 'c', 'text': 'O(n) linear time'},
                            {'id': 'd', 'text': 'O(1) constant time'}],
        'skill': 'DSA',
        'stem': 'What is the time complexity to retrieve an element by its index in a contiguous memory array?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'The BST property dictates that for any node X, all left descendant keys are less than X.key, '
                       'and all right descendant keys are greater than X.key.',
        'id': 'mcq_dsa_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': "All keys in X's left subtree are strictly less than X's key, and all keys in "
                                        "X's right subtree are strictly greater."},
                            {'id': 'b', 'text': 'All parent nodes must contain values smaller than their child nodes.'},
                            {   'id': 'c',
                                'text': 'The depth of left and right subtrees must be identical across all levels.'},
                            {'id': 'd', 'text': 'Nodes must contain exactly two children without exception.'}],
        'skill': 'DSA',
        'stem': 'What ordering invariant must hold for every node X in a valid Binary Search Tree (BST)?',
        'sub_domain': 'trees'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'With a good hash function and appropriate load factor management, hash table insertions and '
                       'lookups execute in average O(1) time.',
        'id': 'mcq_dsa_006',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(log n)'},
                            {'id': 'b', 'text': 'O(1)'},
                            {'id': 'c', 'text': 'O(n)'},
                            {'id': 'd', 'text': 'O(n log n)'}],
        'skill': 'DSA',
        'stem': 'What is the average-case time complexity of inserting a key-value pair into a Hash Table with a '
                'uniform hash distribution?',
        'sub_domain': 'hashing'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'QuickSort degrades to O(n^2) when partitions are maximally unbalanced (e.g. selecting the '
                       'first/last element on an already sorted array without randomization).',
        'id': 'mcq_dsa_011',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'When the pivot always divides the array into two exactly equal halves.'},
                            {   'id': 'b',
                                'text': 'When the array elements are completely random with uniform distribution.'},
                            {   'id': 'c',
                                'text': 'When the chosen pivot repeatedly partitions the array into one empty subarray '
                                        'and one subarray of size n - 1.'},
                            {'id': 'd', 'text': 'When the array size is a power of two.'}],
        'skill': 'DSA',
        'stem': 'Under what circumstance does standard QuickSort degrade to its worst-case time complexity of O(n^2)?',
        'sub_domain': 'sorting'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Standard array-based merge sort requires O(n) temporary buffer space to merge two sorted '
                       'halves into a combined sorted sequence.',
        'id': 'mcq_dsa_012',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(n^2) auxiliary memory.'},
                            {'id': 'b', 'text': 'O(1) in-place auxiliary memory.'},
                            {'id': 'c', 'text': 'O(log n) auxiliary memory.'},
                            {   'id': 'd',
                                'text': 'O(n) auxiliary memory to hold temporary arrays during the merge operation.'}],
        'skill': 'DSA',
        'stem': 'What is the auxiliary space complexity of standard Merge Sort implemented on an array of size N?',
        'sub_domain': 'sorting'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'BFS explores vertices in increasing order of distance from the source using a queue, '
                       'guaranteeing the shortest path in unweighted graphs.',
        'id': 'mcq_dsa_013',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Breadth-First Search (BFS)'},
                            {'id': 'b', 'text': 'Depth-First Search (DFS)'},
                            {'id': 'c', 'text': 'Inorder Traversal'},
                            {'id': 'd', 'text': 'Topological Sort'}],
        'skill': 'DSA',
        'stem': 'Which graph traversal algorithm guarantees finding the shortest path (minimum edge count) between two '
                'vertices in an unweighted graph?',
        'sub_domain': 'graphs'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'In directed graphs, a cycle exists if and only if DFS encounters a back edge to a node that is '
                       'currently in the recursion stack (grey node in 3-color model).',
        'id': 'mcq_dsa_014',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'By counting whether total edges exceed total vertices.'},
                            {   'id': 'b',
                                'text': 'By detecting a back-edge pointing to an ancestor vertex currently active on '
                                        'the recursion call stack.'},
                            {'id': 'c', 'text': 'By verifying whether all vertices have even degrees.'},
                            {'id': 'd', 'text': 'By calculating the sum of edge weights.'}],
        'skill': 'DSA',
        'stem': 'How can Depth-First Search (DFS) detect cycles in a directed graph during traversal?',
        'sub_domain': 'graphs'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Open addressing stores items contiguously in the table for great cache performance, but '
                       'clustering degrades performance when full; chaining uses linked lists per bucket.',
        'id': 'mcq_dsa_015',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Separate chaining consumes zero pointer overhead.'},
                            {'id': 'b', 'text': 'Open addressing permits an infinite load factor greater than 1.0.'},
                            {   'id': 'c',
                                'text': 'Open addressing provides superior CPU cache locality by storing all entries '
                                        'in the primary table array, but suffers from clustering as load factor '
                                        'rises.'},
                            {'id': 'd', 'text': 'Separate chaining requires sorted hash buckets.'}],
        'skill': 'DSA',
        'stem': 'What primary trade-off distinguishes Open Addressing (with Linear Probing) from Separate Chaining for '
                'hash collision resolution?',
        'sub_domain': 'hashing'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'An AVL tree maintains height balance by guaranteeing that for every node, |height(left) - '
                       'height(right)| <= 1, restoring balance via rotations when violated.',
        'id': 'mcq_dsa_016',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Every node must be colored either red or black.'},
                            {   'id': 'b',
                                'text': 'The number of nodes in left and right subtrees must differ by at most one.'},
                            {'id': 'c', 'text': 'All leaves must reside on the exact same depth level.'},
                            {   'id': 'd',
                                'text': 'The balance factor (height difference between left and right subtrees) must '
                                        'be within {-1, 0, +1}.'}],
        'skill': 'DSA',
        'stem': 'What balance invariant must hold at every node in an AVL self-balancing binary search tree?',
        'sub_domain': 'trees'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Push adds an element at the end and sifts up in O(log n); pop removes the root, swaps the last '
                       'element to the root, and sifts down in O(log n).',
        'id': 'mcq_dsa_017',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(log n) for push, and O(log n) for pop.'},
                            {'id': 'b', 'text': 'O(1) for push, and O(n) for pop.'},
                            {'id': 'c', 'text': 'O(n) for push, and O(1) for pop.'},
                            {'id': 'd', 'text': 'O(1) for push, and O(log n) for pop.'}],
        'skill': 'DSA',
        'stem': 'What are the time complexities for pushing a new element and popping the minimum element in a binary '
                'min-heap containing N elements?',
        'sub_domain': 'heaps'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'A key Red-Black tree invariant is that all simple paths from any node to descendant leaves '
                       'must contain the identical count of black nodes, bounding maximum path length to 2*log(n).',
        'id': 'mcq_dsa_021',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'All red nodes must be positioned exclusively at leaf positions.'},
                            {   'id': 'b',
                                'text': 'Every path from a node to any of its descendant null leaves contains the '
                                        'exact same number of black nodes (uniform black-height).'},
                            {   'id': 'c',
                                'text': 'The total count of red nodes must exceed the total count of black nodes.'},
                            {'id': 'd', 'text': 'The root node must always be colored red.'}],
        'skill': 'DSA',
        'stem': 'Which structural invariant must a valid Red-Black Tree satisfy regarding paths from any node to its '
                'descendant null leaves?',
        'sub_domain': 'trees'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': "KMP's preprocessing builds the LPS array in O(m) time using two pointers and dynamic matching, "
                       'enabling the main text scan to execute in O(n) without backtracking.',
        'id': 'mcq_dsa_022',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'O(m log m).'},
                            {'id': 'b', 'text': 'O(m^2) quadratic time.'},
                            {'id': 'c', 'text': 'O(m) linear time in the length of the pattern.'},
                            {'id': 'd', 'text': 'O(2^m) exponential time.'}],
        'skill': 'DSA',
        'stem': 'What is the time complexity to precompute the Longest Prefix Suffix (LPS) lookup array in the '
                'Knuth-Morris-Pratt (KMP) string search algorithm for a pattern of length M?',
        'sub_domain': 'strings'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': "Tarjan's algorithm assigns discovery times and computes low-link values using a single DFS "
                       'traversal and an explicit stack, isolating SCCs in O(V + E) time.',
        'id': 'mcq_dsa_023',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'By computing the minimum spanning tree of the undirected graph.'},
                            {'id': 'b', 'text': 'By reversing all graph edges and running a second DFS pass.'},
                            {'id': 'c', 'text': 'By performing all-pairs shortest paths matrix exponentiation.'},
                            {   'id': 'd',
                                'text': 'By maintaining discovery timestamps and low-link values on a stack, '
                                        'identifying an SCC root when low-link equals discovery timestamp.'}],
        'skill': 'DSA',
        'stem': "How does Tarjan's algorithm identify Strongly Connected Components (SCCs) in a directed graph within "
                'a single DFS traversal?',
        'sub_domain': 'graphs'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Tuples cannot have elements added, removed, or changed after construction, whereas lists '
                       'support mutations like append, pop, and index reassignment.',
        'id': 'mcq_python_001',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Tuples are immutable sequences, whereas lists are mutable and support '
                                        'in-place item assignment.'},
                            {   'id': 'b',
                                'text': 'Tuples store only primitive numbers, whereas lists store arbitrary objects.'},
                            {   'id': 'c',
                                'text': 'Tuples are always ordered by value, whereas lists maintain insertion order.'},
                            {'id': 'd', 'text': 'Tuples cannot be iterated using a standard for-in loop.'}],
        'skill': 'Python',
        'stem': 'What distinguishes a Python tuple from a Python list regarding item modification?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Dictionary keys must be hashable objects whose hash value remains constant during their '
                       'lifetime, allowing equality comparisons with other objects.',
        'id': 'mcq_python_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'The object must inherit directly from the built-in string class.'},
                            {'id': 'b', 'text': 'The object must be hashable, implementing __hash__() and __eq__().'},
                            {'id': 'c', 'text': 'The object must be an integer or floating-point numeric value.'},
                            {'id': 'd', 'text': 'The object must maintain a strictly positive memory address.'}],
        'skill': 'Python',
        'stem': 'What requirement must an object satisfy to serve as a valid key in a standard Python dictionary?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': "CPython's PyVarObject header contains an ob_size field, allowing len() to return the item "
                       'count instantly in O(1) time without traversal.',
        'id': 'mcq_python_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'O(log n) logarithmic time, because it performs a binary search for the tail '
                                        'pointer.'},
                            {   'id': 'b',
                                'text': 'O(n) linear time, because it iterates through the internal array to count '
                                        'items.'},
                            {   'id': 'c',
                                'text': "O(1) constant time, because the element count is stored in the object's C "
                                        'struct header.'},
                            {'id': 'd', 'text': 'O(n^2) quadratic time, because it validates pointer references.'}],
        'skill': 'Python',
        'stem': 'What is the time complexity of the built-in len() function when querying a standard Python list?',
        'sub_domain': 'performance'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': "'is' checks whether two references point to the exact same object in memory (id(a) == id(b)), "
                       "whereas '==' invokes __eq__() to check value equivalence.",
        'id': 'mcq_python_004',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': "'is' is reserved strictly for comparing None values."},
                            {   'id': 'b',
                                'text': "'is' tests for numeric magnitude, whereas '==' tests for type equivalence."},
                            {   'id': 'c',
                                'text': "'is' performs deep recursive comparison, whereas '==' performs shallow "
                                        'comparison.'},
                            {   'id': 'd',
                                'text': "'is' tests for object memory identity, whereas '==' tests for value "
                                        'equality.'}],
        'skill': 'Python',
        'stem': "What distinguishes the 'is' operator from the '==' operator in Python?",
        'sub_domain': 'operators'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Calling append([1, 2]) adds the list as a single child element, whereas extend([1, 2]) unpacks '
                       'the iterable and appends each element individually.',
        'id': 'mcq_python_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'extend() iterates over the argument appending each element individually, '
                                        'whereas append() adds the argument as a single element.'},
                            {   'id': 'b',
                                'text': 'extend() returns a brand new list, whereas append() modifies the list in '
                                        'place.'},
                            {   'id': 'c',
                                'text': 'extend() sorts the list after insertion, whereas append() preserves insertion '
                                        'order.'},
                            {   'id': 'd',
                                'text': 'extend() accepts only string arguments, whereas append() accepts arbitrary '
                                        'objects.'}],
        'skill': 'Python',
        'stem': 'What is the behavior of list.extend(iterable) compared to list.append(item)?',
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Because Python strings are immutable, concatenation constructs a new string object containing '
                       'the combined sequence of characters.',
        'id': 'mcq_python_006',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': "The left-hand string's buffer is expanded in place to accommodate the extra "
                                        'characters.'},
                            {   'id': 'b',
                                'text': 'A new string object is allocated in memory to store the joined characters '
                                        'because strings are immutable.'},
                            {   'id': 'c',
                                'text': 'A mutable pointer table is updated while retaining identical string IDs.'},
                            {'id': 'd', 'text': 'The characters are piped to the operating system temporary spool.'}],
        'skill': 'Python',
        'stem': "What happens in memory when executing string concatenation using the '+' operator in Python?",
        'sub_domain': 'data_structures'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Default argument expressions are evaluated once when the function definition is executed, '
                       'binding the same mutable object across calls.',
        'id': 'mcq_python_011',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Python raises a SyntaxError at script compilation time.'},
                            {   'id': 'b',
                                'text': 'A fresh empty list is instantiated dynamically each time the function is '
                                        'called.'},
                            {   'id': 'c',
                                'text': 'The default list is created once at function definition time and shared '
                                        'across subsequent invocations that omit the parameter.'},
                            {'id': 'd', 'text': 'The list is converted into an immutable tuple automatically.'}],
        'skill': 'Python',
        'stem': "What happens when using a mutable object as a default parameter value, such as 'def append_to(item, "
                "target=[])'?",
        'sub_domain': 'functions'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Using yield transforms the function into a generator constructor; calling next() resumes '
                       'execution right after the yield statement.',
        'id': 'mcq_python_012',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'It converts all local variables into global module variables.'},
                            {   'id': 'b',
                                'text': 'It terminates function execution and destroys the local stack frame '
                                        'permanently.'},
                            {   'id': 'c',
                                'text': 'It schedules the function to run concurrently on a separate operating system '
                                        'thread.'},
                            {   'id': 'd',
                                'text': 'It turns the function into a generator that suspends execution state and '
                                        'yields control back to the caller until next() is invoked.'}],
        'skill': 'Python',
        'stem': "How does the 'yield' keyword alter the execution behavior of a Python function?",
        'sub_domain': 'generators'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'In Python 3, list comprehensions have their own distinct local scope, ensuring loop variables '
                       'do not leak into the enclosing scope.',
        'id': 'mcq_python_013',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': "The variable 'x' is scoped locally to the comprehension's implicit function "
                                        'scope and does not overwrite outer scope variables.'},
                            {   'id': 'b',
                                'text': "The variable 'x' leaks into the surrounding local namespace, retaining its "
                                        'final loop value.'},
                            {'id': 'c', 'text': "The variable 'x' is automatically elevated to module global scope."},
                            {'id': 'd', 'text': 'The comprehension creates a new sub-process with isolated memory.'}],
        'skill': 'Python',
        'stem': "What is the scoping behavior of the iteration variable in a Python 3 list comprehension such as '[x "
                "for x in data]'?",
        'sub_domain': 'scoping'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': '@property allows methods to be accessed via attribute syntax, enabling computed attributes, '
                       'data validation, and clean encapsulation.',
        'id': 'mcq_python_014',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'To serialize class instances directly into JSON strings.'},
                            {   'id': 'b',
                                'text': 'To define getter methods that can be accessed like standard public attributes '
                                        'while allowing encapsulation and validation logic.'},
                            {'id': 'c', 'text': 'To make class methods execute as class-level static functions.'},
                            {'id': 'd', 'text': 'To enforce thread safety across concurrent method calls.'}],
        'skill': 'Python',
        'stem': 'What is the primary architectural purpose of the built-in @property decorator in Python classes?',
        'sub_domain': 'oop'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'The GIL is a mutex that protects access to Python objects, preventing multiple native threads '
                       'from executing Python bytecodes concurrently on multicore CPUs.',
        'id': 'mcq_python_015',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'I/O bound socket operations block the entire process and prevent thread '
                                        'switching.'},
                            {   'id': 'b',
                                'text': 'Multiple threads cannot read shared variables simultaneously under any '
                                        'condition.'},
                            {   'id': 'c',
                                'text': 'Only one native thread can execute Python bytecode at any given moment within '
                                        'a single CPython process.'},
                            {'id': 'd', 'text': 'Threads are forbidden from spawning worker processes.'}],
        'skill': 'Python',
        'stem': "What constraint does CPython's Global Interpreter Lock (GIL) place on standard multi-threaded Python "
                'programs?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': "Descriptors defining __set__() or __delete__() are data descriptors. In Python's attribute "
                       'lookup order, data descriptors take precedence over the instance __dict__.',
        'id': 'mcq_python_021',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A data descriptor can only be attached to built-in C extension types.'},
                            {   'id': 'b',
                                'text': 'A data descriptor defines only __get__(), taking precedence over class-level '
                                        'attributes.'},
                            {   'id': 'c',
                                'text': 'A data descriptor stores raw binary bytes, whereas non-data descriptors store '
                                        'text strings.'},
                            {   'id': 'd',
                                'text': 'A data descriptor defines __set__() or __delete__(), taking precedence over '
                                        "the instance's __dict__ during attribute lookup."}],
        'skill': 'Python',
        'stem': "What criteria distinguish a data descriptor from a non-data descriptor in Python's attribute lookup "
                'resolution?',
        'sub_domain': 'internals'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'In metaclasses, __new__() is responsible for allocating and returning the newly formed class '
                       'object; __init__() configures the class after creation.',
        'id': 'mcq_python_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': '__new__() creates and returns the class object itself, whereas __init__() '
                                        'initializes the already created class object.'},
                            {   'id': 'b',
                                'text': '__new__() creates instances of the user class, whereas __init__() creates the '
                                        'metaclass.'},
                            {'id': 'c', 'text': '__new__() registers class attributes in the global module namespace.'},
                            {   'id': 'd',
                                'text': '__new__() executes whenever an instance of the target class is '
                                        'instantiated.'}],
        'skill': 'Python',
        'stem': "In a custom metaclass subclassing 'type', what is the specific role of the __new__ method compared to "
                '__init__?',
        'sub_domain': 'metaprogramming'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'CPython uses a generational cyclic collector that tracks container objects and isolates '
                       'reference cycles by decrementing trial reference counts.',
        'id': 'mcq_python_023',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It pauses all execution and scans all operating system physical RAM pages.'},
                            {   'id': 'b',
                                'text': 'It tracks container objects across three generations, temporarily adjusting '
                                        'reference counts to detect unreachable subgraphs.'},
                            {'id': 'c', 'text': 'It forces all local variables to be nulled upon function exit.'},
                            {'id': 'd', 'text': 'It converts cyclic references into weak references automatically.'}],
        'skill': 'Python',
        'stem': "How does CPython's generational cyclic garbage collector identify and collect reference cycles that "
                'reference counting alone cannot reclaim?',
        'sub_domain': 'memory'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Encapsulation hides internal object representation (data hiding) and exposes access only '
                       'through controlled public interfaces/methods, protecting invariants.',
        'id': 'mcq_oop_001',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Enforcing that every class in a project derives from a single root class.'},
                            {   'id': 'b',
                                'text': 'Allowing arbitrary global functions to mutate private instance variables '
                                        'directly.'},
                            {   'id': 'c',
                                'text': 'Bundling data with methods that operate on that data while restricting direct '
                                        'external access to internal state.'},
                            {'id': 'd', 'text': 'Compiling object code into machine instructions at runtime.'}],
        'skill': 'OOP',
        'stem': 'What is the primary purpose of encapsulation in object-oriented class design?',
        'sub_domain': 'encapsulation'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Method overriding occurs when a subclass provides a specific implementation of a method '
                       'already defined in its superclass, requiring an identical signature for dynamic dispatch.',
        'id': 'mcq_oop_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'The method must execute within a standalone static function block.'},
                            {   'id': 'b',
                                'text': 'The subclass method must take a completely different number of arguments.'},
                            {   'id': 'c',
                                'text': 'The superclass method must be declared private in languages like Java or '
                                        'C++.'},
                            {   'id': 'd',
                                'text': 'The subclass method must match the method name and parameter signature of the '
                                        'superclass method.'}],
        'skill': 'OOP',
        'stem': 'Which condition is required for runtime method overriding in an inheritance hierarchy?',
        'sub_domain': 'polymorphism'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Abstract classes support state (fields) and partial implementation for shared code reuse, '
                       'whereas interfaces define pure behavioral contracts across unrelated classes.',
        'id': 'mcq_oop_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'An abstract class can maintain instance state fields and default method '
                                        'implementations, while interfaces primarily define behavioral contracts.'},
                            {   'id': 'b',
                                'text': 'Interfaces can be instantiated directly using the new keyword, whereas '
                                        'abstract classes cannot.'},
                            {   'id': 'c',
                                'text': 'A class can inherit from multiple abstract classes but only implement one '
                                        'interface in Java.'},
                            {'id': 'd', 'text': 'Abstract classes cannot declare any abstract methods.'}],
        'skill': 'OOP',
        'stem': 'What is the primary difference between an abstract class and an interface in standard object-oriented '
                'languages?',
        'sub_domain': 'abstraction'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'SRP states that a class should have one, and only one, reason to change, meaning it should '
                       'perform a single well-defined job or business responsibility.',
        'id': 'mcq_oop_004',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'A class should contain only one method and one instance variable.'},
                            {   'id': 'b',
                                'text': 'A class should have only one reason to change, meaning it encapsulates a '
                                        'single cohesive responsibility.'},
                            {'id': 'c', 'text': 'A class can only be instantiated once during application execution.'},
                            {'id': 'd', 'text': 'Every class must implement every interface defined in the package.'}],
        'skill': 'OOP',
        'stem': 'What does the Single Responsibility Principle (SRP) dictate regarding class design?',
        'sub_domain': 'solid_principles'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'LSP requires that objects of a superclass be replaceable with objects of its subclasses '
                       'without breaking program correctness. Strengthening preconditions or throwing new unexpected '
                       'exceptions violates this.',
        'id': 'mcq_oop_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A subclass delegates work to an injected dependency instead of inheriting '
                                        'code.'},
                            {   'id': 'b',
                                'text': 'A subclass overrides a parent method while maintaining all parent contracts '
                                        'and return types.'},
                            {   'id': 'c',
                                'text': 'A subclass strengthens preconditions or throws unexpected exceptions when '
                                        'substituted for its parent class.'},
                            {   'id': 'd',
                                'text': 'A class implements multiple small interfaces instead of one large '
                                        'interface.'}],
        'skill': 'OOP',
        'stem': 'Which scenario represents a violation of the Liskov Substitution Principle (LSP)?',
        'sub_domain': 'solid_principles'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'DIP states that high-level business policy should not depend on low-level detail modules; both '
                       'should depend on abstractions (interfaces), decoupling modules.',
        'id': 'mcq_oop_006',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Dependency graphs must form a circular loop between service layers.'},
                            {   'id': 'b',
                                'text': 'High-level modules should instantiate low-level concrete classes directly '
                                        'using constructors.'},
                            {   'id': 'c',
                                'text': 'Classes should avoid using interfaces and rely exclusively on concrete '
                                        'inheritance.'},
                            {   'id': 'd',
                                'text': 'High-level modules and low-level modules should both depend upon abstractions '
                                        'rather than concrete implementations.'}],
        'skill': 'OOP',
        'stem': 'What is the core recommendation of the Dependency Inversion Principle (DIP)?',
        'sub_domain': 'solid_principles'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Composition enables polymorphic delegation at runtime (swapping strategy objects) and prevents '
                       'deep, brittle inheritance trees where base class edits inadvertently break subclasses.',
        'id': 'mcq_oop_007',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Composition allows dynamic runtime behavior swapping and avoids fragile base '
                                        'class coupling.'},
                            {   'id': 'b',
                                'text': 'Inheritance provides faster compilation times than composition in all '
                                        'programming languages.'},
                            {   'id': 'c',
                                'text': 'Composition eliminates the need for unit testing individual component '
                                        'classes.'},
                            {   'id': 'd',
                                'text': 'Inheritance allows objects to change their parent class dynamically during '
                                        'program execution.'}],
        'skill': 'OOP',
        'stem': 'Why does object-oriented design favor composition over class inheritance when extending system '
                'behavior?',
        'sub_domain': 'design_principles'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Factory Method uses subclass inheritance to decide which single object type to instantiate, '
                       'while Abstract Factory provides an object interface with multiple factory methods to create '
                       'families of related products.',
        'id': 'mcq_oop_008',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Factory Method can only create singleton instances, whereas Abstract Factory '
                                        'creates infinite prototypes.'},
                            {   'id': 'b',
                                'text': 'Factory Method relies on inheritance to produce one product, whereas Abstract '
                                        'Factory uses composition to produce families of related products.'},
                            {   'id': 'c',
                                'text': 'Abstract Factory creates UI buttons only, while Factory Method creates '
                                        'database drivers.'},
                            {   'id': 'd',
                                'text': 'Factory Method is a structural pattern, while Abstract Factory is a '
                                        'behavioral pattern.'}],
        'skill': 'OOP',
        'stem': 'What is the primary architectural distinction between the Factory Method and Abstract Factory design '
                'patterns?',
        'sub_domain': 'design_patterns'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'hard',
        'explanation': 'The Visitor pattern uses double dispatch (element.accept(visitor) calls visitor.visit(this)) '
                       'so new operations can be added by implementing new Visitors without altering existing element '
                       'classes.',
        'id': 'mcq_oop_009',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'It converts all concrete element classes into static global procedures.'},
                            {   'id': 'b',
                                'text': 'It allows dynamically adding new element subclasses without modifying '
                                        'existing visitors.'},
                            {   'id': 'c',
                                'text': 'It allows adding new operations to existing element classes without modifying '
                                        'their source code, through double dispatch.'},
                            {   'id': 'd',
                                'text': 'It eliminates the need for element classes to expose an accept method.'}],
        'skill': 'OOP',
        'stem': 'How does the Visitor design pattern adhere to the Open/Closed Principle when operating on stable '
                'object structures?',
        'sub_domain': 'design_patterns'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'hard',
        'explanation': "ISP states that no client should be forced to depend on methods it does not use. Large 'fat' "
                       'interfaces should be decomposed into fine-grained, role-specific interfaces.',
        'id': 'mcq_oop_010',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Enforcing that interfaces contain only private static utility methods.'},
                            {   'id': 'b',
                                'text': 'Consolidating all interfaces across the entire application into a single '
                                        'universal interface.'},
                            {   'id': 'c',
                                'text': 'Providing empty dummy method implementations in every implementing class.'},
                            {   'id': 'd',
                                'text': 'Splitting monolithic interfaces into cohesive, client-specific role '
                                        'interfaces so clients only depend on methods they actually use.'}],
        'skill': 'OOP',
        'stem': 'How does applying the Interface Segregation Principle (ISP) resolve issues created by fat interfaces?',
        'sub_domain': 'solid_principles'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Threads in the same process share code, heap memory, and open file descriptors, while '
                       'maintaining their own private thread stacks and registers.',
        'id': 'mcq_os_001',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Heap memory and global static variables of the process.'},
                            {'id': 'b', 'text': "Each thread's individual call stack."},
                            {'id': 'c', 'text': "Each thread's individual CPU register state."},
                            {'id': 'd', 'text': 'Isolated virtual address spaces.'}],
        'skill': 'Operating Systems',
        'stem': 'What memory resource is shared by multiple threads executing within the same process?',
        'sub_domain': 'concurrency'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'easy',
        'explanation': 'Round Robin scheduling assigns a fixed time quantum to each ready process in a FIFO queue, '
                       'preempting the process when its quantum expires.',
        'id': 'mcq_os_002',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Shortest Job First (SJF)'},
                            {'id': 'b', 'text': 'Round Robin (RR)'},
                            {'id': 'c', 'text': 'First-Come, First-Served (FCFS)'},
                            {'id': 'd', 'text': 'Priority Scheduling without preemption'}],
        'skill': 'Operating Systems',
        'stem': 'Which CPU scheduling algorithm allocates a fixed time slice (quantum) to each runnable process in '
                'cyclic order?',
        'sub_domain': 'scheduling'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Virtual memory abstracts physical memory into private, uniform address spaces for processes '
                       'and manages mapping to physical RAM and swap storage.',
        'id': 'mcq_os_003',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'To eliminate the need for secondary disk storage devices.'},
                            {'id': 'b', 'text': 'To increase the clock frequency of the central processing unit.'},
                            {   'id': 'c',
                                'text': 'To provide each process with a large, contiguous, isolated address space '
                                        'while abstracting physical RAM.'},
                            {'id': 'd', 'text': 'To run multi-threaded programs on single-core processors.'}],
        'skill': 'Operating Systems',
        'stem': 'What is the primary architectural purpose of virtual memory in modern operating systems?',
        'sub_domain': 'memory'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Processors provide at least a less-privileged user mode and a privileged supervisor/kernel '
                       'mode. Hardware gates privileged instructions and protected resources by the current mode; x86 '
                       'rings and ARM exception levels are architecture-specific implementations of this mechanism.',
        'id': 'mcq_os_004',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Compiler-enforced type safety, which prevents applications from emitting '
                                        'privileged machine instructions.'},
                            {   'id': 'b',
                                'text': 'Process scheduling priority, which grants the highest-priority process direct '
                                        'access to protected devices.'},
                            {   'id': 'c',
                                'text': 'Virtual addressing alone, with system calls executing privileged operations '
                                        'directly in the caller\'s user mode.'},
                            {   'id': 'd',
                                'text': 'Hardware privilege modes that separate user execution from supervisor/kernel '
                                        'execution and gate privileged instructions.'}],
        'skill': 'Operating Systems',
        'stem': 'Which general hardware mechanism protects operating-system integrity from ordinary user '
                'applications across processor architectures?',
        'sub_domain': 'architecture'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'medium',
        'explanation': 'Context switching between processes requires saving registers and program counters, switching '
                       'address spaces, and flushing or invalidating TLB entries.',
        'id': 'mcq_os_011',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Saving CPU registers and invalidating/flushing Translation Lookaside Buffer '
                                        '(TLB) virtual memory mappings.'},
                            {'id': 'b', 'text': 'Re-formatting the secondary solid-state storage device.'},
                            {'id': 'c', 'text': 'Re-compiling application source code into machine instructions.'},
                            {'id': 'd', 'text': 'Re-generating cryptographic SSL certificates for network sockets.'}],
        'skill': 'Operating Systems',
        'stem': 'Which component contributes heavily to the performance overhead of an operating system process '
                'context switch?',
        'sub_domain': 'processes'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'The TLB is an on-chip associative cache that stores recent virtual page to physical frame '
                       'translations, avoiding multi-level page table walks.',
        'id': 'mcq_os_012',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'To store executable binary code for the operating system kernel.'},
                            {   'id': 'b',
                                'text': 'To act as a high-speed hardware cache for recent virtual-to-physical page '
                                        'number translations.'},
                            {   'id': 'c',
                                'text': 'To buffer dirty disk blocks before writing them to persistent storage.'},
                            {   'id': 'd',
                                'text': 'To arbitrate network packet transmission between network interface cards.'}],
        'skill': 'Operating Systems',
        'stem': 'What is the primary function of the Translation Lookaside Buffer (TLB) in CPU memory management?',
        'sub_domain': 'memory'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Deadlock requires all four Coffman conditions to occur concurrently: Mutual exclusion, Hold '
                       'and wait, No preemption, and Circular wait.',
        'id': 'mcq_os_013',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'Read, Write, Execute, and Append permissions.'},
                            {'id': 'b', 'text': 'Atomicity, Consistency, Isolation, and Durability.'},
                            {'id': 'c', 'text': 'Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.'},
                            {'id': 'd', 'text': 'FIFO, LRU, LFU, and Optimal replacement.'}],
        'skill': 'Operating Systems',
        'stem': 'What are the four Coffman conditions that must hold simultaneously for a deadlock to arise?',
        'sub_domain': 'deadlock'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'A mutex has an owner thread; only the locking thread may unlock it. A semaphore has no owner '
                       'and can be signalled by any thread.',
        'id': 'mcq_os_014',
        'negative_marking': 0.25,
        'options_json': [   {'id': 'a', 'text': 'A mutex cannot be used in multi-threaded user applications.'},
                            {'id': 'b', 'text': 'A mutex can be unlocked by any thread currently in the ready queue.'},
                            {   'id': 'c',
                                'text': 'A mutex allows multiple threads to enter the critical section '
                                        'simultaneously.'},
                            {   'id': 'd',
                                'text': 'A mutex enforces ownership: only the specific thread that acquired the mutex '
                                        'can release (unlock) it.'}],
        'skill': 'Operating Systems',
        'stem': 'What ownership property distinguishes a Mutex from a standard Binary Semaphore?',
        'sub_domain': 'synchronization'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'In multi-level paging, if a whole region of virtual memory is unused, its entire sub-tree of '
                       'page tables is omitted, saving immense amounts of RAM.',
        'id': 'mcq_os_021',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Page tables for unallocated or unused regions of the virtual address space do '
                                        'not need to be instantiated in physical memory.'},
                            {   'id': 'b',
                                'text': 'They compress page table entries using LZFSE compression in hardware.'},
                            {'id': 'c', 'text': 'They eliminate the requirement for Translation Lookaside Buffers.'},
                            {'id': 'd', 'text': 'They allow page table lookups in strictly O(1) single-cycle time.'}],
        'skill': 'Operating Systems',
        'stem': 'What is the primary memory-saving advantage of Multi-Level Page Tables over Single-Level Page Tables '
                'in a 64-bit architecture?',
        'sub_domain': 'memory'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'CFS uses a red-black tree keyed on vruntime (virtual runtime); the leftmost node represents '
                       'the task that has received the least CPU time and is scheduled next.',
        'id': 'mcq_os_022',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'A binary heap selecting the task with the largest remaining time slice.'},
                            {   'id': 'b',
                                'text': 'A self-balancing Red-Black Tree selecting the task with the smallest virtual '
                                        'runtime (vruntime).'},
                            {'id': 'c', 'text': 'A FIFO queue tracking process arrival timestamps.'},
                            {'id': 'd', 'text': 'A circular doubly linked list ordered by process ID.'}],
        'skill': 'Operating Systems',
        'stem': 'In the Linux Completely Fair Scheduler (CFS), which data structure and metric determine the next task '
                'chosen to run on the CPU?',
        'sub_domain': 'scheduling'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'easy',
        'explanation': 'Deploying known high-severity bugs risks user outages and data loss. Responsible engineering '
                       'requires halting the release, communicating transparently, and fixing the defect in staging.',
        'id': 'mcq_hr_001',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Proceed with a small canary because rollback is available, deferring full '
                                        'triage until after the scheduled launch.'},
                            {   'id': 'b',
                                'text': 'Keep the scheduled deployment but add focused monitoring and ask the on-call '
                                        'engineer to watch the affected path.'},
                            {   'id': 'c',
                                'text': 'Halt the deployment, notify stakeholders, and triage the bug in a staging '
                                        'environment before rescheduling.'},
                            {   'id': 'd',
                                'text': 'Ask the product owner to accept the risk verbally while the team prepares a '
                                        'post-deployment hotfix.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'A confirmed high-severity bug that can irreversibly corrupt customer data is discovered 15 minutes '
                'before a scheduled production deployment. What is the most responsible engineering action?',
        'sub_domain': 'release_management'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'easy',
        'explanation': 'Professional software development prioritizes organizational leverage and code reuse; '
                       'evaluating existing solutions and collaborating avoids duplicate maintenance costs.',
        'id': 'mcq_hr_002',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Review the service documentation and begin an independent prototype before '
                                        'contacting its maintainers.'},
                            {   'id': 'b',
                                'text': 'Ask your manager to transfer ownership of the existing service before doing a '
                                        'technical comparison.'},
                            {   'id': 'c',
                                'text': 'Adopt the existing API immediately based on its stated purpose, without '
                                        'checking its support model or service-level objectives.'},
                            {   'id': 'd',
                                'text': 'Reach out to the other team to evaluate their service capabilities and '
                                        'discuss integrating rather than reinventing.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'After reviewing its published documentation, you realize a feature assigned to you substantially '
                'duplicates another team\'s maintained service, but its support model and operational limits are '
                'unclear. What should you do before implementation?',
        'sub_domain': 'cross_team_collaboration'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'easy',
        'explanation': 'Clear, professional communication sets expectations without rubber-stamping unexamined code or '
                       'abandoning critical production remediation work.',
        'id': 'mcq_hr_003',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Acknowledge the review request, communicate your current focus on the '
                                        'production fix, and provide a clear time when you can review it.'},
                            {   'id': 'b',
                                'text': 'Pause the production investigation immediately and complete the review '
                                        'yourself before returning to the incident.'},
                            {   'id': 'c',
                                'text': 'Forward the request to an available engineer without explaining its context '
                                        'or confirming that they can take it.'},
                            {   'id': 'd',
                                'text': 'Leave a brief note that you will review it later, without giving a time or '
                                        'helping the teammate find another reviewer.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'A teammate asks for a code review while you are focused on an urgent production bug fix. How should '
                'you handle this request?',
        'sub_domain': 'peer_review'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'medium',
        'explanation': 'Constructive technical decision-making uses empirical evaluation criteria, architecture '
                       'decision records (ADRs), and small prototypes to resolve trade-offs objectively.',
        'id': 'mcq_hr_004',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Choose the option with the lower immediate migration cost, document it as '
                                        'temporary, and defer evaluation of operational risks.'},
                            {   'id': 'b',
                                'text': 'Define explicit technical evaluation criteria, build focused '
                                        'proofs-of-concept, and evaluate trade-offs collaboratively with the team.'},
                            {   'id': 'c',
                                'text': 'Escalate both written proposals directly to the most senior manager and accept '
                                        'their preference as the technical decision.'},
                            {   'id': 'd',
                                'text': 'Send full production traffic to both databases for a quarter before agreeing '
                                        'on success criteria or an exit plan.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'An architectural disagreement between two senior engineers regarding database selection has stalled '
                'team progress for three days. What is the most constructive resolution approach?',
        'sub_domain': 'conflict_resolution'},
    {   'correct_option_ids': ['c'],
        'difficulty': 'medium',
        'explanation': 'Incident command protocols separate active technical remediation from stakeholder management, '
                       'providing updates via designated roles without distracting engineers working on restoration.',
        'id': 'mcq_hr_005',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Share the leading hypothesis as unconfirmed, but have the primary responders '
                                        'join the executive call to answer follow-up questions.'},
                            {   'id': 'b',
                                'text': 'Pause mitigation briefly so the response team can assemble a detailed causal '
                                        'timeline for the executive.'},
                            {   'id': 'c',
                                'text': 'Provide a brief status update with known customer impact, designate a liaison '
                                        'to handle communications, and keep responders focused on mitigation.'},
                            {   'id': 'd',
                                'text': 'Defer all stakeholder communication until service is restored, then provide a '
                                        'single consolidated update before the post-mortem.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'During an ongoing major customer-facing outage, an executive demands an immediate root-cause '
                'explanation while responders are actively restoring service. How should the incident commander '
                'respond?',
        'sub_domain': 'incident_management'},
    {   'correct_option_ids': ['d'],
        'difficulty': 'medium',
        'explanation': 'Engineering integrity requires transparent risk reporting. Security vulnerabilities must be '
                       'surfaced with evidence so technical and product leaders can make informed, safe release '
                       'decisions.',
        'id': 'mcq_hr_006',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Ask the dependency team for an accelerated estimate while retaining the launch '
                                        'date until product leadership requests a formal risk review.'},
                            {   'id': 'b',
                                'text': 'Record the vulnerability in the backlog and proceed because the service is '
                                        'currently reachable only from the corporate network.'},
                            {   'id': 'c',
                                'text': 'Apply the dependency upgrade directly during an emergency production window '
                                        'before completing staging and rollback validation.'},
                            {   'id': 'd',
                                'text': 'Document the risk severity, inform security and product stakeholders, and '
                                        'recommend prioritizing the security patch over the release schedule.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'You confirm an exploitable high-risk vulnerability in an internal microservice, with no validated '
                'compensating control. Remediation requires a dependency upgrade that will delay a major feature '
                'launch by three days. What is the proper escalation path?',
        'sub_domain': 'security_governance'},
    {   'correct_option_ids': ['a'],
        'difficulty': 'hard',
        'explanation': 'A rigorous blameless review still establishes accountability for follow-through: it explains '
                       'how staging reached production, adds least-privilege and destructive-operation safeguards, and '
                       'assigns measurable actions to owners without treating one person as the root cause.',
        'id': 'mcq_hr_007',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Trace the technical and organizational conditions that let staging credentials '
                                        'reach production, add scoped credentials, dry-run and approval safeguards, '
                                        'and assign tested follow-up actions to named owners.'},
                            {   'id': 'b',
                                'text': 'Require the engineer to repeat cleanup-tool training and temporarily remove '
                                        'their access, while leaving the shared credentials and deployment path '
                                        'unchanged.'},
                            {   'id': 'c',
                                'text': 'Centralize every cleanup operation with the operations team and require a '
                                        'manager approval, without examining why environment isolation failed.'},
                            {   'id': 'd',
                                'text': 'Add a production confirmation prompt and expand backup-restore drills, but '
                                        'treat the staging-to-production credential path as outside the incident '
                                        'scope.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'A cleanup command launched from staging deleted production data because a shared credential and an '
                'environment variable selected the wrong database. Recovery succeeded. Which post-mortem action set '
                'best combines blameless analysis with accountable prevention?',
        'sub_domain': 'blameless_postmortem'},
    {   'correct_option_ids': ['b'],
        'difficulty': 'hard',
        'explanation': 'The lead should make non-waivable obligations and residual risk explicit, escalate the decision '
                       'to accountable risk owners, and offer a narrower delivery that retains essential verification. '
                       'A formal, time-bounded exception may govern genuinely waivable checks, but not silently erase '
                       'security or compliance duties.',
        'id': 'mcq_hr_008',
        'negative_marking': 0.25,
        'options_json': [   {   'id': 'a',
                                'text': 'Keep every existing gate unchanged and allow the deadline to pass before '
                                        'informing the contract owner or proposing an alternate delivery.'},
                            {   'id': 'b',
                                'text': 'Document which security or compliance controls are non-waivable, quantify the '
                                        'residual risks, escalate to accountable risk owners, and propose a scoped or '
                                        'phased delivery that retains essential gates.'},
                            {   'id': 'c',
                                'text': 'Accept a blanket temporary exception for all scans and tests, relying on '
                                        'enhanced production monitoring and rollback after the full launch.'},
                            {   'id': 'd',
                                'text': 'Replace the automated gates with one senior engineer\'s manual review so the '
                                        'full scope can ship on time without a documented exception.'}],
        'skill': 'HR/Professional Judgment',
        'stem': 'Management asks your team to waive automated security scans and integration tests to meet a contractual '
                'delivery deadline. As lead engineer, which response best balances professional duty, risk governance, '
                'and the delivery commitment?',
        'sub_domain': 'engineering_ethics'}]

PHASE2_SQL_BANK: list[dict[str, Any]] = [   {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample customer and order data',
                         'seed_data': '\n'
                                      '                    INSERT INTO customers (id, name, status) VALUES\n'
                                      "                        (1, 'Alice', 'active'),\n"
                                      "                        (2, 'Bob', 'inactive'),\n"
                                      "                        (3, 'Charlie', 'active');\n"
                                      '                    INSERT INTO orders (id, customer_id, amount) VALUES\n'
                                      '                        (1, 1, 60.0),\n'
                                      '                        (2, 1, 55.0),\n'
                                      '                        (3, 2, 200.0),\n'
                                      '                        (4, 3, 40.0);\n'
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Boundary at 100.0 and multiple orders',
                         'seed_data': '\n'
                                      '                    INSERT INTO customers (id, name, status) VALUES\n'
                                      "                        (1, 'Dave', 'active'),\n"
                                      "                        (2, 'Erin', 'active'),\n"
                                      "                        (3, 'Faythe', 'active');\n"
                                      '                    INSERT INTO orders (id, customer_id, amount) VALUES\n'
                                      '                        (1, 1, 100.0),\n'
                                      '                        (2, 2, 100.01),\n'
                                      '                        (3, 3, 50.0),\n'
                                      '                        (4, 3, 50.01);\n'
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'All inactive or zero matching rows',
                         'seed_data': '\n'
                                      '                    INSERT INTO customers (id, name, status) VALUES\n'
                                      "                        (1, 'Grace', 'inactive'),\n"
                                      "                        (2, 'Heidi', 'pending');\n"
                                      '                    INSERT INTO orders (id, customer_id, amount) VALUES\n'
                                      '                        (1, 1, 500.0),\n'
                                      '                        (2, 2, 600.0);\n'
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_001',
        'prompt': '### High-Value Customers\n'
                  '\n'
                  'Write a query to find the names and total spending of active customers who have spent strictly more '
                  'than 100 in total across all their orders.\n'
                  '\n'
                  '**Output columns:** `name`, `total_spent`\n'
                  '\n'
                  'Order results by `total_spent` in descending order, then by `name` in ascending order.',
        'reference_query': '\n'
                           '            SELECT c.name, SUM(o.amount) AS total_spent\n'
                           '            FROM customers c\n'
                           '            JOIN orders o ON c.id = o.customer_id\n'
                           "            WHERE c.status = 'active'\n"
                           '            GROUP BY c.id, c.name\n'
                           '            HAVING SUM(o.amount) > 100\n'
                           '            ORDER BY total_spent DESC, c.name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE customers (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                status TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE orders (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                customer_id INTEGER NOT NULL,\n'
                      '                amount REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample employees and departments',
                         'seed_data': '\n'
                                      '                    INSERT INTO departments (id, name) VALUES (1, '
                                      "'Engineering'), (2, 'Sales');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Alice', 1, 75000),\n"
                                      "                        (2, 'Bob', 2, 48000),\n"
                                      "                        (3, 'Charlie', 1, 50000);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Tied salaries and varied departments',
                         'seed_data': '\n'
                                      "                    INSERT INTO departments (id, name) VALUES (1, 'HR'), (2, "
                                      "'Finance'), (3, 'Legal');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Dan', 1, 60000),\n"
                                      "                        (2, 'Carol', 2, 60000),\n"
                                      "                        (3, 'Eve', 3, 90000),\n"
                                      "                        (4, 'Frank', 1, 30000);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Boundary check exactly 50000 and below',
                         'seed_data': '\n'
                                      '                    INSERT INTO departments (id, name) VALUES (10, '
                                      "'Operations');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Grace', 10, 49999.99),\n"
                                      "                        (2, 'Hank', 10, 50000.00);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_002',
        'prompt': '### Employee Department Directory\n'
                  '\n'
                  'Write a query to list the employee name, department name, and salary for all employees whose salary '
                  'is at least 50000.\n'
                  '\n'
                  '**Output columns:** `employee_name`, `department_name`, `salary`\n'
                  '\n'
                  'Order by `salary` descending, then `employee_name` ascending.',
        'reference_query': '\n'
                           '            SELECT e.name AS employee_name, d.name AS department_name, e.salary\n'
                           '            FROM employees e\n'
                           '            JOIN departments d ON e.department_id = d.id\n'
                           '            WHERE e.salary >= 50000\n'
                           '            ORDER BY e.salary DESC, employee_name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE departments (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                department_id INTEGER NOT NULL,\n'
                      '                salary REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample product inventory',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category, stock_quantity) '
                                      'VALUES\n'
                                      "                        (1, 'Laptop', 'Electronics', 5),\n"
                                      "                        (2, 'Mouse', 'Electronics', 10),\n"
                                      "                        (3, 'Desk', 'Furniture', 3),\n"
                                      "                        (4, 'Pen', NULL, 100);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Exact threshold 10 and null categories',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category, stock_quantity) '
                                      'VALUES\n'
                                      "                        (1, 'Chair', 'Furniture', 10),\n"
                                      "                        (2, 'Sofa', 'Furniture', 1),\n"
                                      "                        (3, 'Apples', 'Grocery', 10),\n"
                                      "                        (4, 'Oranges', 'Grocery', 0),\n"
                                      "                        (5, 'Notebook', 'Stationery', 25);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'All categories below threshold',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category, stock_quantity) '
                                      'VALUES\n'
                                      "                        (1, 'Item A', 'CatA', 2),\n"
                                      "                        (2, 'Item B', 'CatA', 3),\n"
                                      "                        (3, 'Item C', 'CatB', 9);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_003',
        'prompt': '### Product Category Inventory\n'
                  '\n'
                  'Write a query to calculate total stock quantity per product category for categories where category '
                  'is not null and total stock exceeds 10 units.\n'
                  '\n'
                  '**Output columns:** `category`, `total_stock`\n'
                  '\n'
                  'Order by `total_stock` descending, then `category` ascending.',
        'reference_query': '\n'
                           '            SELECT category, SUM(stock_quantity) AS total_stock\n'
                           '            FROM products\n'
                           '            WHERE category IS NOT NULL\n'
                           '            GROUP BY category\n'
                           '            HAVING SUM(stock_quantity) > 10\n'
                           '            ORDER BY total_stock DESC, category ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE products (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                category TEXT,\n'
                      '                stock_quantity INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample books across publishers',
                         'seed_data': '\n'
                                      '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                                      "                        (1, 'Book A', 'OReilly', 45.50),\n"
                                      "                        (2, 'Book B', 'OReilly', 54.50),\n"
                                      "                        (3, 'Book C', 'Manning', 39.99),\n"
                                      "                        (4, 'Book D', 'Addison-Wesley', 60.00);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple publishers with varying book counts',
                         'seed_data': '\n'
                                      '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                                      "                        (1, 'Book 1', 'Manning', 40.00),\n"
                                      "                        (2, 'Book 2', 'Manning', 50.00),\n"
                                      "                        (3, 'Book 3', 'Manning', 60.00),\n"
                                      "                        (4, 'Book 4', 'Packt', 25.00),\n"
                                      "                        (5, 'Book 5', 'Packt', 35.00),\n"
                                      "                        (6, 'Book 6', 'Springer', 120.00);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Decimal rounding verification',
                         'seed_data': '\n'
                                      '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                                      "                        (1, 'Intro', 'TechPress', 10.333),\n"
                                      "                        (2, 'Advanced', 'TechPress', 20.333);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_004',
        'prompt': '### Average Book Price by Publisher\n'
                  '\n'
                  'Write a query to find the rounded average book price (to 2 decimal places) for publishers that have '
                  'published at least 2 books.\n'
                  '\n'
                  '**Output columns:** `publisher`, `avg_price`\n'
                  '\n'
                  'Order by `avg_price` descending, then `publisher` ascending.',
        'reference_query': '\n'
                           '            SELECT publisher, ROUND(AVG(price), 2) AS avg_price\n'
                           '            FROM books\n'
                           '            GROUP BY publisher\n'
                           '            HAVING COUNT(*) >= 2\n'
                           '            ORDER BY avg_price DESC, publisher ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE books (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                title TEXT NOT NULL,\n'
                      '                publisher TEXT NOT NULL,\n'
                      '                price REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample users and login timestamps',
                         'seed_data': '\n'
                                      "                    INSERT INTO users (id, username) VALUES (1, 'alice'), (2, "
                                      "'bob'), (3, 'charlie');\n"
                                      '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                                      "                        (1, 1, '2026-01-01 10:00:00'),\n"
                                      "                        (2, 1, '2026-01-02 12:00:00'),\n"
                                      "                        (3, 2, '2026-01-01 08:30:00');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'User without logins and out-of-order timestamps',
                         'seed_data': '\n'
                                      "                    INSERT INTO users (id, username) VALUES (1, 'zara'), (2, "
                                      "'adam'), (3, 'no_login');\n"
                                      '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                                      "                        (1, 1, '2026-02-15 09:00:00'),\n"
                                      "                        (2, 1, '2026-02-10 11:00:00'),\n"
                                      "                        (3, 2, '2026-01-20 14:00:00');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single login per user',
                         'seed_data': '\n'
                                      "                    INSERT INTO users (id, username) VALUES (1, 'echo'), (2, "
                                      "'delta');\n"
                                      '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                                      "                        (1, 1, '2026-03-01 00:00:00'),\n"
                                      "                        (2, 2, '2026-03-02 00:00:00');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_005',
        'prompt': '### Most Recent User Login\n'
                  '\n'
                  'Write a query to find the username and latest login timestamp for each user who has at least one '
                  'recorded login.\n'
                  '\n'
                  '**Output columns:** `username`, `last_login`\n'
                  '\n'
                  'Order by `username` in ascending alphabetical order.',
        'reference_query': '\n'
                           '            SELECT u.username, MAX(l.login_timestamp) AS last_login\n'
                           '            FROM users u\n'
                           '            JOIN logins l ON u.id = l.user_id\n'
                           '            GROUP BY u.id, u.username\n'
                           '            ORDER BY u.username ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE users (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                username TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE logins (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                user_id INTEGER NOT NULL,\n'
                      '                login_timestamp TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample sales data with 4 products',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name) VALUES\n'
                                      "                        (1, 'Keyboard'), (2, 'Monitor'), (3, 'Mouse'), (4, "
                                      "'Headphones');\n"
                                      '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                                      '                        (1, 1, 10), (2, 2, 5), (3, 3, 15), (4, 4, 8), (5, 1, '
                                      '5);\n'
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Tie breaker on name and multiple orders',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name) VALUES\n'
                                      "                        (1, 'Alpha'), (2, 'Beta'), (3, 'Gamma'), (4, 'Delta');\n"
                                      '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                                      '                        (1, 1, 20), (2, 2, 20), (3, 3, 30), (4, 4, 5);\n'
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Fewer than 3 products in database',
                         'seed_data': '\n'
                                      "                    INSERT INTO products (id, name) VALUES (1, 'Solo'), (2, "
                                      "'Duo');\n"
                                      '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                                      '                        (1, 1, 50), (2, 2, 25);\n'
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_006',
        'prompt': '### Top Selling Products by Volume\n'
                  '\n'
                  'Write a query to retrieve the top 3 selling products based on total units sold.\n'
                  '\n'
                  '**Output columns:** `name`, `total_sold`\n'
                  '\n'
                  'Order by `total_sold` descending, then `name` ascending. Limit to 3 rows.',
        'reference_query': '\n'
                           '            SELECT p.name, SUM(oi.quantity) AS total_sold\n'
                           '            FROM products p\n'
                           '            JOIN order_items oi ON p.id = oi.product_id\n'
                           '            GROUP BY p.id, p.name\n'
                           '            ORDER BY total_sold DESC, p.name ASC\n'
                           '            LIMIT 3;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE products (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE order_items (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                product_id INTEGER NOT NULL,\n'
                      '                quantity INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample tickets with mixed priorities and assignments',
                         'seed_data': '\n'
                                      '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                                      "                        (1, 'Server down', NULL, 'high'),\n"
                                      "                        (2, 'Email bounce', 3, 'high'),\n"
                                      "                        (3, 'Password reset', NULL, 'low'),\n"
                                      "                        (4, 'Data loss', NULL, 'high');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'All tickets assigned or non-high priority',
                         'seed_data': '\n'
                                      '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                                      "                        (10, 'Bug A', 1, 'high'),\n"
                                      "                        (11, 'Bug B', NULL, 'medium'),\n"
                                      "                        (12, 'Bug C', 2, 'low');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple unassigned high priority tickets',
                         'seed_data': '\n'
                                      '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                                      "                        (101, 'Outage Alpha', NULL, 'high'),\n"
                                      "                        (102, 'Outage Beta', NULL, 'high'),\n"
                                      "                        (103, 'Outage Gamma', NULL, 'high');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_007',
        'prompt': '### Unassigned High-Priority Tickets\n'
                  '\n'
                  "Write a query to list the id and title of all support tickets with 'high' priority that have not "
                  'been assigned to any agent (`agent_id` is NULL).\n'
                  '\n'
                  '**Output columns:** `id`, `title`\n'
                  '\n'
                  'Order by `id` ascending.',
        'reference_query': '\n'
                           '            SELECT id, title\n'
                           '            FROM tickets\n'
                           "            WHERE agent_id IS NULL AND priority = 'high'\n"
                           '            ORDER BY id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE tickets (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                title TEXT NOT NULL,\n'
                      '                agent_id INTEGER,\n'
                      '                priority TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample students and exam scores',
                         'seed_data': '\n'
                                      "                    INSERT INTO students (id, name) VALUES (1, 'Alice'), (2, "
                                      "'Bob'), (3, 'Charlie');\n"
                                      '                    INSERT INTO exam_scores (id, student_id, subject, score) '
                                      'VALUES\n'
                                      "                        (1, 1, 'Math', 85),\n"
                                      "                        (2, 1, 'Physics', 60),\n"
                                      "                        (3, 2, 'Math', 55),\n"
                                      "                        (4, 3, 'Chemistry', 92);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Threshold boundary at 59 and 60',
                         'seed_data': '\n'
                                      "                    INSERT INTO students (id, name) VALUES (1, 'Dan'), (2, "
                                      "'Emma');\n"
                                      '                    INSERT INTO exam_scores (id, student_id, subject, score) '
                                      'VALUES\n'
                                      "                        (1, 1, 'Biology', 59),\n"
                                      "                        (2, 1, 'History', 60),\n"
                                      "                        (3, 2, 'History', 59);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Equal passed counts checking tie break',
                         'seed_data': '\n'
                                      "                    INSERT INTO students (id, name) VALUES (1, 'Zack'), (2, "
                                      "'Abby');\n"
                                      '                    INSERT INTO exam_scores (id, student_id, subject, score) '
                                      'VALUES\n'
                                      "                        (1, 1, 'Art', 70),\n"
                                      "                        (2, 2, 'Art', 75);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_008',
        'prompt': '### Student Exam Pass Summary\n'
                  '\n'
                  "Write a query to list each student's name and the total number of exams they have passed (where "
                  '`score` >= 60). Include only students who have at least one passed exam.\n'
                  '\n'
                  '**Output columns:** `name`, `passed_count`\n'
                  '\n'
                  'Order by `passed_count` descending, then `name` ascending.',
        'reference_query': '\n'
                           '            SELECT s.name, COUNT(*) AS passed_count\n'
                           '            FROM students s\n'
                           '            JOIN exam_scores e ON s.id = e.student_id\n'
                           '            WHERE e.score >= 60\n'
                           '            GROUP BY s.id, s.name\n'
                           '            ORDER BY passed_count DESC, s.name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE students (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE exam_scores (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                student_id INTEGER NOT NULL,\n'
                      '                subject TEXT NOT NULL,\n'
                      '                score INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample page views across multiple dates',
                         'seed_data': '\n'
                                      '                    INSERT INTO page_views (id, visitor_id, view_date, '
                                      'page_url) VALUES\n'
                                      "                        (1, 101, '2026-03-01', '/checkout/step1'),\n"
                                      "                        (2, 101, '2026-03-01', '/checkout/step2'),\n"
                                      "                        (3, 102, '2026-03-01', '/home'),\n"
                                      "                        (4, 103, '2026-03-01', '/checkout/pay'),\n"
                                      "                        (5, 101, '2026-03-02', '/checkout/step1');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'URL pattern matching and deduplication',
                         'seed_data': '\n'
                                      '                    INSERT INTO page_views (id, visitor_id, view_date, '
                                      'page_url) VALUES\n'
                                      "                        (1, 1, '2026-04-10', '/checkout'),\n"
                                      "                        (2, 1, '2026-04-10', '/checkout/confirm'),\n"
                                      "                        (3, 2, '2026-04-10', '/products/checkout-item'),\n"
                                      "                        (4, 3, '2026-04-11', '/checkout');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'No checkout visits',
                         'seed_data': '\n'
                                      '                    INSERT INTO page_views (id, visitor_id, view_date, '
                                      'page_url) VALUES\n'
                                      "                        (1, 5, '2026-05-01', '/about'),\n"
                                      "                        (2, 6, '2026-05-01', '/contact');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_009',
        'prompt': '### Unique Daily Checkout Visitors\n'
                  '\n'
                  "Write a query to count the number of unique visitors who visited any page starting with '/checkout' "
                  'on each day.\n'
                  '\n'
                  '**Output columns:** `view_date`, `unique_visitors`\n'
                  '\n'
                  'Order by `view_date` ascending.',
        'reference_query': '\n'
                           '            SELECT view_date, COUNT(DISTINCT visitor_id) AS unique_visitors\n'
                           '            FROM page_views\n'
                           "            WHERE page_url LIKE '/checkout%'\n"
                           '            GROUP BY view_date\n'
                           '            ORDER BY view_date ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE page_views (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                visitor_id INTEGER NOT NULL,\n'
                      '                view_date TEXT NOT NULL,\n'
                      '                page_url TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample warehouses and inventory counts',
                         'seed_data': '\n'
                                      "                    INSERT INTO warehouses (id, city) VALUES (1, 'Chicago'), "
                                      "(2, 'Dallas'), (3, 'Seattle');\n"
                                      '                    INSERT INTO inventory (id, warehouse_id, item_sku, '
                                      'quantity) VALUES\n'
                                      "                        (1, 1, 'SKU-01', 300),\n"
                                      "                        (2, 1, 'SKU-02', 250),\n"
                                      "                        (3, 2, 'SKU-01', 100),\n"
                                      "                        (4, 3, 'SKU-03', 500);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Exact 500 threshold and multiple warehouses',
                         'seed_data': '\n'
                                      "                    INSERT INTO warehouses (id, city) VALUES (1, 'Boston'), (2, "
                                      "'Austin');\n"
                                      '                    INSERT INTO inventory (id, warehouse_id, item_sku, '
                                      'quantity) VALUES\n'
                                      "                        (1, 1, 'A', 499),\n"
                                      "                        (2, 2, 'B', 250),\n"
                                      "                        (3, 2, 'C', 250);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Tied totals verifying alphabetical city tie break',
                         'seed_data': '\n'
                                      "                    INSERT INTO warehouses (id, city) VALUES (1, 'Denver'), (2, "
                                      "'Atlanta');\n"
                                      '                    INSERT INTO inventory (id, warehouse_id, item_sku, '
                                      'quantity) VALUES\n'
                                      "                        (1, 1, 'X', 600),\n"
                                      "                        (2, 2, 'Y', 600);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'easy',
        'id': 'sql_prob_010',
        'prompt': '### High Volume Warehouses\n'
                  '\n'
                  'Write a query to calculate total inventory quantity per warehouse city for warehouses holding at '
                  'least 500 total items.\n'
                  '\n'
                  '**Output columns:** `city`, `total_quantity`\n'
                  '\n'
                  'Order by `total_quantity` descending, then `city` ascending.',
        'reference_query': '\n'
                           '            SELECT w.city, SUM(i.quantity) AS total_quantity\n'
                           '            FROM warehouses w\n'
                           '            JOIN inventory i ON w.id = i.warehouse_id\n'
                           '            GROUP BY w.id, w.city\n'
                           '            HAVING SUM(i.quantity) >= 500\n'
                           '            ORDER BY total_quantity DESC, w.city ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE warehouses (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                city TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE inventory (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                warehouse_id INTEGER NOT NULL,\n'
                      '                item_sku TEXT NOT NULL,\n'
                      '                quantity INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample transactions across months',
                         'seed_data': '\n'
                                      '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                                      "                        (1, 600.0, '2026-01-05'),\n"
                                      "                        (2, 500.0, '2026-01-15'),\n"
                                      "                        (3, -50.0, '2026-01-20'),\n"
                                      "                        (4, 800.0, '2026-02-01'),\n"
                                      "                        (5, 150.0, '2026-02-14');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple months meeting threshold and negative transaction filtering',
                         'seed_data': '\n'
                                      '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                                      "                        (1, 1000.0, '2026-03-01'),\n"
                                      "                        (2, 400.0, '2026-04-01'),\n"
                                      "                        (3, 700.0, '2026-04-15'),\n"
                                      "                        (4, -200.0, '2026-04-20'),\n"
                                      "                        (5, 999.99, '2026-05-10');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'All months below threshold or negative amounts',
                         'seed_data': '\n'
                                      '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                                      "                        (1, 200.0, '2026-06-01'),\n"
                                      "                        (2, 300.0, '2026-06-02'),\n"
                                      "                        (3, -1500.0, '2026-06-03');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_011',
        'prompt': '### Monthly Revenue Aggregation\n'
                  '\n'
                  'Write a query to calculate monthly revenue trends from positive transactions (`amount` > 0). For '
                  'each month with at least 1000 in total revenue, return the month string (`YYYY-MM`), count of '
                  'transactions, and total revenue rounded to 2 decimal places.\n'
                  '\n'
                  '**Output columns:** `month`, `tx_count`, `total_revenue`\n'
                  '\n'
                  'Order by `month` in ascending order.',
        'reference_query': '\n'
                           '            SELECT\n'
                           "                strftime('%Y-%m', tx_date) AS month,\n"
                           '                COUNT(*) AS tx_count,\n'
                           '                ROUND(SUM(amount), 2) AS total_revenue\n'
                           '            FROM transactions\n'
                           '            WHERE amount > 0\n'
                           "            GROUP BY strftime('%Y-%m', tx_date)\n"
                           '            HAVING SUM(amount) >= 1000\n'
                           '            ORDER BY month ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE transactions (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                amount REAL NOT NULL,\n'
                      '                tx_date TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample employees with distinct salaries',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, department, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Alice', 'Tech', 100),\n"
                                      "                        (2, 'Bob', 'Tech', 200),\n"
                                      "                        (3, 'Charlie', 'HR', 300);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Duplicate top salaries testing distinct requirement',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, department, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Dave', 'Finance', 500),\n"
                                      "                        (2, 'Erin', 'Finance', 500),\n"
                                      "                        (3, 'Frank', 'Sales', 400),\n"
                                      "                        (4, 'Grace', 'Sales', 300);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Only one distinct salary in table (should return NULL)',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, department, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Hank', 'IT', 100),\n"
                                      "                        (2, 'Ivy', 'IT', 100);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': False},
        'difficulty': 'medium',
        'id': 'sql_prob_012',
        'prompt': '### Second Highest Distinct Salary\n'
                  '\n'
                  'Write a query to find the second highest distinct salary among all employees. If there is no second '
                  'highest salary, return NULL as `second_highest_salary`.\n'
                  '\n'
                  '**Output columns:** `second_highest_salary`',
        'reference_query': '\n'
                           '            SELECT (\n'
                           '                SELECT DISTINCT salary\n'
                           '                FROM employees\n'
                           '                ORDER BY salary DESC\n'
                           '                LIMIT 1 OFFSET 1\n'
                           '            ) AS second_highest_salary;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                department TEXT NOT NULL,\n'
                      '                salary REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample orders across 2024, 2025, and 2026',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, customer_id, order_date, '
                                      'total_amount) VALUES\n'
                                      "                        (1, 101, '2024-05-10', 50.0),\n"
                                      "                        (2, 101, '2025-01-15', 75.0),\n"
                                      "                        (3, 102, '2024-11-20', 100.0),\n"
                                      "                        (4, 103, '2025-03-01', 20.0),\n"
                                      "                        (5, 104, '2026-01-01', 10.0);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple orders per year and boundary years',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, customer_id, order_date, '
                                      'total_amount) VALUES\n'
                                      "                        (1, 1, '2024-01-01', 10.0),\n"
                                      "                        (2, 1, '2024-12-31', 20.0),\n"
                                      "                        (3, 1, '2025-01-01', 30.0),\n"
                                      "                        (4, 2, '2023-12-31', 100.0),\n"
                                      "                        (5, 2, '2024-06-01', 100.0),\n"
                                      "                        (6, 3, '2025-06-01', 50.0),\n"
                                      "                        (7, 4, '2024-03-01', 15.0),\n"
                                      "                        (8, 4, '2025-09-01', 25.0);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'No customer meeting condition',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, customer_id, order_date, '
                                      'total_amount) VALUES\n'
                                      "                        (1, 10, '2023-05-01', 50.0),\n"
                                      "                        (2, 20, '2026-05-01', 50.0);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_013',
        'prompt': '### Multi-Year Repeat Customers\n'
                  '\n'
                  'Write a query to find the customer IDs of customers who placed at least one order in 2024 AND at '
                  'least one order in 2025.\n'
                  '\n'
                  '**Output columns:** `customer_id`\n'
                  '\n'
                  'Order by `customer_id` ascending.',
        'reference_query': '\n'
                           '            SELECT customer_id\n'
                           '            FROM orders\n'
                           '            GROUP BY customer_id\n'
                           "            HAVING SUM(CASE WHEN strftime('%Y', order_date) = '2024' THEN 1 ELSE 0 END) > "
                           '0\n'
                           "               AND SUM(CASE WHEN strftime('%Y', order_date) = '2025' THEN 1 ELSE 0 END) > "
                           '0\n'
                           '            ORDER BY customer_id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE orders (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                customer_id INTEGER NOT NULL,\n'
                      '                order_date TEXT NOT NULL,\n'
                      '                total_amount REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample employees with distinct maximum salaries per dept',
                         'seed_data': '\n'
                                      '                    INSERT INTO departments (id, name) VALUES (1, '
                                      "'Engineering'), (2, 'Sales');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Alice', 1, 90000),\n"
                                      "                        (2, 'Bob', 1, 80000),\n"
                                      "                        (3, 'Charlie', 2, 70000),\n"
                                      "                        (4, 'David', 2, 65000);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Tied highest salaries within the same department',
                         'seed_data': '\n'
                                      "                    INSERT INTO departments (id, name) VALUES (1, 'Design'), "
                                      "(2, 'Marketing');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Zoe', 1, 85000),\n"
                                      "                        (2, 'Amy', 1, 85000),\n"
                                      "                        (3, 'Brian', 1, 70000),\n"
                                      "                        (4, 'Chloe', 2, 95000);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single employee per department',
                         'seed_data': '\n'
                                      "                    INSERT INTO departments (id, name) VALUES (1, 'Support');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      "VALUES (1, 'Solo', 1, 50000);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_014',
        'prompt': '### Department Highest Earners\n'
                  '\n'
                  'Write a query to find the employees who earn the highest salary in each department. If there are '
                  'ties for the maximum salary in a department, include all tied employees.\n'
                  '\n'
                  '**Output columns:** `department_name`, `employee_name`, `salary`\n'
                  '\n'
                  'Order by `department_name` ascending, then `employee_name` ascending.',
        'reference_query': '\n'
                           '            SELECT d.name AS department_name, e.name AS employee_name, e.salary\n'
                           '            FROM employees e\n'
                           '            JOIN departments d ON e.department_id = d.id\n'
                           '            WHERE (e.department_id, e.salary) IN (\n'
                           '                SELECT department_id, MAX(salary)\n'
                           '                FROM employees\n'
                           '                GROUP BY department_id\n'
                           '            )\n'
                           '            ORDER BY department_name ASC, employee_name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE departments (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                department_id INTEGER NOT NULL,\n'
                      '                salary REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample transactions for two accounts',
                         'seed_data': '\n'
                                      '                    INSERT INTO bank_transactions (id, account_id, tx_date, '
                                      'amount) VALUES\n'
                                      "                        (1, 100, '2026-01-01', 500.0),\n"
                                      "                        (2, 100, '2026-01-02', -100.0),\n"
                                      "                        (3, 100, '2026-01-03', 250.0),\n"
                                      "                        (4, 200, '2026-01-01', 1000.0),\n"
                                      "                        (5, 200, '2026-01-05', -400.0);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple transactions on the same date with tie breaking by id',
                         'seed_data': '\n'
                                      '                    INSERT INTO bank_transactions (id, account_id, tx_date, '
                                      'amount) VALUES\n'
                                      "                        (1, 1, '2026-02-01', 100.0),\n"
                                      "                        (2, 1, '2026-02-01', 50.0),\n"
                                      "                        (3, 1, '2026-02-01', -20.0),\n"
                                      "                        (4, 2, '2026-02-01', 500.0);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Negative starting balances and fluctuating balances',
                         'seed_data': '\n'
                                      '                    INSERT INTO bank_transactions (id, account_id, tx_date, '
                                      'amount) VALUES\n'
                                      "                        (1, 5, '2026-03-01', -50.0),\n"
                                      "                        (2, 5, '2026-03-02', 100.0),\n"
                                      "                        (3, 5, '2026-03-03', -100.0);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_015',
        'prompt': '### Running Balance of Bank Accounts\n'
                  '\n'
                  'Write a query to calculate the cumulative running balance for each bank account over time.\n'
                  '\n'
                  '**Output columns:** `account_id`, `id`, `tx_date`, `amount`, `running_balance`\n'
                  '\n'
                  'Order by `account_id` ascending, `tx_date` ascending, and `id` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                account_id,\n'
                           '                id,\n'
                           '                tx_date,\n'
                           '                amount,\n'
                           '                SUM(amount) OVER (\n'
                           '                    PARTITION BY account_id\n'
                           '                    ORDER BY tx_date ASC, id ASC\n'
                           '                ) AS running_balance\n'
                           '            FROM bank_transactions\n'
                           '            ORDER BY account_id ASC, tx_date ASC, id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE bank_transactions (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                account_id INTEGER NOT NULL,\n'
                      '                tx_date TEXT NOT NULL,\n'
                      '                amount REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample orders with multi-day intervals',
                         'seed_data': '\n'
                                      '                    INSERT INTO customer_orders (id, customer_id, order_date) '
                                      'VALUES\n'
                                      "                        (1, 10, '2026-01-01'),\n"
                                      "                        (2, 10, '2026-01-05'),\n"
                                      "                        (3, 10, '2026-01-15'),\n"
                                      "                        (4, 20, '2026-02-01');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Orders on consecutive days and same customer multiple orders',
                         'seed_data': '\n'
                                      '                    INSERT INTO customer_orders (id, customer_id, order_date) '
                                      'VALUES\n'
                                      "                        (1, 1, '2026-03-01'),\n"
                                      "                        (2, 1, '2026-03-02'),\n"
                                      "                        (3, 1, '2026-03-10'),\n"
                                      "                        (4, 2, '2026-03-05'),\n"
                                      "                        (5, 2, '2026-03-25');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'All customers have only one order (all NULL days_since_prev)',
                         'seed_data': '\n'
                                      '                    INSERT INTO customer_orders (id, customer_id, order_date) '
                                      'VALUES\n'
                                      "                        (1, 100, '2026-04-01'),\n"
                                      "                        (2, 200, '2026-04-02');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_016',
        'prompt': '### Days Between Consecutive Customer Orders\n'
                  '\n'
                  "Write a query to calculate the number of days elapsed between each customer's consecutive orders. "
                  "For a customer's first order, `days_since_prev` should be NULL.\n"
                  '\n'
                  '**Output columns:** `customer_id`, `id`, `order_date`, `days_since_prev`\n'
                  '\n'
                  'Order by `customer_id` ascending, `order_date` ascending, and `id` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                customer_id,\n'
                           '                id,\n'
                           '                order_date,\n'
                           '                CAST(\n'
                           '                    ROUND(\n'
                           '                        julianday(order_date) - julianday(\n'
                           '                            LAG(order_date) OVER (\n'
                           '                                PARTITION BY customer_id\n'
                           '                                ORDER BY order_date ASC, id ASC\n'
                           '                            )\n'
                           '                        )\n'
                           '                    ) AS INTEGER\n'
                           '                ) AS days_since_prev\n'
                           '            FROM customer_orders\n'
                           '            ORDER BY customer_id ASC, order_date ASC, id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE customer_orders (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                customer_id INTEGER NOT NULL,\n'
                      '                order_date TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample products across two categories',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                                      "                        (1, 'Laptop', 1, 1200.0),\n"
                                      "                        (2, 'Keyboard', 1, 80.0),\n"
                                      "                        (3, 'Mouse', 1, 40.0),\n"
                                      "                        (4, 'Desk', 2, 350.0),\n"
                                      "                        (5, 'Chair', 2, 150.0);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Categories where all products have identical prices (no above average)',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                                      "                        (1, 'Apple', 10, 2.0),\n"
                                      "                        (2, 'Banana', 10, 2.0),\n"
                                      "                        (3, 'Carrot', 20, 5.0),\n"
                                      "                        (4, 'Dill', 20, 10.0);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple categories with tie breaks',
                         'seed_data': '\n'
                                      '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                                      "                        (1, 'Pro A', 100, 50.0),\n"
                                      "                        (2, 'Pro B', 100, 50.0),\n"
                                      "                        (3, 'Basic', 100, 20.0);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_017',
        'prompt': '### Above Average Category Products\n'
                  '\n'
                  'Write a query to find products whose price is strictly greater than the average price of all '
                  'products within their category.\n'
                  '\n'
                  '**Output columns:** `name`, `category_id`, `price`\n'
                  '\n'
                  'Order by `category_id` ascending, then `price` descending, then `name` ascending.',
        'reference_query': '\n'
                           '            SELECT p.name, p.category_id, p.price\n'
                           '            FROM products p\n'
                           '            JOIN (\n'
                           '                SELECT category_id, AVG(price) AS avg_cat_price\n'
                           '                FROM products\n'
                           '                GROUP BY category_id\n'
                           '            ) c ON p.category_id = c.category_id\n'
                           '            WHERE p.price > c.avg_cat_price\n'
                           '            ORDER BY p.category_id ASC, p.price DESC, p.name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE products (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                category_id INTEGER NOT NULL,\n'
                      '                price REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample users with active and inactive timelines',
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, username, created_at) VALUES\n'
                                      "                        (1, 'alice', '2025-01-01'),\n"
                                      "                        (2, 'bob', '2025-02-01'),\n"
                                      "                        (3, 'charlie', '2025-03-01');\n"
                                      '                    INSERT INTO activity_logs (id, user_id, activity_date) '
                                      'VALUES\n'
                                      "                        (1, 1, '2025-05-15'),\n"
                                      "                        (2, 2, '2025-07-20');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': "Boundary date exactly '2025-06-01' and users with zero logs",
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, username, created_at) VALUES\n'
                                      "                        (1, 'david', '2025-01-10'),\n"
                                      "                        (2, 'emma', '2025-02-15'),\n"
                                      "                        (3, 'frank', '2025-03-20');\n"
                                      '                    INSERT INTO activity_logs (id, user_id, activity_date) '
                                      'VALUES\n'
                                      "                        (1, 1, '2025-06-01'),\n"
                                      "                        (2, 2, '2025-06-02');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'All users active after the threshold date',
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, username, created_at) VALUES\n'
                                      "                        (1, 'grace', '2025-04-01'),\n"
                                      "                        (2, 'hank', '2025-04-01');\n"
                                      '                    INSERT INTO activity_logs (id, user_id, activity_date) '
                                      'VALUES\n'
                                      "                        (1, 1, '2025-08-01'),\n"
                                      "                        (2, 2, '2025-09-01');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_018',
        'prompt': '### Inactive User Detection\n'
                  '\n'
                  "Write a query to find all users who have had zero activity after '2025-06-01' (including users who "
                  'have never logged any activity at all).\n'
                  '\n'
                  '**Output columns:** `username`, `created_at`\n'
                  '\n'
                  'Order by `username` ascending.',
        'reference_query': '\n'
                           '            SELECT u.username, u.created_at\n'
                           '            FROM users u\n'
                           '            WHERE u.id NOT IN (\n'
                           '                SELECT DISTINCT user_id\n'
                           '                FROM activity_logs\n'
                           "                WHERE activity_date > '2025-06-01'\n"
                           '            )\n'
                           '            ORDER BY u.username ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE users (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                username TEXT NOT NULL,\n'
                      '                created_at TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE activity_logs (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                user_id INTEGER NOT NULL,\n'
                      '                activity_date TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample manager hierarchy with salary disparities',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, salary, manager_id) '
                                      'VALUES\n'
                                      "                        (1, 'Boss', 70000, NULL),\n"
                                      "                        (2, 'Lead Dev', 80000, 1),\n"
                                      "                        (3, 'Junior Dev', 50000, 2),\n"
                                      "                        (4, 'Senior Dev', 90000, 2);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Equal salaries (should not qualify as strictly less)',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, salary, manager_id) '
                                      'VALUES\n'
                                      "                        (10, 'Director', 100000, NULL),\n"
                                      "                        (20, 'Manager A', 100000, 10),\n"
                                      "                        (30, 'Staff', 95000, 20);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple subordinate violations per manager',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, salary, manager_id) '
                                      'VALUES\n'
                                      "                        (1, 'Lead', 60000, NULL),\n"
                                      "                        (2, 'Sub1', 65000, 1),\n"
                                      "                        (3, 'Sub2', 75000, 1),\n"
                                      "                        (4, 'Sub3', 85000, 1);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_019',
        'prompt': '### Managers Earning Less Than Subordinates\n'
                  '\n'
                  'Write a query to identify all managers who earn strictly less salary than at least one of their '
                  'direct subordinates.\n'
                  '\n'
                  '**Output columns:** `manager_id`, `manager_name`, `manager_salary`\n'
                  '\n'
                  'Return distinct managers ordered by `manager_id` ascending.',
        'reference_query': '\n'
                           '            SELECT DISTINCT m.id AS manager_id, m.name AS manager_name, m.salary AS '
                           'manager_salary\n'
                           '            FROM employees m\n'
                           '            JOIN employees e ON m.id = e.manager_id\n'
                           '            WHERE m.salary < e.salary\n'
                           '            ORDER BY manager_id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                salary REAL NOT NULL,\n'
                      '                manager_id INTEGER\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample sales data summing to 100 units',
                         'seed_data': '\n'
                                      '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                                      "                        (1, 'Phone', 50),\n"
                                      "                        (2, 'Laptop', 30),\n"
                                      "                        (3, 'Tablet', 20);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Arbitrary total units with decimal precision rounding',
                         'seed_data': '\n'
                                      '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                                      "                        (1, 'Alpha', 33),\n"
                                      "                        (2, 'Beta', 33),\n"
                                      "                        (3, 'Gamma', 34);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single product in table',
                         'seed_data': '\n'
                                      '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                                      "                        (1, 'OnlyOne', 42);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_020',
        'prompt': '### Cumulative Percentage of Product Sales\n'
                  '\n'
                  "Write a query to calculate each product's units sold and the cumulative percentage of overall "
                  'company sales (rounded to 2 decimal places, e.g. 50.00 for 50%).\n'
                  '\n'
                  '**Output columns:** `product_name`, `units_sold`, `cumulative_pct`\n'
                  '\n'
                  'Order by `units_sold` descending, then `product_name` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                product_name,\n'
                           '                units_sold,\n'
                           '                ROUND(\n'
                           '                    100.0 * SUM(units_sold) OVER (\n'
                           '                        ORDER BY units_sold DESC, product_name ASC\n'
                           '                    ) / SUM(units_sold) OVER (),\n'
                           '                    2\n'
                           '                ) AS cumulative_pct\n'
                           '            FROM sales\n'
                           '            ORDER BY units_sold DESC, product_name ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE sales (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                product_name TEXT NOT NULL,\n'
                      '                units_sold INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample activity with multiple streaks per user',
                         'seed_data': '\n'
                                      '                    INSERT INTO user_activity (user_id, activity_date) VALUES\n'
                                      "                        (1, '2026-01-01'),\n"
                                      "                        (1, '2026-01-02'),\n"
                                      "                        (1, '2026-01-03'),\n"
                                      "                        (1, '2026-01-05'),\n"
                                      "                        (1, '2026-01-06'),\n"
                                      "                        (2, '2026-01-01'),\n"
                                      "                        (2, '2026-01-03');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Duplicate activity dates per user and longer streaks',
                         'seed_data': '\n'
                                      '                    INSERT INTO user_activity (user_id, activity_date) VALUES\n'
                                      "                        (10, '2026-02-10'),\n"
                                      "                        (10, '2026-02-10'),\n"
                                      "                        (10, '2026-02-11'),\n"
                                      "                        (10, '2026-02-12'),\n"
                                      "                        (10, '2026-02-13'),\n"
                                      "                        (20, '2026-02-10'),\n"
                                      "                        (20, '2026-02-11');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single day activity for all users (all streak 1)',
                         'seed_data': '\n'
                                      '                    INSERT INTO user_activity (user_id, activity_date) VALUES\n'
                                      "                        (100, '2026-03-01'),\n"
                                      "                        (200, '2026-03-05');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_021',
        'prompt': '### Longest Consecutive Active Day Streak\n'
                  '\n'
                  'Write a query using islands-and-gaps technique to calculate the length of the longest consecutive '
                  'active days streak for each user.\n'
                  '\n'
                  '**Output columns:** `user_id`, `max_streak_days`\n'
                  '\n'
                  'Order by `max_streak_days` descending, then `user_id` ascending.',
        'reference_query': '\n'
                           '            WITH distinct_dates AS (\n'
                           '                SELECT DISTINCT user_id, activity_date\n'
                           '                FROM user_activity\n'
                           '            ),\n'
                           '            numbered AS (\n'
                           '                SELECT\n'
                           '                    user_id,\n'
                           '                    activity_date,\n'
                           '                    julianday(activity_date) - ROW_NUMBER() OVER (\n'
                           '                        PARTITION BY user_id\n'
                           '                        ORDER BY activity_date ASC\n'
                           '                    ) AS grp\n'
                           '                FROM distinct_dates\n'
                           '            ),\n'
                           '            streaks AS (\n'
                           '                SELECT user_id, grp, COUNT(*) AS streak_len\n'
                           '                FROM numbered\n'
                           '                GROUP BY user_id, grp\n'
                           '            )\n'
                           '            SELECT user_id, MAX(streak_len) AS max_streak_days\n'
                           '            FROM streaks\n'
                           '            GROUP BY user_id\n'
                           '            ORDER BY max_streak_days DESC, user_id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE user_activity (\n'
                      '                user_id INTEGER NOT NULL,\n'
                      '                activity_date TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample 3-tier company org hierarchy',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                                      "                        (1, 'CEO Alice', NULL),\n"
                                      "                        (2, 'VP Bob', 1),\n"
                                      "                        (3, 'VP Charlie', 1),\n"
                                      "                        (4, 'Engineer Dave', 2);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Deep 5-level hierarchy chain',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                                      "                        (10, 'Level1', NULL),\n"
                                      "                        (20, 'Level2', 10),\n"
                                      "                        (30, 'Level3', 20),\n"
                                      "                        (40, 'Level4', 30),\n"
                                      "                        (50, 'Level5', 40);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple branches at each level',
                         'seed_data': '\n'
                                      '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                                      "                        (1, 'Boss', NULL),\n"
                                      "                        (2, 'M1', 1),\n"
                                      "                        (3, 'M2', 1),\n"
                                      "                        (4, 'W1', 2),\n"
                                      "                        (5, 'W2', 2),\n"
                                      "                        (6, 'W3', 3);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_022',
        'prompt': '### Recursive Organization Hierarchy Depth\n'
                  '\n'
                  'Write a recursive query using `WITH RECURSIVE` to determine the reporting level of each employee in '
                  'the company hierarchy. The top executive (whose `manager_id` is NULL) is at level 1, direct reports '
                  'to level 1 are at level 2, and so on.\n'
                  '\n'
                  '**Output columns:** `id`, `name`, `level`\n'
                  '\n'
                  'Order by `level` ascending, then `id` ascending.',
        'reference_query': '\n'
                           '            WITH RECURSIVE org_tree AS (\n'
                           '                SELECT id, name, manager_id, 1 AS level\n'
                           '                FROM employees\n'
                           '                WHERE manager_id IS NULL\n'
                           '                UNION ALL\n'
                           '                SELECT e.id, e.name, e.manager_id, ot.level + 1\n'
                           '                FROM employees e\n'
                           '                JOIN org_tree ot ON e.manager_id = ot.id\n'
                           '            )\n'
                           '            SELECT id, name, level\n'
                           '            FROM org_tree\n'
                           '            ORDER BY level ASC, id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                manager_id INTEGER\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample orders with both odd and even counts per region',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, region, amount) VALUES\n'
                                      "                        (1, 'North', 10.0),\n"
                                      "                        (2, 'North', 20.0),\n"
                                      "                        (3, 'North', 30.0),\n"
                                      "                        (4, 'South', 100.0),\n"
                                      "                        (5, 'South', 200.0),\n"
                                      "                        (6, 'South', 300.0),\n"
                                      "                        (7, 'South', 400.0);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Tied values in middle positions',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, region, amount) VALUES\n'
                                      "                        (1, 'East', 50.0),\n"
                                      "                        (2, 'East', 50.0),\n"
                                      "                        (3, 'East', 50.0),\n"
                                      "                        (4, 'East', 50.0),\n"
                                      "                        (5, 'West', 15.5),\n"
                                      "                        (6, 'West', 25.5);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single order per region',
                         'seed_data': '\n'
                                      '                    INSERT INTO orders (id, region, amount) VALUES\n'
                                      "                        (1, 'Central', 99.99);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_023',
        'prompt': '### Median Order Amount per Region\n'
                  '\n'
                  'Write a query to calculate the median order `amount` for each region (rounded to 2 decimal places). '
                  'If a region has an even count of orders, the median is the average of the two middle values.\n'
                  '\n'
                  '**Output columns:** `region`, `median_amount`\n'
                  '\n'
                  'Order by `region` ascending.',
        'reference_query': '\n'
                           '            WITH ranked AS (\n'
                           '                SELECT\n'
                           '                    region,\n'
                           '                    amount,\n'
                           '                    ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount ASC, id ASC) AS '
                           'rnk_asc,\n'
                           '                    ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, id DESC) '
                           'AS rnk_desc\n'
                           '                FROM orders\n'
                           '            )\n'
                           '            SELECT\n'
                           '                region,\n'
                           '                ROUND(AVG(amount), 2) AS median_amount\n'
                           '            FROM ranked\n'
                           '            WHERE ABS(CAST(rnk_asc AS INTEGER) - CAST(rnk_desc AS INTEGER)) <= 1\n'
                           '            GROUP BY region\n'
                           '            ORDER BY region ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE orders (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                region TEXT NOT NULL,\n'
                      '                amount REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample cohort signups and events across 2026-01 and 2026-02',
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, signup_month) VALUES\n'
                                      "                        (1, '2026-01'),\n"
                                      "                        (2, '2026-01'),\n"
                                      "                        (3, '2026-02');\n"
                                      '                    INSERT INTO user_events (id, user_id, event_month) VALUES\n'
                                      "                        (1, 1, '2026-01'),\n"
                                      "                        (2, 1, '2026-02'),\n"
                                      "                        (3, 1, '2026-03'),\n"
                                      "                        (4, 2, '2026-01'),\n"
                                      "                        (5, 3, '2026-02'),\n"
                                      "                        (6, 3, '2026-04');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Users with zero activity and year boundary crossing',
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, signup_month) VALUES\n'
                                      "                        (10, '2025-11'),\n"
                                      "                        (20, '2025-11'),\n"
                                      "                        (30, '2025-12');\n"
                                      '                    INSERT INTO user_events (id, user_id, event_month) VALUES\n'
                                      "                        (1, 10, '2025-11'),\n"
                                      "                        (2, 10, '2025-12'),\n"
                                      "                        (3, 10, '2026-01'),\n"
                                      "                        (4, 30, '2025-12');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Empty events table (all retention 0)',
                         'seed_data': '\n'
                                      '                    INSERT INTO users (id, signup_month) VALUES\n'
                                      "                        (1, '2026-05');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_024',
        'prompt': '### Monthly User Cohort Retention\n'
                  '\n'
                  'Write a query to perform cohort retention analysis. For each user `signup_month` (formatted '
                  '`YYYY-MM`), report the total cohort size (`cohort_size`), and the number of users who had at least '
                  'one activity event in Month 0 (`m0_active`), Month 1 (`m1_active`), and Month 2 (`m2_active`) '
                  'relative to their signup month.\n'
                  '\n'
                  '**Output columns:** `signup_month`, `cohort_size`, `m0_active`, `m1_active`, `m2_active`\n'
                  '\n'
                  'Order by `signup_month` ascending.',
        'reference_query': '\n'
                           '            WITH user_activity_offsets AS (\n'
                           '                SELECT\n'
                           '                    u.signup_month,\n'
                           '                    u.id AS user_id,\n'
                           '                    MAX(CASE WHEN e.event_month = u.signup_month THEN 1 ELSE 0 END) AS '
                           'in_m0,\n'
                           '                    MAX(CASE\n'
                           "                        WHEN strftime('%Y', e.event_month) * 12 + CAST(strftime('%m', "
                           'e.event_month) AS INTEGER) -\n'
                           "                             (strftime('%Y', u.signup_month) * 12 + CAST(strftime('%m', "
                           'u.signup_month) AS INTEGER)) = 1\n'
                           '                        THEN 1 ELSE 0 END) AS in_m1,\n'
                           '                    MAX(CASE\n'
                           "                        WHEN strftime('%Y', e.event_month) * 12 + CAST(strftime('%m', "
                           'e.event_month) AS INTEGER) -\n'
                           "                             (strftime('%Y', u.signup_month) * 12 + CAST(strftime('%m', "
                           'u.signup_month) AS INTEGER)) = 2\n'
                           '                        THEN 1 ELSE 0 END) AS in_m2\n'
                           '                FROM users u\n'
                           '                LEFT JOIN user_events e ON u.id = e.user_id\n'
                           '                GROUP BY u.signup_month, u.id\n'
                           '            )\n'
                           '            SELECT\n'
                           '                signup_month,\n'
                           '                COUNT(*) AS cohort_size,\n'
                           '                SUM(in_m0) AS m0_active,\n'
                           '                SUM(in_m1) AS m1_active,\n'
                           '                SUM(in_m2) AS m2_active\n'
                           '            FROM user_activity_offsets\n'
                           '            GROUP BY signup_month\n'
                           '            ORDER BY signup_month ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE users (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                signup_month TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE user_events (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                user_id INTEGER NOT NULL,\n'
                      '                event_month TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample overlapping and adjacent room reservations',
                         'seed_data': '\n'
                                      '                    INSERT INTO reservations (id, room_id, start_time, '
                                      'end_time) VALUES\n'
                                      "                        (1, 101, '2026-01-10 09:00', '2026-01-10 11:00'),\n"
                                      "                        (2, 101, '2026-01-10 10:30', '2026-01-10 12:00'),\n"
                                      "                        (3, 101, '2026-01-10 13:00', '2026-01-10 14:00'),\n"
                                      "                        (4, 102, '2026-01-10 09:00', '2026-01-10 10:00');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Touching boundary times (start == end is not an overlap)',
                         'seed_data': '\n'
                                      '                    INSERT INTO reservations (id, room_id, start_time, '
                                      'end_time) VALUES\n'
                                      "                        (1, 1, '2026-02-01 08:00', '2026-02-01 09:00'),\n"
                                      "                        (2, 1, '2026-02-01 09:00', '2026-02-01 10:00'),\n"
                                      "                        (3, 1, '2026-02-01 08:30', '2026-02-01 09:30');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple overlapping reservations across distinct rooms',
                         'seed_data': '\n'
                                      '                    INSERT INTO reservations (id, room_id, start_time, '
                                      'end_time) VALUES\n'
                                      "                        (10, 5, '2026-03-01 10:00', '2026-03-01 12:00'),\n"
                                      "                        (11, 5, '2026-03-01 11:00', '2026-03-01 13:00'),\n"
                                      "                        (12, 6, '2026-03-01 10:00', '2026-03-01 12:00'),\n"
                                      "                        (13, 6, '2026-03-01 10:30', '2026-03-01 11:30');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_025',
        'prompt': '### Overlapping Room Reservations\n'
                  '\n'
                  'Write a query to identify all pairs of conflicting/overlapping reservations for the same room. Two '
                  'reservations A and B for the same room conflict if `A.start_time < B.end_time` and `B.start_time < '
                  'A.end_time`. To eliminate duplicates and self-joins, report pairs where `A.id < B.id`.\n'
                  '\n'
                  '**Output columns:** `room_id`, `res1_id`, `res2_id`\n'
                  '\n'
                  'Order by `room_id` ascending, `res1_id` ascending, then `res2_id` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                r1.room_id,\n'
                           '                r1.id AS res1_id,\n'
                           '                r2.id AS res2_id\n'
                           '            FROM reservations r1\n'
                           '            JOIN reservations r2 ON r1.room_id = r2.room_id AND r1.id < r2.id\n'
                           '            WHERE r1.start_time < r2.end_time\n'
                           '              AND r2.start_time < r1.end_time\n'
                           '            ORDER BY r1.room_id ASC, res1_id ASC, res2_id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE reservations (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                room_id INTEGER NOT NULL,\n'
                      '                start_time TEXT NOT NULL,\n'
                      '                end_time TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample employees with salary ties in rank 1 and 2',
                         'seed_data': '\n'
                                      '                    INSERT INTO departments (id, name) VALUES (1, '
                                      "'Engineering'), (2, 'Marketing');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Alice', 1, 100000),\n"
                                      "                        (2, 'Bob', 1, 100000),\n"
                                      "                        (3, 'Charlie', 1, 90000),\n"
                                      "                        (4, 'David', 1, 80000),\n"
                                      "                        (5, 'Eve', 2, 70000),\n"
                                      "                        (6, 'Frank', 2, 65000);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Ties for second rank',
                         'seed_data': '\n'
                                      "                    INSERT INTO departments (id, name) VALUES (1, 'Finance');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      'VALUES\n'
                                      "                        (1, 'Gary', 1, 120000),\n"
                                      "                        (2, 'Helen', 1, 110000),\n"
                                      "                        (3, 'Ian', 1, 110000),\n"
                                      "                        (4, 'Jack', 1, 90000);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Departments with only 1 employee',
                         'seed_data': '\n'
                                      "                    INSERT INTO departments (id, name) VALUES (1, 'Legal');\n"
                                      '                    INSERT INTO employees (id, name, department_id, salary) '
                                      "VALUES (1, 'Solo', 1, 80000);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_026',
        'prompt': '### Top Two Salary Ranks per Department\n'
                  '\n'
                  'Write a query using `DENSE_RANK()` to find the employees in the top 2 highest salary tiers for each '
                  'department. Include all employees tied for rank 1 or rank 2.\n'
                  '\n'
                  '**Output columns:** `department_name`, `employee_name`, `salary`, `salary_rank`\n'
                  '\n'
                  'Order by `department_name` ascending, `salary_rank` ascending, `salary` descending, and '
                  '`employee_name` ascending.',
        'reference_query': '\n'
                           '            WITH ranked AS (\n'
                           '                SELECT\n'
                           '                    d.name AS department_name,\n'
                           '                    e.name AS employee_name,\n'
                           '                    e.salary,\n'
                           '                    DENSE_RANK() OVER (\n'
                           '                        PARTITION BY e.department_id\n'
                           '                        ORDER BY e.salary DESC\n'
                           '                    ) AS salary_rank\n'
                           '                FROM employees e\n'
                           '                JOIN departments d ON e.department_id = d.id\n'
                           '            )\n'
                           '            SELECT department_name, employee_name, salary, salary_rank\n'
                           '            FROM ranked\n'
                           '            WHERE salary_rank <= 2\n'
                           '            ORDER BY department_name ASC, salary_rank ASC, salary DESC, employee_name '
                           'ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE departments (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL\n'
                      '            );\n'
                      '            CREATE TABLE employees (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                name TEXT NOT NULL,\n'
                      '                department_id INTEGER NOT NULL,\n'
                      '                salary REAL NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample clicks with gaps below and above 30 minutes',
                         'seed_data': '\n'
                                      '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                                      "                        (1, 1, '2026-01-01 10:00:00'),\n"
                                      "                        (2, 1, '2026-01-01 10:15:00'),\n"
                                      "                        (3, 1, '2026-01-01 11:00:00'),\n"
                                      "                        (4, 2, '2026-01-01 12:00:00');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Boundary exactly at 1800 seconds and multi-click sessions',
                         'seed_data': '\n'
                                      '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                                      "                        (1, 10, '2026-02-01 08:00:00'),\n"
                                      "                        (2, 10, '2026-02-01 08:30:00'),\n"
                                      "                        (3, 10, '2026-02-01 09:00:01'),\n"
                                      "                        (4, 20, '2026-02-01 09:00:00'),\n"
                                      "                        (5, 20, '2026-02-01 09:05:00'),\n"
                                      "                        (6, 20, '2026-02-01 09:10:00');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Single click per user',
                         'seed_data': '\n'
                                      '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                                      "                        (1, 100, '2026-03-01 10:00:00'),\n"
                                      "                        (2, 200, '2026-03-01 11:00:00');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_027',
        'prompt': '### User Clickstream Sessionization\n'
                  '\n'
                  'Write a query to group user clicks into sessions. A new session begins if strictly more than 1800 '
                  "seconds (30 minutes) have elapsed since the user's previous click. For each user session, return "
                  'the user ID, session start time (`session_start`), and total count of clicks in that session '
                  '(`click_count`).\n'
                  '\n'
                  '**Output columns:** `user_id`, `session_start`, `click_count`\n'
                  '\n'
                  'Order by `user_id` ascending, then `session_start` ascending.',
        'reference_query': '\n'
                           '            WITH click_diffs AS (\n'
                           '                SELECT\n'
                           '                    user_id,\n'
                           '                    click_time,\n'
                           '                    CASE\n'
                           '                        WHEN (julianday(click_time) - julianday(\n'
                           '                            LAG(click_time) OVER (PARTITION BY user_id ORDER BY click_time '
                           'ASC, id ASC)\n'
                           '                        )) * 86400 > 1800\n'
                           '                        OR LAG(click_time) OVER (PARTITION BY user_id ORDER BY click_time '
                           'ASC, id ASC) IS NULL\n'
                           '                        THEN 1\n'
                           '                        ELSE 0\n'
                           '                    END AS is_new_session\n'
                           '                FROM clicks\n'
                           '            ),\n'
                           '            sessionized AS (\n'
                           '                SELECT\n'
                           '                    user_id,\n'
                           '                    click_time,\n'
                           '                    SUM(is_new_session) OVER (\n'
                           '                        PARTITION BY user_id\n'
                           '                        ORDER BY click_time ASC\n'
                           '                    ) AS session_id\n'
                           '                FROM click_diffs\n'
                           '            )\n'
                           '            SELECT\n'
                           '                user_id,\n'
                           '                MIN(click_time) AS session_start,\n'
                           '                COUNT(*) AS click_count\n'
                           '            FROM sessionized\n'
                           '            GROUP BY user_id, session_id\n'
                           '            ORDER BY user_id ASC, session_start ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE clicks (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                user_id INTEGER NOT NULL,\n'
                      '                click_time TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample orders with overlapping items',
                         'seed_data': '\n'
                                      '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                                      "                        (1, 'Bread'), (1, 'Butter'), (1, 'Milk'),\n"
                                      "                        (2, 'Bread'), (2, 'Butter'),\n"
                                      "                        (3, 'Bread'), (3, 'Jam');\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Multiple items with higher co-purchase counts and ties',
                         'seed_data': '\n'
                                      '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                                      "                        (10, 'Coffee'), (10, 'Sugar'), (10, 'Cream'),\n"
                                      "                        (20, 'Coffee'), (20, 'Sugar'), (20, 'Cream'),\n"
                                      "                        (30, 'Coffee'), (30, 'Sugar'),\n"
                                      "                        (40, 'Tea'),    (40, 'Honey');\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'No item pairs meeting threshold of 2',
                         'seed_data': '\n'
                                      '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                                      "                        (1, 'Pencil'), (1, 'Eraser'),\n"
                                      "                        (2, 'Pen'), (2, 'Paper');\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_028',
        'prompt': '### Market Basket Analysis: Co-Purchased Item Pairs\n'
                  '\n'
                  'Write a query to perform market basket analysis. Find all distinct pairs of items (`item_a`, '
                  '`item_b` where `item_a < item_b`) that were purchased together in the same order at least 2 times.\n'
                  '\n'
                  '**Output columns:** `item_a`, `item_b`, `co_purchase_count`\n'
                  '\n'
                  'Order by `co_purchase_count` descending, `item_a` ascending, and `item_b` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                i1.item_name AS item_a,\n'
                           '                i2.item_name AS item_b,\n'
                           '                COUNT(*) AS co_purchase_count\n'
                           '            FROM order_items i1\n'
                           '            JOIN order_items i2 ON i1.order_id = i2.order_id AND i1.item_name < '
                           'i2.item_name\n'
                           '            GROUP BY item_a, item_b\n'
                           '            HAVING COUNT(*) >= 2\n'
                           '            ORDER BY co_purchase_count DESC, item_a ASC, item_b ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE order_items (\n'
                      '                order_id INTEGER NOT NULL,\n'
                      '                item_name TEXT NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample stock changes with one item going below zero',
                         'seed_data': '\n'
                                      '                    INSERT INTO stock_events (id, item_id, event_date, '
                                      'change_qty) VALUES\n'
                                      "                        (1, 101, '2026-01-01', 10),\n"
                                      "                        (2, 101, '2026-01-05', -15),\n"
                                      "                        (3, 101, '2026-01-10', 20),\n"
                                      "                        (4, 102, '2026-01-01', 50),\n"
                                      "                        (5, 102, '2026-01-02', -10);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Items recovering from negative and dipping multiple times',
                         'seed_data': '\n'
                                      '                    INSERT INTO stock_events (id, item_id, event_date, '
                                      'change_qty) VALUES\n'
                                      "                        (1, 1, '2026-02-01', 5),\n"
                                      "                        (2, 1, '2026-02-02', -8),\n"
                                      "                        (3, 1, '2026-02-03', 10),\n"
                                      "                        (4, 1, '2026-02-04', -20),\n"
                                      "                        (5, 2, '2026-02-01', -1);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Stock reaching exactly 0 (not a stockout)',
                         'seed_data': '\n'
                                      '                    INSERT INTO stock_events (id, item_id, event_date, '
                                      'change_qty) VALUES\n'
                                      "                        (1, 50, '2026-03-01', 10),\n"
                                      "                        (2, 50, '2026-03-02', -10);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'hard',
        'id': 'sql_prob_029',
        'prompt': '### Inventory Stockout Date Simulation\n'
                  '\n'
                  'Write a query to calculate cumulative running inventory for each item based on inventory change '
                  'events. Identify the earliest event date on which each item experienced a stockout (cumulative '
                  'stock fell strictly below zero). For each such item, report the item ID, the stockout event date '
                  '(`stockout_date`), and the stock level at that moment (`stockout_level`).\n'
                  '\n'
                  '**Output columns:** `item_id`, `stockout_date`, `stockout_level`\n'
                  '\n'
                  'Order by `item_id` ascending.',
        'reference_query': '\n'
                           '            WITH running_stock AS (\n'
                           '                SELECT\n'
                           '                    item_id,\n'
                           '                    event_date,\n'
                           '                    SUM(change_qty) OVER (\n'
                           '                        PARTITION BY item_id\n'
                           '                        ORDER BY event_date ASC, id ASC\n'
                           '                    ) AS current_stock,\n'
                           '                    id\n'
                           '                FROM stock_events\n'
                           '            ),\n'
                           '            negative_events AS (\n'
                           '                SELECT\n'
                           '                    item_id,\n'
                           '                    event_date,\n'
                           '                    current_stock,\n'
                           '                    ROW_NUMBER() OVER (\n'
                           '                        PARTITION BY item_id\n'
                           '                        ORDER BY event_date ASC, id ASC\n'
                           '                    ) AS rnk\n'
                           '                FROM running_stock\n'
                           '                WHERE current_stock < 0\n'
                           '            )\n'
                           '            SELECT\n'
                           '                item_id,\n'
                           '                event_date AS stockout_date,\n'
                           '                current_stock AS stockout_level\n'
                           '            FROM negative_events\n'
                           '            WHERE rnk = 1\n'
                           '            ORDER BY item_id ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE stock_events (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                item_id INTEGER NOT NULL,\n'
                      '                event_date TEXT NOT NULL,\n'
                      '                change_qty INTEGER NOT NULL\n'
                      '            );\n'
                      '        '},
    {   'cases': [   {   'case_type': 'visible_sample',
                         'description': 'Sample sales data across all four quarters',
                         'seed_data': '\n'
                                      '                    INSERT INTO category_sales (id, category, sale_quarter, '
                                      'revenue) VALUES\n'
                                      "                        (1, 'Electronics', 'Q1', 100.0),\n"
                                      "                        (2, 'Electronics', 'Q2', 150.0),\n"
                                      "                        (3, 'Electronics', 'Q3', 200.0),\n"
                                      "                        (4, 'Electronics', 'Q4', 250.0),\n"
                                      "                        (5, 'Clothing', 'Q1', 50.0),\n"
                                      "                        (6, 'Clothing', 'Q2', 75.0);\n"
                                      '                ',
                         'sort_order': 0},
                     {   'case_type': 'hidden_case',
                         'description': 'Categories missing multiple quarters and decimals',
                         'seed_data': '\n'
                                      '                    INSERT INTO category_sales (id, category, sale_quarter, '
                                      'revenue) VALUES\n'
                                      "                        (1, 'Books', 'Q3', 45.50),\n"
                                      "                        (2, 'Books', 'Q4', 54.50),\n"
                                      "                        (3, 'Furniture', 'Q1', 300.25),\n"
                                      "                        (4, 'Furniture', 'Q4', 199.75);\n"
                                      '                ',
                         'sort_order': 1},
                     {   'case_type': 'hidden_case',
                         'description': 'Tied total revenue verifying category tie break',
                         'seed_data': '\n'
                                      '                    INSERT INTO category_sales (id, category, sale_quarter, '
                                      'revenue) VALUES\n'
                                      "                        (1, 'Zeta', 'Q1', 100.0),\n"
                                      "                        (2, 'Alpha', 'Q2', 100.0);\n"
                                      '                ',
                         'sort_order': 2}],
        'checks_json': {'forbidden_constructs': [], 'order_matters': True},
        'difficulty': 'medium',
        'id': 'sql_prob_030',
        'prompt': '### Quarterly Category Sales Pivot\n'
                  '\n'
                  'Write a query to pivot quarterly revenue by category into separate columns for `Q1`, `Q2`, `Q3`, '
                  'and `Q4`, along with the `total_revenue` across the year.\n'
                  '\n'
                  '**Output columns:** `category`, `q1_revenue`, `q2_revenue`, `q3_revenue`, `q4_revenue`, '
                  '`total_revenue`\n'
                  '\n'
                  'Order by `total_revenue` descending, then `category` ascending.',
        'reference_query': '\n'
                           '            SELECT\n'
                           '                category,\n'
                           "                ROUND(SUM(CASE WHEN sale_quarter = 'Q1' THEN revenue ELSE 0.0 END), 2) AS "
                           'q1_revenue,\n'
                           "                ROUND(SUM(CASE WHEN sale_quarter = 'Q2' THEN revenue ELSE 0.0 END), 2) AS "
                           'q2_revenue,\n'
                           "                ROUND(SUM(CASE WHEN sale_quarter = 'Q3' THEN revenue ELSE 0.0 END), 2) AS "
                           'q3_revenue,\n'
                           "                ROUND(SUM(CASE WHEN sale_quarter = 'Q4' THEN revenue ELSE 0.0 END), 2) AS "
                           'q4_revenue,\n'
                           '                ROUND(SUM(revenue), 2) AS total_revenue\n'
                           '            FROM category_sales\n'
                           '            GROUP BY category\n'
                           '            ORDER BY total_revenue DESC, category ASC;\n'
                           '        ',
        'schema_ddl': '\n'
                      '            CREATE TABLE category_sales (\n'
                      '                id INTEGER PRIMARY KEY,\n'
                      '                category TEXT NOT NULL,\n'
                      '                sale_quarter TEXT NOT NULL,\n'
                      '                revenue REAL NOT NULL\n'
                      '            );\n'
                      '        '}]

def seed_phase2_content_bank(session: Session) -> None:
    """Idempotently seed all 150 MCQs and 30 SQL problems into the database."""
    # 1. Ensure core skills exist across all 9 approved skills
    skill_names = {
        "DBMS",
        "System Design",
        "Machine Learning",
        "Computer Networks",
        "DSA",
        "Python",
        "OOP",
        "Operating Systems",
        "HR/Professional Judgment",
    }
    existing_skills = {s.canonical_name: s.id for s in session.scalars(select(SkillRow)).all()}
    for name in sorted(skill_names):
        if name not in existing_skills:
            s_row = SkillRow(canonical_name=name, sub_domain="general")
            session.add(s_row)
            session.flush()
            existing_skills[name] = s_row.id

    # 2. Seed 150 MCQs
    for fixture in PHASE2_MCQ_BANK:
        existing_q = session.get(MCQQuestionRow, fixture["id"])
        skill_id = existing_skills[fixture["skill"]]
        if not existing_q:
            q_row = MCQQuestionRow(
                id=fixture["id"],
                skill_id=skill_id,
                sub_domain=fixture["sub_domain"],
                difficulty=fixture["difficulty"],
                stem=fixture["stem"],
                options_json=fixture["options_json"],
                correct_option_ids=fixture["correct_option_ids"],
                explanation=fixture["explanation"],
                negative_marking=fixture["negative_marking"],
            )
            session.add(q_row)

    # 3. Seed 30 SQL problems and 90 cases
    for prob_fixture in PHASE2_SQL_BANK:
        existing_p = session.get(SQLProblemRow, prob_fixture["id"])
        if not existing_p:
            p_row = SQLProblemRow(
                id=prob_fixture["id"],
                difficulty=prob_fixture["difficulty"],
                prompt=prob_fixture["prompt"],
                schema_ddl=prob_fixture["schema_ddl"],
                reference_query=prob_fixture["reference_query"],
                checks_json=prob_fixture["checks_json"],
            )
            session.add(p_row)
            session.flush()

            for case in prob_fixture["cases"]:
                c_row = SQLProblemCaseRow(
                    problem_id=prob_fixture["id"],
                    case_type=case["case_type"],
                    seed_data=case["seed_data"],
                    description=case["description"],
                    sort_order=case["sort_order"],
                )
                session.add(c_row)

    session.commit()
