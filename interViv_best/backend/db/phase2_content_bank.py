"""Phase 2 verified MCQ and SQL content banks.

Contains:
- 150 verified MCQs across 5 core skills (30 each: DBMS, Python, OS, Computer Networks, DSA).
  Each skill contains 10 easy, 10 medium, 10 hard questions.
  No negative phrasing, defensible single correct answers.
- 30 verified SQL problems with clean DDL, seed data (1 visible sample + 2 hidden evaluation cases per problem),
  and verified reference queries.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import MCQQuestionRow, SQLProblemRow, SQLProblemCaseRow, SkillRow

PHASE2_MCQ_BANK: list[dict[str, Any]] = [{'id': 'mcq_dbms_001',
  'skill': 'DBMS',
  'sub_domain': 'indexing',
  'difficulty': 'easy',
  'stem': 'What is the primary operational advantage of a B+ tree index over a hash index in relational databases?',
  'options_json': [{'id': 'a', 'text': 'B+ trees execute exact-match lookups in strictly O(1) time complexity.'},
                   {'id': 'b',
                    'text': 'B+ trees efficiently support range queries and ordered scans because leaf nodes are '
                            'linked in sequential order.'},
                   {'id': 'c',
                    'text': 'B+ trees require zero storage overhead on disk compared to the underlying table heap.'},
                   {'id': 'd', 'text': 'B+ trees avoid hash collisions by eliminating disk read operations.'}],
  'correct_option_ids': ['b'],
  'explanation': 'B+ tree leaves form a doubly linked list, enabling efficient range scans and sorted traversals, '
                 'unlike hash indexes which only support equality lookups.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_002',
  'skill': 'DBMS',
  'sub_domain': 'keys',
  'difficulty': 'easy',
  'stem': 'Which database constraint guarantees that every tuple in a table possesses a distinct non-null identifier?',
  'options_json': [{'id': 'a', 'text': 'Primary Key constraint'},
                   {'id': 'b', 'text': 'Foreign Key constraint'},
                   {'id': 'c', 'text': 'Check constraint'},
                   {'id': 'd', 'text': 'Default constraint'}],
  'correct_option_ids': ['a'],
  'explanation': 'A primary key constraint uniquely identifies each record in a table and automatically enforces both '
                 'uniqueness and non-nullability.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_003',
  'skill': 'DBMS',
  'sub_domain': 'transactions',
  'difficulty': 'easy',
  'stem': 'Which ACID property guarantees that all operations within a transaction complete successfully or all their '
          'changes are rolled back?',
  'options_json': [{'id': 'a', 'text': 'Atomicity'},
                   {'id': 'b', 'text': 'Consistency'},
                   {'id': 'c', 'text': 'Isolation'},
                   {'id': 'd', 'text': 'Durability'}],
  'correct_option_ids': ['a'],
  'explanation': "Atomicity ensures an 'all-or-nothing' execution model where partial transactions leave no trace in "
                 'the database state.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_004',
  'skill': 'DBMS',
  'sub_domain': 'relationships',
  'difficulty': 'easy',
  'stem': 'Which integrity mechanism enforces relational consistency between a child table column and a parent table '
          'primary key?',
  'options_json': [{'id': 'a', 'text': 'Referential integrity via Foreign Key'},
                   {'id': 'b', 'text': 'Domain integrity via Check constraint'},
                   {'id': 'c', 'text': 'Entity integrity via Primary Key'},
                   {'id': 'd', 'text': 'User-defined integrity via Triggers only'}],
  'correct_option_ids': ['a'],
  'explanation': 'Referential integrity uses foreign keys to ensure that relationships between tables remain '
                 'consistent and prevent orphaned records.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_005',
  'skill': 'DBMS',
  'sub_domain': 'normalization',
  'difficulty': 'easy',
  'stem': 'What requirement characterizes First Normal Form (1NF) in relational schema design?',
  'options_json': [{'id': 'a',
                    'text': 'All attributes must contain atomic, indivisible values with no repeating groups.'},
                   {'id': 'b',
                    'text': 'All non-key attributes must be fully functionally dependent on the entire primary key.'},
                   {'id': 'c', 'text': 'Transitive dependencies between non-prime attributes must be eliminated.'},
                   {'id': 'd', 'text': 'Every functional dependency determinant must be a candidate key.'}],
  'correct_option_ids': ['a'],
  'explanation': '1NF requires that each column contain only atomic values and that the relation contains no repeating '
                 'groups or multivalued attributes.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_006',
  'skill': 'DBMS',
  'sub_domain': 'querying',
  'difficulty': 'easy',
  'stem': 'Which SQL JOIN returns exclusively the rows where matching values exist in both participating tables?',
  'options_json': [{'id': 'a', 'text': 'INNER JOIN'},
                   {'id': 'b', 'text': 'LEFT OUTER JOIN'},
                   {'id': 'c', 'text': 'FULL OUTER JOIN'},
                   {'id': 'd', 'text': 'CROSS JOIN'}],
  'correct_option_ids': ['a'],
  'explanation': 'INNER JOIN selects records that have matching values in both tables, filtering out non-matching rows '
                 'from both sides.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_007',
  'skill': 'DBMS',
  'sub_domain': 'indexing',
  'difficulty': 'easy',
  'stem': 'What distinguishes a clustered index from a non-clustered index in a relational storage engine?',
  'options_json': [{'id': 'a', 'text': 'A clustered index dictates the physical sorting order of table rows on disk.'},
                   {'id': 'b', 'text': 'A table can possess up to 16 clustered indexes simultaneously.'},
                   {'id': 'c', 'text': 'A clustered index stores pointers to rows rather than table data itself.'},
                   {'id': 'd', 'text': 'A clustered index is stored exclusively in RAM cache memory.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A clustered index organizes the physical storage order of the data pages on disk, meaning each table '
                 'can have at most one clustered index.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_008',
  'skill': 'DBMS',
  'sub_domain': 'sql',
  'difficulty': 'easy',
  'stem': 'Which SQL statement category includes commands such as CREATE, ALTER, and DROP?',
  'options_json': [{'id': 'a', 'text': 'Data Definition Language (DDL)'},
                   {'id': 'b', 'text': 'Data Manipulation Language (DML)'},
                   {'id': 'c', 'text': 'Data Control Language (DCL)'},
                   {'id': 'd', 'text': 'Transaction Control Language (TCL)'}],
  'correct_option_ids': ['a'],
  'explanation': 'DDL commands define and modify the schema structure of database objects, including tables, indexes, '
                 'and constraints.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_009',
  'skill': 'DBMS',
  'sub_domain': 'views',
  'difficulty': 'easy',
  'stem': 'What is the primary nature of a standard SQL VIEW in a relational database management system?',
  'options_json': [{'id': 'a',
                    'text': 'A virtual table defined by a stored SELECT query without persisting duplicated row data.'},
                   {'id': 'b', 'text': 'A physically materialized snapshot duplicated across cluster worker nodes.'},
                   {'id': 'c',
                    'text': 'A temporary table created in tempdb that drops automatically upon session disconnect.'},
                   {'id': 'd', 'text': 'An append-only transaction log stream.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A standard view is a virtual relation whose contents are dynamically computed by executing its '
                 'underlying query upon invocation.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_010',
  'skill': 'DBMS',
  'sub_domain': 'recovery',
  'difficulty': 'easy',
  'stem': 'Which mechanism ensures the Durability property of committed transactions during sudden server power loss?',
  'options_json': [{'id': 'a',
                    'text': 'Write-Ahead Logging (WAL) flushed to stable storage before transaction commit '
                            'confirmation.'},
                   {'id': 'b', 'text': 'Periodic volatile memory dumps to operating system swap space.'},
                   {'id': 'c', 'text': 'Read-committed transaction isolation locks held in RAM.'},
                   {'id': 'd', 'text': 'Dynamic query recompilation at database startup.'}],
  'correct_option_ids': ['a'],
  'explanation': 'WAL guarantees durability by appending all state modifications to durable non-volatile storage prior '
                 'to marking the transaction committed.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_011',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'medium',
  'stem': 'Under the ANSI SQL Read Committed isolation level, what concurrency phenomenon remains possible during '
          'concurrent transaction execution?',
  'options_json': [{'id': 'a',
                    'text': 'Non-repeatable read: re-reading the same row returns modified values committed by another '
                            'transaction.'},
                   {'id': 'b', 'text': 'Dirty read: reading uncommitted data written by a concurrent transaction.'},
                   {'id': 'c',
                    'text': "Dirty write: concurrent uncommitted transactions overwriting each other's uncommitted "
                            'rows.'},
                   {'id': 'd', 'text': 'Cascading aborts caused by uncommitted dependency chains.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Read Committed prevents dirty reads by only reading committed rows, but permits non-repeatable reads '
                 'because rows read earlier can change upon subsequent reads.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_012',
  'skill': 'DBMS',
  'sub_domain': 'normalization',
  'difficulty': 'medium',
  'stem': 'What condition must a relation satisfy to achieve Third Normal Form (3NF)?',
  'options_json': [{'id': 'a',
                    'text': 'It is in 2NF and every non-prime attribute is non-transitively dependent on every '
                            'candidate key.'},
                   {'id': 'b',
                    'text': 'It is in 1NF and all non-key columns depend on part of a composite primary key.'},
                   {'id': 'c', 'text': 'Every multi-valued dependency is a functional dependency.'},
                   {'id': 'd', 'text': 'No candidate key contains more than a single column attribute.'}],
  'correct_option_ids': ['a'],
  'explanation': '3NF requires a relation to be in 2NF and contain no transitive functional dependencies of non-prime '
                 'attributes on candidate keys.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_013',
  'skill': 'DBMS',
  'sub_domain': 'normalization',
  'difficulty': 'medium',
  'stem': 'What specific criterion defines Boyce-Codd Normal Form (BCNF) relative to standard 3NF?',
  'options_json': [{'id': 'a', 'text': 'For every non-trivial functional dependency X -> Y, X must be a superkey.'},
                   {'id': 'b', 'text': 'For every functional dependency X -> Y, Y must belong to a prime attribute.'},
                   {'id': 'c',
                    'text': 'Every join operation must be lossless without preserving functional dependencies.'},
                   {'id': 'd', 'text': 'Composite candidate keys are strictly forbidden.'}],
  'correct_option_ids': ['a'],
  'explanation': 'BCNF eliminates anomalies where a determinant in a functional dependency is not a candidate '
                 'key/superkey.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_014',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'medium',
  'stem': 'What rule governs the shrinking phase of the Two-Phase Locking (2PL) protocol?',
  'options_json': [{'id': 'a',
                    'text': 'A transaction may release locks, but cannot acquire any new locks once lock release '
                            'begins.'},
                   {'id': 'b', 'text': 'A transaction must convert all shared locks into exclusive locks.'},
                   {'id': 'c', 'text': 'A transaction must release all locks simultaneously at the moment of commit.'},
                   {'id': 'd',
                    'text': 'A transaction acquires additional locks only after verifying that deadlocks cannot '
                            'occur.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In 2PL, the shrinking phase permits releasing locks but strictly forbids acquiring new locks, '
                 'guaranteeing conflict serializability.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_015',
  'skill': 'DBMS',
  'sub_domain': 'query_optimization',
  'difficulty': 'medium',
  'stem': 'What constitutes a covering index for an executing SELECT query?',
  'options_json': [{'id': 'a',
                    'text': 'An index containing all columns referenced in the SELECT, WHERE, and JOIN clauses, '
                            'eliminating table heap lookups.'},
                   {'id': 'b', 'text': 'An index that indexes every column present in the underlying physical table.'},
                   {'id': 'c', 'text': 'A primary key index that covers all foreign key constraints.'},
                   {'id': 'd', 'text': 'A hash index mapped over all numeric columns in a table.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A covering index contains all attributes necessary to fulfill the query, allowing the engine to '
                 'satisfy the request directly from index pages.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_016',
  'skill': 'DBMS',
  'sub_domain': 'query_optimization',
  'difficulty': 'medium',
  'stem': 'When evaluating equi-joins over two large unsorted tables without existing indexes, which join algorithm '
          'typically minimizes random disk I/O?',
  'options_json': [{'id': 'a', 'text': 'Hash Join'},
                   {'id': 'b', 'text': 'Nested Loop Join'},
                   {'id': 'c', 'text': 'Cartesian Product Scan'},
                   {'id': 'd', 'text': 'Index Scan Join'}],
  'correct_option_ids': ['a'],
  'explanation': 'Hash join builds an in-memory hash table on the smaller build relation and probes it via a '
                 'sequential scan of the probe relation, avoiding random I/O.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_017',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'medium',
  'stem': 'Which anomaly can emerge under Snapshot Isolation that cannot occur under true Serializable isolation?',
  'options_json': [{'id': 'a',
                    'text': 'Write Skew: concurrent transactions read overlapping data sets and concurrently make '
                            'disjoint updates violating integrity constraints.'},
                   {'id': 'b', 'text': 'Dirty Read: transactions observing uncommitted row states.'},
                   {'id': 'c', 'text': 'Lost Update on the exact same row when first-committer-wins is enabled.'},
                   {'id': 'd', 'text': 'Cascading rollbacks across multiple committed sessions.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Snapshot Isolation prevents dirty reads and lost updates on identical rows, but permits write skew '
                 'because transactions update distinct rows based on overlapping read snapshots.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_018',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'medium',
  'stem': 'How does a database engine detect deadlocks among concurrent transactions using a Wait-For Graph?',
  'options_json': [{'id': 'a',
                    'text': 'By detecting directed cycles within the graph where vertices represent transactions and '
                            'edges represent lock dependencies.'},
                   {'id': 'b',
                    'text': 'By checking if the total count of active transactions exceeds the configured lock pool '
                            'capacity.'},
                   {'id': 'c',
                    'text': 'By verifying whether shared locks outnumber exclusive locks across database tables.'},
                   {'id': 'd', 'text': 'By monitoring operating system thread preemption queues.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A deadlock in a Wait-For Graph corresponds directly to a directed cycle, where each transaction in '
                 'the cycle is waiting for a resource held by another.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_019',
  'skill': 'DBMS',
  'sub_domain': 'indexing',
  'difficulty': 'medium',
  'stem': 'Given a composite B-tree index on columns (A, B, C), which WHERE clause predicate leverages the index '
          'structure via range scan?',
  'options_json': [{'id': 'a', 'text': 'WHERE A = 10 AND B > 20'},
                   {'id': 'b', 'text': 'WHERE B = 20 AND C = 30'},
                   {'id': 'c', 'text': 'WHERE C = 30'},
                   {'id': 'd', 'text': 'WHERE B > 20'}],
  'correct_option_ids': ['a'],
  'explanation': 'Composite indexes observe the leftmost prefix rule; filtering on leading column A allows the engine '
                 'to seek and range scan on B.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_020',
  'skill': 'DBMS',
  'sub_domain': 'storage',
  'difficulty': 'medium',
  'stem': 'What is the purpose of the checkpoint operation in write-ahead logging database engines?',
  'options_json': [{'id': 'a',
                    'text': 'To flush dirty buffer pool pages to disk, bounding the volume of log records to replay '
                            'during crash recovery.'},
                   {'id': 'b', 'text': 'To drop all inactive user sessions and reset transaction IDs to zero.'},
                   {'id': 'c', 'text': 'To convert row-oriented table heaps into columnar formats.'},
                   {'id': 'd', 'text': 'To recalculate table cardinality statistics for the query planner.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Checkpoints synchronize dirty in-memory pages with disk storage, establishing a safe horizon before '
                 'which log records need no recovery replay.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_021',
  'skill': 'DBMS',
  'sub_domain': 'recovery',
  'difficulty': 'hard',
  'stem': 'What are the three sequential execution phases of the ARIES crash recovery algorithm?',
  'options_json': [{'id': 'a', 'text': 'Analysis, Redo, and Undo'},
                   {'id': 'b', 'text': 'Scan, Filter, and Aggregate'},
                   {'id': 'c', 'text': 'Validate, Write, and Purge'},
                   {'id': 'd', 'text': 'Snapshot, Replay, and Flush'}],
  'correct_option_ids': ['a'],
  'explanation': 'ARIES operates in three distinct phases: Analysis determines dirty pages and active transactions, '
                 'Redo repeats history, and Undo rolls back active transactions.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_022',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'hard',
  'stem': 'What property makes Strict Two-Phase Locking (Strict 2PL) widely preferred over basic 2PL in commercial '
          'database engines?',
  'options_json': [{'id': 'a',
                    'text': 'It holds exclusive locks until transaction commit or abort, preventing cascading aborts.'},
                   {'id': 'b',
                    'text': 'It completely eliminates all deadlocks without requiring timeouts or cycle detection.'},
                   {'id': 'c', 'text': 'It allows transactions to read uncommitted rows safely without locking.'},
                   {'id': 'd', 'text': 'It eliminates the need for write-ahead logging on storage devices.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Strict 2PL retains all exclusive locks until transaction completion, ensuring dirty values are never '
                 'exposed to concurrent transactions and preventing cascading rollbacks.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_023',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'hard',
  'stem': 'Which mechanism enables standard relational engines to prevent Phantom Reads under the Serializable '
          'isolation level?',
  'options_json': [{'id': 'a',
                    'text': 'Predicate locks or next-key index locks that protect the gap between existing index '
                            'keys.'},
                   {'id': 'b', 'text': 'Optimistic row-level checksums verified upon disk read.'},
                   {'id': 'c', 'text': 'Exclusive table locks acquired during all SELECT statements.'},
                   {'id': 'd', 'text': 'Forcing all transaction execution through a single worker thread.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Phantom reads involve newly inserted tuples matching a search predicate; next-key and predicate '
                 'locking lock both existing keys and gap intervals.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_024',
  'skill': 'DBMS',
  'sub_domain': 'storage',
  'difficulty': 'hard',
  'stem': 'In Log-Structured Merge (LSM) tree architectures, what trade-off distinguishes Leveled Compaction from '
          'Size-Tiered Compaction?',
  'options_json': [{'id': 'a',
                    'text': 'Leveled Compaction provides lower read amplification and lower space amplification at the '
                            'expense of higher write amplification.'},
                   {'id': 'b',
                    'text': 'Leveled Compaction executes writes in memory without persisting write-ahead logs.'},
                   {'id': 'c',
                    'text': 'Size-Tiered Compaction guarantees strictly O(1) point lookups across all levels.'},
                   {'id': 'd',
                    'text': 'Size-Tiered Compaction uses zero auxiliary disk space during compaction runs.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Leveled compaction enforces strictly non-overlapping keys per level, which dramatically reduces '
                 'point lookup cost and wasted space, but requires rewrites increasing write amplification.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_025',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'hard',
  'stem': 'In Multi-Version Concurrency Control (MVCC) engines like PostgreSQL, what process reclaims physical table '
          'space occupied by obsolete row versions (dead tuples)?',
  'options_json': [{'id': 'a', 'text': 'VACUUM processing'},
                   {'id': 'b', 'text': 'Write-Ahead Log checkpointing'},
                   {'id': 'c', 'text': 'Buffer pool page eviction'},
                   {'id': 'd', 'text': 'Transaction rollback journal truncation'}],
  'correct_option_ids': ['a'],
  'explanation': 'PostgreSQL uses VACUUM (and autovacuum) to scan tables, remove dead row versions whose transaction '
                 'horizons have passed, and mark space reusable.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_026',
  'skill': 'DBMS',
  'sub_domain': 'algorithms',
  'difficulty': 'hard',
  'stem': 'In external merge sort with B buffer pages available, how many sorted runs can be merged together in a '
          'single pass during the merge phase?',
  'options_json': [{'id': 'a', 'text': 'B - 1 runs'},
                   {'id': 'b', 'text': 'B runs'},
                   {'id': 'c', 'text': 'B / 2 runs'},
                   {'id': 'd', 'text': '2 runs'}],
  'correct_option_ids': ['a'],
  'explanation': 'External merge sort reserves 1 buffer page for the output block and uses the remaining B - 1 buffer '
                 'pages as input buffers for B - 1 runs.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_027',
  'skill': 'DBMS',
  'sub_domain': 'distributed',
  'difficulty': 'hard',
  'stem': 'What fundamental limitation affects the Two-Phase Commit (2PC) protocol when the coordinator crashes after '
          'participants vote to commit?',
  'options_json': [{'id': 'a',
                    'text': 'Participants can become blocked indefinitely waiting to learn the final commit or abort '
                            'decision.'},
                   {'id': 'b', 'text': 'Transactions automatically commit without verifying participant votes.'},
                   {'id': 'c', 'text': 'Data on participant nodes is permanently corrupted and unrecoverable.'},
                   {'id': 'd', 'text': 'Network partitions are converted into Byzantine consensus failures.'}],
  'correct_option_ids': ['a'],
  'explanation': '2PC is a blocking protocol; if the coordinator fails while participants are in the prepared state, '
                 'participants must hold resources until coordinator recovery.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_028',
  'skill': 'DBMS',
  'sub_domain': 'distributed',
  'difficulty': 'hard',
  'stem': 'In the Raft consensus protocol, what ensures that a newly elected leader contains all committed log entries '
          'from prior terms?',
  'options_json': [{'id': 'a',
                    'text': "Candidate election votes require that the candidate's log is at least as up-to-date as "
                            "the voting majority's log."},
                   {'id': 'b',
                    'text': 'Followers forward missing log entries to the leader immediately upon election.'},
                   {'id': 'c', 'text': 'The leader reads all follower logs and takes the union of all entries.'},
                   {'id': 'd', 'text': 'A dedicated observer node commits missing entries on behalf of the cluster.'}],
  'correct_option_ids': ['a'],
  'explanation': "Raft's Election Restriction ensures that a candidate can only win an election if its log contains "
                 'all committed entries of a majority of nodes.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_029',
  'skill': 'DBMS',
  'sub_domain': 'buffer_pool',
  'difficulty': 'hard',
  'stem': 'How does the 2Q buffer pool replacement algorithm avoid cache pollution caused by large one-time sequential '
          'table scans?',
  'options_json': [{'id': 'a',
                    'text': 'It places newly referenced pages in a FIFO queue and promotes pages to an LRU queue only '
                            'upon a second access.'},
                   {'id': 'b', 'text': 'It completely bypasses disk cache for all SELECT queries.'},
                   {'id': 'c', 'text': 'It purges dirty pages immediately without writing them to log files.'},
                   {'id': 'd', 'text': 'It limits sequential scans to a fixed single page in memory.'}],
  'correct_option_ids': ['a'],
  'explanation': '2Q maintains two page queues: initial accesses enter a FIFO queue, filtering out single-scan pages, '
                 'while pages accessed repeatedly earn promotion to an LRU queue.',
  'negative_marking': 0.25},
 {'id': 'mcq_dbms_030',
  'skill': 'DBMS',
  'sub_domain': 'concurrency',
  'difficulty': 'hard',
  'stem': 'What validation check does backward-oriented Optimistic Concurrency Control (BOCC) perform during a '
          "transaction's validation phase?",
  'options_json': [{'id': 'a',
                    'text': "It verifies that the validating transaction's read set is disjoint from the write sets of "
                            'concurrent transactions that committed earlier.'},
                   {'id': 'b',
                    'text': 'It ensures that the transaction acquired locks on all accessed rows prior to reading '
                            'them.'},
                   {'id': 'c',
                    'text': 'It validates that the transaction wrote all changes directly to table heaps during '
                            'execution.'},
                   {'id': 'd',
                    'text': 'It checks that no active transactions have pending lock requests in the lock table.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In BOCC, a transaction validates by checking whether its read set intersects the write sets of '
                 'transactions that committed between its start and validation times.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_001',
  'skill': 'Python',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'What distinguishes a Python tuple from a Python list regarding item modification?',
  'options_json': [{'id': 'a',
                    'text': 'Tuples are immutable sequences, whereas lists are mutable and support in-place item '
                            'assignment.'},
                   {'id': 'b', 'text': 'Tuples store only primitive numbers, whereas lists store arbitrary objects.'},
                   {'id': 'c', 'text': 'Tuples are always ordered by value, whereas lists maintain insertion order.'},
                   {'id': 'd', 'text': 'Tuples cannot be iterated using a standard for-in loop.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Tuples cannot have elements added, removed, or changed after construction, whereas lists support '
                 'mutations like append, pop, and index reassignment.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_002',
  'skill': 'Python',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'What requirement must an object satisfy to serve as a valid key in a standard Python dictionary?',
  'options_json': [{'id': 'a', 'text': 'The object must be hashable, implementing __hash__() and __eq__().'},
                   {'id': 'b', 'text': 'The object must inherit directly from the built-in string class.'},
                   {'id': 'c', 'text': 'The object must be an integer or floating-point numeric value.'},
                   {'id': 'd', 'text': 'The object must maintain a strictly positive memory address.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Dictionary keys must be hashable objects whose hash value remains constant during their lifetime, '
                 'allowing equality comparisons with other objects.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_003',
  'skill': 'Python',
  'sub_domain': 'performance',
  'difficulty': 'easy',
  'stem': 'What is the time complexity of the built-in len() function when querying a standard Python list?',
  'options_json': [{'id': 'a',
                    'text': "O(1) constant time, because the element count is stored in the object's C struct header."},
                   {'id': 'b',
                    'text': 'O(n) linear time, because it iterates through the internal array to count items.'},
                   {'id': 'c',
                    'text': 'O(log n) logarithmic time, because it performs a binary search for the tail pointer.'},
                   {'id': 'd', 'text': 'O(n^2) quadratic time, because it validates pointer references.'}],
  'correct_option_ids': ['a'],
  'explanation': "CPython's PyVarObject header contains an ob_size field, allowing len() to return the item count "
                 'instantly in O(1) time without traversal.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_004',
  'skill': 'Python',
  'sub_domain': 'operators',
  'difficulty': 'easy',
  'stem': "What distinguishes the 'is' operator from the '==' operator in Python?",
  'options_json': [{'id': 'a', 'text': "'is' tests for object memory identity, whereas '==' tests for value equality."},
                   {'id': 'b', 'text': "'is' tests for numeric magnitude, whereas '==' tests for type equivalence."},
                   {'id': 'c',
                    'text': "'is' performs deep recursive comparison, whereas '==' performs shallow comparison."},
                   {'id': 'd', 'text': "'is' is reserved strictly for comparing None values."}],
  'correct_option_ids': ['a'],
  'explanation': "'is' checks whether two references point to the exact same object in memory (id(a) == id(b)), "
                 "whereas '==' invokes __eq__() to check value equivalence.",
  'negative_marking': 0.25},
 {'id': 'mcq_python_005',
  'skill': 'Python',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'What is the behavior of list.extend(iterable) compared to list.append(item)?',
  'options_json': [{'id': 'a',
                    'text': 'extend() iterates over the argument appending each element individually, whereas append() '
                            'adds the argument as a single element.'},
                   {'id': 'b',
                    'text': 'extend() returns a brand new list, whereas append() modifies the list in place.'},
                   {'id': 'c',
                    'text': 'extend() sorts the list after insertion, whereas append() preserves insertion order.'},
                   {'id': 'd',
                    'text': 'extend() accepts only string arguments, whereas append() accepts arbitrary objects.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Calling append([1, 2]) adds the list as a single child element, whereas extend([1, 2]) unpacks the '
                 'iterable and appends each element individually.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_006',
  'skill': 'Python',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': "What happens in memory when executing string concatenation using the '+' operator in Python?",
  'options_json': [{'id': 'a',
                    'text': 'A new string object is allocated in memory to store the joined characters because strings '
                            'are immutable.'},
                   {'id': 'b',
                    'text': "The left-hand string's buffer is expanded in place to accommodate the extra characters."},
                   {'id': 'c', 'text': 'A mutable pointer table is updated while retaining identical string IDs.'},
                   {'id': 'd', 'text': 'The characters are piped to the operating system temporary spool.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Because Python strings are immutable, concatenation constructs a new string object containing the '
                 'combined sequence of characters.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_007',
  'skill': 'Python',
  'sub_domain': 'builtins',
  'difficulty': 'easy',
  'stem': 'Why is range(1_000_000) memory-efficient in Python 3?',
  'options_json': [{'id': 'a',
                    'text': 'It returns an immutable sequence object that computes elements on demand using fixed '
                            'memory.'},
                   {'id': 'b', 'text': 'It stores all one million integers in a compressed C-level array.'},
                   {'id': 'c', 'text': 'It writes the sequence to a temporary disk swap file.'},
                   {'id': 'd', 'text': 'It uses operating system thread pools to generate numbers asynchronously.'}],
  'correct_option_ids': ['a'],
  'explanation': "Python 3's range object stores only start, stop, and step parameters, consuming minimal fixed memory "
                 'regardless of range span.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_008',
  'skill': 'Python',
  'sub_domain': 'functions',
  'difficulty': 'easy',
  'stem': 'What value is returned by a Python function that completes execution without reaching a return statement?',
  'options_json': [{'id': 'a', 'text': 'None'},
                   {'id': 'b', 'text': '0'},
                   {'id': 'c', 'text': 'False'},
                   {'id': 'd', 'text': "An empty string ''"}],
  'correct_option_ids': ['a'],
  'explanation': 'When execution reaches the end of a function body without encountering an explicit return statement, '
                 'Python automatically returns None.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_009',
  'skill': 'Python',
  'sub_domain': 'types',
  'difficulty': 'easy',
  'stem': 'What is the boolean evaluation of an empty collection such as [], {}, or set() in Python conditional '
          'statements?',
  'options_json': [{'id': 'a', 'text': 'Evaluates to False'},
                   {'id': 'b', 'text': 'Evaluates to True'},
                   {'id': 'c', 'text': 'Raises a TypeError exception'},
                   {'id': 'd', 'text': 'Evaluates to undefined'}],
  'correct_option_ids': ['a'],
  'explanation': 'In Python, empty sequences and collections have falsy truth values, evaluating to False in boolean '
                 'contexts.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_010',
  'skill': 'Python',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'Which built-in Python collection guarantees unique elements and average O(1) membership lookup?',
  'options_json': [{'id': 'a', 'text': 'set'},
                   {'id': 'b', 'text': 'list'},
                   {'id': 'c', 'text': 'tuple'},
                   {'id': 'd', 'text': 'deque'}],
  'correct_option_ids': ['a'],
  'explanation': 'The set data structure is implemented as a hash table, ensuring element uniqueness and average O(1) '
                 "membership checks with the 'in' operator.",
  'negative_marking': 0.25},
 {'id': 'mcq_python_011',
  'skill': 'Python',
  'sub_domain': 'functions',
  'difficulty': 'medium',
  'stem': "What happens when using a mutable object as a default parameter value, such as 'def append_to(item, "
          "target=[])'?",
  'options_json': [{'id': 'a',
                    'text': 'The default list is created once at function definition time and shared across subsequent '
                            'invocations that omit the parameter.'},
                   {'id': 'b',
                    'text': 'A fresh empty list is instantiated dynamically each time the function is called.'},
                   {'id': 'c', 'text': 'Python raises a SyntaxError at script compilation time.'},
                   {'id': 'd', 'text': 'The list is converted into an immutable tuple automatically.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Default argument expressions are evaluated once when the function definition is executed, binding '
                 'the same mutable object across calls.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_012',
  'skill': 'Python',
  'sub_domain': 'generators',
  'difficulty': 'medium',
  'stem': "How does the 'yield' keyword alter the execution behavior of a Python function?",
  'options_json': [{'id': 'a',
                    'text': 'It turns the function into a generator that suspends execution state and yields control '
                            'back to the caller until next() is invoked.'},
                   {'id': 'b',
                    'text': 'It terminates function execution and destroys the local stack frame permanently.'},
                   {'id': 'c',
                    'text': 'It schedules the function to run concurrently on a separate operating system thread.'},
                   {'id': 'd', 'text': 'It converts all local variables into global module variables.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Using yield transforms the function into a generator constructor; calling next() resumes execution '
                 'right after the yield statement.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_013',
  'skill': 'Python',
  'sub_domain': 'scoping',
  'difficulty': 'medium',
  'stem': "What is the scoping behavior of the iteration variable in a Python 3 list comprehension such as '[x for x "
          "in data]'?",
  'options_json': [{'id': 'a',
                    'text': "The variable 'x' is scoped locally to the comprehension's implicit function scope and "
                            'does not overwrite outer scope variables.'},
                   {'id': 'b',
                    'text': "The variable 'x' leaks into the surrounding local namespace, retaining its final loop "
                            'value.'},
                   {'id': 'c', 'text': "The variable 'x' is automatically elevated to module global scope."},
                   {'id': 'd', 'text': 'The comprehension creates a new sub-process with isolated memory.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In Python 3, list comprehensions have their own distinct local scope, ensuring loop variables do not '
                 'leak into the enclosing scope.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_014',
  'skill': 'Python',
  'sub_domain': 'oop',
  'difficulty': 'medium',
  'stem': 'What is the primary architectural purpose of the built-in @property decorator in Python classes?',
  'options_json': [{'id': 'a',
                    'text': 'To define getter methods that can be accessed like standard public attributes while '
                            'allowing encapsulation and validation logic.'},
                   {'id': 'b', 'text': 'To serialize class instances directly into JSON strings.'},
                   {'id': 'c', 'text': 'To make class methods execute as class-level static functions.'},
                   {'id': 'd', 'text': 'To enforce thread safety across concurrent method calls.'}],
  'correct_option_ids': ['a'],
  'explanation': '@property allows methods to be accessed via attribute syntax, enabling computed attributes, data '
                 'validation, and clean encapsulation.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_015',
  'skill': 'Python',
  'sub_domain': 'concurrency',
  'difficulty': 'medium',
  'stem': "What constraint does CPython's Global Interpreter Lock (GIL) place on standard multi-threaded Python "
          'programs?',
  'options_json': [{'id': 'a',
                    'text': 'Only one native thread can execute Python bytecode at any given moment within a single '
                            'CPython process.'},
                   {'id': 'b',
                    'text': 'Multiple threads cannot read shared variables simultaneously under any condition.'},
                   {'id': 'c',
                    'text': 'I/O bound socket operations block the entire process and prevent thread switching.'},
                   {'id': 'd', 'text': 'Threads are forbidden from spawning worker processes.'}],
  'correct_option_ids': ['a'],
  'explanation': 'The GIL is a mutex that protects access to Python objects, preventing multiple native threads from '
                 'executing Python bytecodes concurrently on multicore CPUs.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_016',
  'skill': 'Python',
  'sub_domain': 'functions',
  'difficulty': 'medium',
  'stem': "When defining a function signature 'def process(a, *args, **kwargs)', what data types are received by args "
          'and kwargs?',
  'options_json': [{'id': 'a',
                    'text': 'args is a tuple of extra positional arguments, and kwargs is a dictionary of extra '
                            'keyword arguments.'},
                   {'id': 'b',
                    'text': 'args is a list of positional arguments, and kwargs is a tuple of keyword arguments.'},
                   {'id': 'c', 'text': 'args is a dictionary, and kwargs is a set.'},
                   {'id': 'd', 'text': 'args and kwargs are both mutable lists.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In Python, *args packs excess positional arguments into an immutable tuple, and **kwargs packs '
                 'excess keyword arguments into a mutable dictionary.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_017',
  'skill': 'Python',
  'sub_domain': 'oop',
  'difficulty': 'medium',
  'stem': "Which special methods must a class implement to comply with Python's Context Manager protocol for the "
          "'with' statement?",
  'options_json': [{'id': 'a', 'text': '__enter__() and __exit__()'},
                   {'id': 'b', 'text': '__start__() and __stop__()'},
                   {'id': 'c', 'text': '__open__() and __close__()'},
                   {'id': 'd', 'text': '__begin__() and __commit__()'}],
  'correct_option_ids': ['a'],
  'explanation': 'The context manager protocol requires __enter__() for resource acquisition and setup, and __exit__() '
                 'for cleanup and exception handling.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_018',
  'skill': 'Python',
  'sub_domain': 'memory',
  'difficulty': 'medium',
  'stem': 'What distinguishes copy.deepcopy() from copy.copy() on an object containing nested mutable lists?',
  'options_json': [{'id': 'a',
                    'text': 'deepcopy() recursively copies all nested objects, whereas copy() constructs a shallow '
                            'container holding references to existing child objects.'},
                   {'id': 'b',
                    'text': 'deepcopy() converts all nested objects into strings, whereas copy() retains their data '
                            'types.'},
                   {'id': 'c', 'text': 'deepcopy() freezes nested lists into immutable tuples.'},
                   {'id': 'd', 'text': 'deepcopy() modifies the original object in place during duplication.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A shallow copy duplicates only the top-level container, referencing nested objects; a deep copy '
                 'duplicates nested structures recursively.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_019',
  'skill': 'Python',
  'sub_domain': 'oop',
  'difficulty': 'medium',
  'stem': 'Which algorithm does Python use to determine Method Resolution Order (MRO) in multiple inheritance '
          'hierarchies?',
  'options_json': [{'id': 'a', 'text': 'C3 Linearization algorithm'},
                   {'id': 'b', 'text': "Dijkstra's shortest path algorithm"},
                   {'id': 'c', 'text': 'Depth-first left-to-right tree traversal with duplicate retention'},
                   {'id': 'd', 'text': 'Breadth-first search with random tie-breaking'}],
  'correct_option_ids': ['a'],
  'explanation': 'Python employs C3 Linearization to compute a deterministic class precedence list that guarantees '
                 'monotonicity and preserves local precedence order.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_020',
  'skill': 'Python',
  'sub_domain': 'oop',
  'difficulty': 'medium',
  'stem': 'What behavior occurs when attempting to reassign an attribute on an instance of a dataclass defined with '
          '@dataclass(frozen=True)?',
  'options_json': [{'id': 'a', 'text': 'Python raises a FrozenInstanceError (subclass of AttributeError).'},
                   {'id': 'b', 'text': 'The reassignment succeeds silently without modifying memory.'},
                   {'id': 'c', 'text': 'The object is duplicated automatically with the updated attribute.'},
                   {'id': 'd', 'text': 'Python issues a runtime DeprecationWarning.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Setting frozen=True generates __setattr__ and __delattr__ methods that raise '
                 'dataclasses.FrozenInstanceError upon modification attempts.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_021',
  'skill': 'Python',
  'sub_domain': 'internals',
  'difficulty': 'hard',
  'stem': "What criteria distinguish a data descriptor from a non-data descriptor in Python's attribute lookup "
          'resolution?',
  'options_json': [{'id': 'a',
                    'text': 'A data descriptor defines __set__() or __delete__(), taking precedence over the '
                            "instance's __dict__ during attribute lookup."},
                   {'id': 'b',
                    'text': 'A data descriptor defines only __get__(), taking precedence over class-level attributes.'},
                   {'id': 'c',
                    'text': 'A data descriptor stores raw binary bytes, whereas non-data descriptors store text '
                            'strings.'},
                   {'id': 'd', 'text': 'A data descriptor can only be attached to built-in C extension types.'}],
  'correct_option_ids': ['a'],
  'explanation': "Descriptors defining __set__() or __delete__() are data descriptors. In Python's attribute lookup "
                 'order, data descriptors take precedence over the instance __dict__.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_022',
  'skill': 'Python',
  'sub_domain': 'metaprogramming',
  'difficulty': 'hard',
  'stem': "In a custom metaclass subclassing 'type', what is the specific role of the __new__ method compared to "
          '__init__?',
  'options_json': [{'id': 'a',
                    'text': '__new__() creates and returns the class object itself, whereas __init__() initializes the '
                            'already created class object.'},
                   {'id': 'b',
                    'text': '__new__() creates instances of the user class, whereas __init__() creates the metaclass.'},
                   {'id': 'c', 'text': '__new__() registers class attributes in the global module namespace.'},
                   {'id': 'd', 'text': '__new__() executes whenever an instance of the target class is instantiated.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In metaclasses, __new__() is responsible for allocating and returning the newly formed class object; '
                 '__init__() configures the class after creation.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_023',
  'skill': 'Python',
  'sub_domain': 'memory',
  'difficulty': 'hard',
  'stem': "How does CPython's generational cyclic garbage collector identify and collect reference cycles that "
          'reference counting alone cannot reclaim?',
  'options_json': [{'id': 'a',
                    'text': 'It tracks container objects across three generations, temporarily adjusting reference '
                            'counts to detect unreachable subgraphs.'},
                   {'id': 'b', 'text': 'It pauses all execution and scans all operating system physical RAM pages.'},
                   {'id': 'c', 'text': 'It forces all local variables to be nulled upon function exit.'},
                   {'id': 'd', 'text': 'It converts cyclic references into weak references automatically.'}],
  'correct_option_ids': ['a'],
  'explanation': 'CPython uses a generational cyclic collector that tracks container objects and isolates reference '
                 'cycles by decrementing trial reference counts.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_024',
  'skill': 'Python',
  'sub_domain': 'asyncio',
  'difficulty': 'hard',
  'stem': "When calling 'asyncio.gather(*aws, return_exceptions=False)', what occurs if one of the awaited coroutines "
          'raises an unhandled exception?',
  'options_json': [{'id': 'a',
                    'text': 'The exception propagates immediately to the caller of gather(), while other active tasks '
                            'continue running in the event loop.'},
                   {'id': 'b',
                    'text': 'All other pending tasks are cancelled immediately and their results are discarded.'},
                   {'id': 'c', 'text': 'The exception is suppressed and converted to None in the results list.'},
                   {'id': 'd', 'text': 'The entire asyncio event loop terminates.'}],
  'correct_option_ids': ['a'],
  'explanation': 'With return_exceptions=False, the first exception is raised immediately to the gather() caller; '
                 'sibling tasks continue execution unless explicitly cancelled.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_025',
  'skill': 'Python',
  'sub_domain': 'internals',
  'difficulty': 'hard',
  'stem': 'What memory optimization occurs when declaring \'__slots__ = ("x", "y")\' in a Python class definition?',
  'options_json': [{'id': 'a',
                    'text': 'Instances allocate fixed descriptor pointers instead of creating a per-instance __dict__, '
                            'reducing memory footprint.'},
                   {'id': 'b', 'text': 'Instances are stored in shared read-only cache memory.'},
                   {'id': 'c', 'text': 'The class converts attribute lookups into direct C register operations.'},
                   {'id': 'd', 'text': 'Attributes become immune to garbage collection.'}],
  'correct_option_ids': ['a'],
  'explanation': '__slots__ reserves space for declared attributes directly in the instance struct and avoids creating '
                 'the default per-instance dynamic __dict__.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_026',
  'skill': 'Python',
  'sub_domain': 'scoping',
  'difficulty': 'hard',
  'stem': "What causes the output '[4, 4, 4, 4, 4]' when executing '[f() for f in [lambda: i for i in range(5)]]' in "
          'Python?',
  'options_json': [{'id': 'a',
                    'text': "Late binding: closures bind variable names rather than values, looking up 'i' at "
                            'execution time when the loop has completed.'},
                   {'id': 'b',
                    'text': 'Lambdas are compiled into static functions that share a single return pointer.'},
                   {'id': 'c', 'text': 'The range() function mutates all previously produced numbers.'},
                   {'id': 'd', 'text': 'List comprehensions execute in reverse order internally.'}],
  'correct_option_ids': ['a'],
  'explanation': "Python closures exhibit late binding: the variable 'i' is looked up in the surrounding scope when "
                 "the lambda is called, at which point 'i' is 4.",
  'negative_marking': 0.25},
 {'id': 'mcq_python_027',
  'skill': 'Python',
  'sub_domain': 'internals',
  'difficulty': 'hard',
  'stem': 'What performance benefit is achieved by applying sys.intern(string) on dynamically constructed string '
          'identifiers?',
  'options_json': [{'id': 'a',
                    'text': 'It stores strings in an internal lookup table, enabling O(1) pointer equality comparisons '
                            "via the 'is' operator."},
                   {'id': 'b', 'text': 'It compresses string data using zlib in memory.'},
                   {'id': 'c', 'text': 'It enables mutability of string characters in place.'},
                   {'id': 'd', 'text': 'It converts unicode characters into 8-bit ASCII representations.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Interned strings ensure that identical strings share the exact same memory address, allowing '
                 'comparison to be performed with a single pointer comparison.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_028',
  'skill': 'Python',
  'sub_domain': 'oop',
  'difficulty': 'hard',
  'stem': 'When a class inherits from an abstract base class with unimplemented @abc.abstractmethod methods, at what '
          'point does Python raise an error?',
  'options_json': [{'id': 'a', 'text': 'When attempting to instantiate the subclass at runtime via ClassName().'},
                   {'id': 'b', 'text': 'When the subclass definition is initially parsed by the bytecode compiler.'},
                   {'id': 'c', 'text': 'When the unimplemented abstract method is explicitly invoked.'},
                   {'id': 'd', 'text': 'When the module containing the class is imported.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Python checks for abstract methods when an instantiation attempt occurs (__call__ on the class), '
                 'raising a TypeError if abstract methods remain unoverridden.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_029',
  'skill': 'Python',
  'sub_domain': 'memory',
  'difficulty': 'hard',
  'stem': 'What is the primary operational characteristic of a weakref.ref object in Python?',
  'options_json': [{'id': 'a',
                    'text': 'It references a target object without incrementing its reference count, allowing it to be '
                            'garbage collected when other references vanish.'},
                   {'id': 'b',
                    'text': 'It prevents the referent from ever being freed by the cyclic garbage collector.'},
                   {'id': 'c', 'text': 'It creates an in-memory duplicate of the target object with lower precision.'},
                   {'id': 'd',
                    'text': 'It serializes the target object to disk when memory usage exceeds threshold limits.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Weak references allow referencing an object without preventing its deallocation, making them ideal '
                 'for caches and circular graph mappings.',
  'negative_marking': 0.25},
 {'id': 'mcq_python_030',
  'skill': 'Python',
  'sub_domain': 'concurrency',
  'difficulty': 'hard',
  'stem': "What makes the 'contextvars' module superior to 'threading.local' in asynchronous asyncio applications?",
  'options_json': [{'id': 'a',
                    'text': 'It correctly isolates context values across concurrent coroutines running within the same '
                            'operating system thread.'},
                   {'id': 'b', 'text': 'It bypasses the Global Interpreter Lock for mathematical calculations.'},
                   {'id': 'c', 'text': 'It persists variables across separate operating system process restarts.'},
                   {'id': 'd', 'text': 'It converts asynchronous coroutines into synchronous blocking threads.'}],
  'correct_option_ids': ['a'],
  'explanation': 'threading.local is shared across all coroutines running in the same thread; contextvars provides '
                 'proper context tracking for individual asyncio Tasks.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_001',
  'skill': 'OS',
  'sub_domain': 'concurrency',
  'difficulty': 'easy',
  'stem': 'What memory resource is shared by multiple threads executing within the same process?',
  'options_json': [{'id': 'a', 'text': 'Heap memory and global static variables of the process.'},
                   {'id': 'b', 'text': "Each thread's individual call stack."},
                   {'id': 'c', 'text': "Each thread's individual CPU register state."},
                   {'id': 'd', 'text': 'Isolated virtual address spaces.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Threads in the same process share code, heap memory, and open file descriptors, while maintaining '
                 'their own private thread stacks and registers.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_002',
  'skill': 'OS',
  'sub_domain': 'scheduling',
  'difficulty': 'easy',
  'stem': 'Which CPU scheduling algorithm allocates a fixed time slice (quantum) to each runnable process in cyclic '
          'order?',
  'options_json': [{'id': 'a', 'text': 'Round Robin (RR)'},
                   {'id': 'b', 'text': 'Shortest Job First (SJF)'},
                   {'id': 'c', 'text': 'First-Come, First-Served (FCFS)'},
                   {'id': 'd', 'text': 'Priority Scheduling without preemption'}],
  'correct_option_ids': ['a'],
  'explanation': 'Round Robin scheduling assigns a fixed time quantum to each ready process in a FIFO queue, '
                 'preempting the process when its quantum expires.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_003',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'easy',
  'stem': 'What is the primary architectural purpose of virtual memory in modern operating systems?',
  'options_json': [{'id': 'a',
                    'text': 'To provide each process with a large, contiguous, isolated address space while '
                            'abstracting physical RAM.'},
                   {'id': 'b', 'text': 'To increase the clock frequency of the central processing unit.'},
                   {'id': 'c', 'text': 'To eliminate the need for secondary disk storage devices.'},
                   {'id': 'd', 'text': 'To run multi-threaded programs on single-core processors.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Virtual memory abstracts physical memory into private, uniform address spaces for processes and '
                 'manages mapping to physical RAM and swap storage.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_004',
  'skill': 'OS',
  'sub_domain': 'architecture',
  'difficulty': 'easy',
  'stem': 'What hardware privilege distinction protects operating system integrity from user applications?',
  'options_json': [{'id': 'a',
                    'text': 'Dual-mode operation separating User Mode (Ring 3) and Kernel/Supervisor Mode (Ring 0).'},
                   {'id': 'b', 'text': 'Hardware encryption of all CPU registers during instruction execution.'},
                   {'id': 'c', 'text': 'Dedicated physical motherboards for user code and kernel code.'},
                   {'id': 'd', 'text': 'Restricting user applications to interpreted bytecode.'}],
  'correct_option_ids': ['a'],
  'explanation': 'CPUs provide privilege rings (User mode and Kernel mode) so privileged instructions like direct '
                 'hardware access can execute only in kernel mode.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_005',
  'skill': 'OS',
  'sub_domain': 'architecture',
  'difficulty': 'easy',
  'stem': 'What mechanism enables a user-space application to request a privileged service from the operating system '
          'kernel?',
  'options_json': [{'id': 'a', 'text': "Executing a System Call instruction (such as 'syscall' or a software trap)."},
                   {'id': 'b', 'text': 'Calling a private C function directly across memory addresses.'},
                   {'id': 'c', 'text': 'Writing directly to the hard disk drive controller registers.'},
                   {'id': 'd', 'text': 'Overwriting the CPU instruction pointer register.'}],
  'correct_option_ids': ['a'],
  'explanation': 'System calls cause a controlled hardware trap that switches the CPU from user mode to kernel mode to '
                 'execute requested kernel services.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_006',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'easy',
  'stem': 'Under what condition does the Memory Management Unit (MMU) generate a Page Fault interrupt?',
  'options_json': [{'id': 'a',
                    'text': 'When a process references a virtual page whose valid/present bit is clear in the page '
                            'table.'},
                   {'id': 'b', 'text': 'When physical RAM reaches exactly 100 percent utilization.'},
                   {'id': 'c', 'text': 'When two processes access different physical memory addresses concurrently.'},
                   {'id': 'd', 'text': 'When a thread attempts to allocate memory on its own stack.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A page fault occurs when a virtual memory reference targets a page that is currently not mapped to a '
                 'physical frame in RAM (present bit = 0).',
  'negative_marking': 0.25},
 {'id': 'mcq_os_007',
  'skill': 'OS',
  'sub_domain': 'deadlock',
  'difficulty': 'easy',
  'stem': 'In the context of deadlocks, what characterizes the Circular Wait condition?',
  'options_json': [{'id': 'a',
                    'text': 'A closed chain of processes exists such that each process holds a resource needed by the '
                            'next process in the chain.'},
                   {'id': 'b',
                    'text': 'A process requests the exact same resource repeatedly in an infinite while loop.'},
                   {'id': 'c', 'text': 'CPU schedulers dispatch processes in a circular queue.'},
                   {'id': 'd',
                    'text': 'Multiple threads attempt to acquire memory faster than the allocator can supply.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Circular wait means a set of processes {P0, P1, ... Pn} exists such that P0 waits for a resource '
                 'held by P1, and Pn waits for a resource held by P0.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_008',
  'skill': 'OS',
  'sub_domain': 'synchronization',
  'difficulty': 'easy',
  'stem': 'What is the primary difference between a counting semaphore and a binary semaphore?',
  'options_json': [{'id': 'a',
                    'text': "A counting semaphore's counter can range over an unrestricted integer domain, controlling "
                            'access to a pool of N resources.'},
                   {'id': 'b', 'text': 'A counting semaphore can only be accessed by a single thread.'},
                   {'id': 'c',
                    'text': 'A counting semaphore is implemented in hardware while a binary semaphore is software '
                            'only.'},
                   {'id': 'd', 'text': 'A counting semaphore cannot cause thread blocking.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A counting semaphore tracks a finite number of available resource units (value >= 0), whereas a '
                 'binary semaphore takes only 0 or 1.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_009',
  'skill': 'OS',
  'sub_domain': 'filesystems',
  'difficulty': 'easy',
  'stem': 'Which piece of file metadata is stored inside a Unix inode structure?',
  'options_json': [{'id': 'a', 'text': 'File size, permissions, owner UID, timestamps, and data block pointers.'},
                   {'id': 'b', 'text': 'The human-readable filename string itself.'},
                   {'id': 'c', 'text': 'The full path string of the parent directory.'},
                   {'id': 'd', 'text': 'The memory addresses of currently running user processes.'}],
  'correct_option_ids': ['a'],
  'explanation': 'An inode stores all file metadata and block pointers; the filename and inode mapping are stored '
                 'separately in directory entries.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_010',
  'skill': 'OS',
  'sub_domain': 'scheduling',
  'difficulty': 'easy',
  'stem': 'What distinguishes preemptive CPU scheduling from non-preemptive scheduling?',
  'options_json': [{'id': 'a',
                    'text': 'In preemptive scheduling, the OS can interrupt a running process and move it to the ready '
                            'queue before its burst completes.'},
                   {'id': 'b',
                    'text': 'In preemptive scheduling, processes run until they voluntarily yield or terminate.'},
                   {'id': 'c',
                    'text': 'In preemptive scheduling, priority levels remain static throughout the lifetime of a '
                            'process.'},
                   {'id': 'd',
                    'text': 'In preemptive scheduling, multiple processes execute on a single thread simultaneously.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Preemption allows the kernel scheduler to interrupt a running process (e.g. on timer interrupt or '
                 'higher-priority arrival) to allocate CPU to another process.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_011',
  'skill': 'OS',
  'sub_domain': 'processes',
  'difficulty': 'medium',
  'stem': 'Which component contributes heavily to the performance overhead of an operating system process context '
          'switch?',
  'options_json': [{'id': 'a',
                    'text': 'Saving CPU registers and invalidating/flushing Translation Lookaside Buffer (TLB) virtual '
                            'memory mappings.'},
                   {'id': 'b', 'text': 'Re-formatting the secondary solid-state storage device.'},
                   {'id': 'c', 'text': 'Re-compiling application source code into machine instructions.'},
                   {'id': 'd', 'text': 'Re-generating cryptographic SSL certificates for network sockets.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Context switching between processes requires saving registers and program counters, switching '
                 'address spaces, and flushing or invalidating TLB entries.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_012',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'medium',
  'stem': 'What is the primary function of the Translation Lookaside Buffer (TLB) in CPU memory management?',
  'options_json': [{'id': 'a',
                    'text': 'To act as a high-speed hardware cache for recent virtual-to-physical page number '
                            'translations.'},
                   {'id': 'b', 'text': 'To store executable binary code for the operating system kernel.'},
                   {'id': 'c', 'text': 'To buffer dirty disk blocks before writing them to persistent storage.'},
                   {'id': 'd', 'text': 'To arbitrate network packet transmission between network interface cards.'}],
  'correct_option_ids': ['a'],
  'explanation': 'The TLB is an on-chip associative cache that stores recent virtual page to physical frame '
                 'translations, avoiding multi-level page table walks.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_013',
  'skill': 'OS',
  'sub_domain': 'deadlock',
  'difficulty': 'medium',
  'stem': 'What are the four Coffman conditions that must hold simultaneously for a deadlock to arise?',
  'options_json': [{'id': 'a', 'text': 'Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.'},
                   {'id': 'b', 'text': 'Atomicity, Consistency, Isolation, and Durability.'},
                   {'id': 'c', 'text': 'Read, Write, Execute, and Append permissions.'},
                   {'id': 'd', 'text': 'FIFO, LRU, LFU, and Optimal replacement.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Deadlock requires all four Coffman conditions to occur concurrently: Mutual exclusion, Hold and '
                 'wait, No preemption, and Circular wait.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_014',
  'skill': 'OS',
  'sub_domain': 'synchronization',
  'difficulty': 'medium',
  'stem': 'What ownership property distinguishes a Mutex from a standard Binary Semaphore?',
  'options_json': [{'id': 'a',
                    'text': 'A mutex enforces ownership: only the specific thread that acquired the mutex can release '
                            '(unlock) it.'},
                   {'id': 'b', 'text': 'A mutex can be unlocked by any thread currently in the ready queue.'},
                   {'id': 'c', 'text': 'A mutex allows multiple threads to enter the critical section simultaneously.'},
                   {'id': 'd', 'text': 'A mutex cannot be used in multi-threaded user applications.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A mutex has an owner thread; only the locking thread may unlock it. A semaphore has no owner and can '
                 'be signalled by any thread.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_015',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'medium',
  'stem': "Which page replacement algorithm is susceptible to Belady's Anomaly, where increasing physical page frames "
          'increases page faults?',
  'options_json': [{'id': 'a', 'text': 'First-In, First-Out (FIFO)'},
                   {'id': 'b', 'text': 'Least Recently Used (LRU)'},
                   {'id': 'c', 'text': 'Optimal Page Replacement (OPT)'},
                   {'id': 'd', 'text': 'Stack-based replacement algorithms'}],
  'correct_option_ids': ['a'],
  'explanation': "Belady's Anomaly occurs in FIFO because it is not a stack algorithm; increasing allocated page "
                 'frames can increase total page faults for certain access patterns.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_016',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'medium',
  'stem': 'How does the Clock (Second Chance) page replacement algorithm approximate LRU efficiently in '
          'hardware/software?',
  'options_json': [{'id': 'a',
                    'text': 'By inspecting a single reference bit per page frame in circular queue order, clearing the '
                            'bit and giving a second chance.'},
                   {'id': 'b',
                    'text': 'By maintaining an exact timestamp of every memory access in a hardware register.'},
                   {'id': 'c', 'text': 'By counting total frequency of accesses across all active processes.'},
                   {'id': 'd', 'text': 'By evicting the newest page loaded into memory.'}],
  'correct_option_ids': ['a'],
  'explanation': 'The Clock algorithm sweeps a pointer over frames: if reference bit is 1, it sets it to 0 and '
                 'advances; if 0, it selects that page for eviction.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_017',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'medium',
  'stem': 'What distinguishes Internal Fragmentation from External Fragmentation in memory allocation?',
  'options_json': [{'id': 'a',
                    'text': 'Internal fragmentation is wasted space inside an allocated block; external fragmentation '
                            'is free space fragmented between allocated blocks.'},
                   {'id': 'b',
                    'text': 'Internal fragmentation occurs on hard disks; external fragmentation occurs in CPU '
                            'registers.'},
                   {'id': 'c', 'text': 'Internal fragmentation can be eliminated by memory compaction.'},
                   {'id': 'd', 'text': 'Internal fragmentation occurs only with variable-sized dynamic partitioning.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Internal fragmentation happens when allocated memory exceeds requested memory (e.g. in fixed pages); '
                 'external occurs when total free memory is broken into small unusable chunks.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_018',
  'skill': 'OS',
  'sub_domain': 'ipc',
  'difficulty': 'medium',
  'stem': 'Why does Shared Memory Inter-Process Communication (IPC) achieve higher throughput than Message Passing '
          '(e.g. Unix pipes)?',
  'options_json': [{'id': 'a',
                    'text': 'Shared memory avoids repeated data copying between user space and kernel space after the '
                            'initial mapping.'},
                   {'id': 'b', 'text': 'Shared memory bypasses CPU cache hierarchy completely.'},
                   {'id': 'c',
                    'text': 'Shared memory automatically synchronizes concurrent writes without requiring locks.'},
                   {'id': 'd', 'text': 'Shared memory encrypts data in hardware.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Pipes and message queues require copying data from user buffer to kernel buffer and then to receiver '
                 'buffer; shared memory maps pages directly into both address spaces.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_019',
  'skill': 'OS',
  'sub_domain': 'processes',
  'difficulty': 'medium',
  'stem': 'How does Copy-on-Write (COW) optimize the performance of the Unix fork() system call?',
  'options_json': [{'id': 'a',
                    'text': 'Parent and child share the same physical pages read-only until either process attempts a '
                            'write, copying only modified pages.'},
                   {'id': 'b', 'text': 'It writes child process memory directly to secondary disk swap space.'},
                   {'id': 'c', 'text': 'It converts all child threads into asynchronous coroutines.'},
                   {'id': 'd', 'text': 'It delays child process creation until the child executes an exec() call.'}],
  'correct_option_ids': ['a'],
  'explanation': 'COW marks pages read-only upon fork(); a page fault traps to the OS only when a write occurs, '
                 'duplicating only the modified page.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_020',
  'skill': 'OS',
  'sub_domain': 'scheduling',
  'difficulty': 'medium',
  'stem': 'How does the Priority Inheritance Protocol resolve the Priority Inversion problem in real-time systems?',
  'options_json': [{'id': 'a',
                    'text': 'By temporarily elevating a lower-priority task holding a resource to the priority of the '
                            'highest-priority task waiting for that resource.'},
                   {'id': 'b', 'text': 'By terminating lower-priority tasks when higher-priority tasks become ready.'},
                   {'id': 'c', 'text': 'By disabling all interrupts during critical section execution.'},
                   {'id': 'd', 'text': 'By assigning equal static priorities to all processes in the system.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Priority inheritance temporarily boosts the priority of a low-priority lock holder to prevent '
                 'medium-priority tasks from preempting it while high-priority tasks wait.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_021',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'hard',
  'stem': 'What is the primary memory-saving advantage of Multi-Level Page Tables over Single-Level Page Tables in a '
          '64-bit architecture?',
  'options_json': [{'id': 'a',
                    'text': 'Page tables for unallocated or unused regions of the virtual address space do not need to '
                            'be instantiated in physical memory.'},
                   {'id': 'b', 'text': 'They compress page table entries using LZFSE compression in hardware.'},
                   {'id': 'c', 'text': 'They eliminate the requirement for Translation Lookaside Buffers.'},
                   {'id': 'd', 'text': 'They allow page table lookups in strictly O(1) single-cycle time.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In multi-level paging, if a whole region of virtual memory is unused, its entire sub-tree of page '
                 'tables is omitted, saving immense amounts of RAM.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_022',
  'skill': 'OS',
  'sub_domain': 'scheduling',
  'difficulty': 'hard',
  'stem': 'In the Linux Completely Fair Scheduler (CFS), which data structure and metric determine the next task '
          'chosen to run on the CPU?',
  'options_json': [{'id': 'a',
                    'text': 'A self-balancing Red-Black Tree selecting the task with the smallest virtual runtime '
                            '(vruntime).'},
                   {'id': 'b', 'text': 'A binary heap selecting the task with the largest remaining time slice.'},
                   {'id': 'c', 'text': 'A FIFO queue tracking process arrival timestamps.'},
                   {'id': 'd', 'text': 'A circular doubly linked list ordered by process ID.'}],
  'correct_option_ids': ['a'],
  'explanation': 'CFS uses a red-black tree keyed on vruntime (virtual runtime); the leftmost node represents the task '
                 'that has received the least CPU time and is scheduled next.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_023',
  'skill': 'OS',
  'sub_domain': 'synchronization',
  'difficulty': 'hard',
  'stem': "Why does Peterson's software mutual exclusion algorithm fail on modern multicore processors without "
          'explicit memory barriers (fences)?',
  'options_json': [{'id': 'a',
                    'text': 'Modern out-of-order processors and compilers can reorder stores and loads to different '
                            'memory locations, breaking sequential consistency assumptions.'},
                   {'id': 'b', 'text': 'Multicore processors do not support shared memory between cores.'},
                   {'id': 'c',
                    'text': "Peterson's algorithm is mathematically limited to single-core 8-bit microcontrollers."},
                   {'id': 'd', 'text': 'Atomic test-and-set hardware instructions disable software flag variables.'}],
  'correct_option_ids': ['a'],
  'explanation': "Peterson's algorithm relies on strict sequential consistency; modern CPUs reorder independent "
                 'read/write operations for performance unless memory fences enforce ordering.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_024',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'hard',
  'stem': 'What design characteristic defines an Inverted Page Table?',
  'options_json': [{'id': 'a',
                    'text': 'It contains one entry per physical frame of RAM rather than per virtual page, indexing '
                            'entries via a hash of process ID and virtual page number.'},
                   {'id': 'b',
                    'text': 'It stores page translations in reverse byte order to match big-endian architectures.'},
                   {'id': 'c', 'text': 'It maps virtual addresses directly to disk block sectors instead of RAM.'},
                   {'id': 'd', 'text': 'It is maintained by user-space applications rather than kernel MMU code.'}],
  'correct_option_ids': ['a'],
  'explanation': 'An inverted page table has one entry per physical frame in memory, dramatically bounding table size '
                 'to physical RAM size; lookups use a hash anchor table.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_025',
  'skill': 'OS',
  'sub_domain': 'memory',
  'difficulty': 'hard',
  'stem': 'What condition marks the onset of Thrashing in a virtual memory system?',
  'options_json': [{'id': 'a',
                    'text': 'The sum of the working sets of all active processes exceeds total available physical RAM, '
                            'causing the system to spend more time paging than executing instructions.'},
                   {'id': 'b',
                    'text': 'The CPU cache reaches maximum clock frequency and triggers thermal throttling.'},
                   {'id': 'c', 'text': 'Two processes acquire mutex locks in reverse order.'},
                   {'id': 'd', 'text': 'The page table overflows its designated kernel allocation buffer.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Thrashing happens when the aggregate working sets exceed available frames, resulting in continuous '
                 'page faults and disk I/O thrashing with minimal useful computation.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_026',
  'skill': 'OS',
  'sub_domain': 'io',
  'difficulty': 'hard',
  'stem': 'How does Direct Memory Access (DMA) cycle stealing interact with CPU operation during bulk data transfers?',
  'options_json': [{'id': 'a',
                    'text': 'The DMA controller temporarily takes control of the memory bus for a bus cycle, briefly '
                            'delaying CPU access to RAM.'},
                   {'id': 'b',
                    'text': 'The DMA controller halts the CPU clock permanently until the transfer finishes.'},
                   {'id': 'c',
                    'text': 'The DMA controller re-routes CPU instructions through peripheral device buffers.'},
                   {'id': 'd', 'text': 'The DMA controller executes CPU instructions on behalf of the application.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In cycle stealing, the DMA controller transfers one word at a time by capturing the system bus for a '
                 'single bus cycle, interweaving transfers with CPU execution.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_027',
  'skill': 'OS',
  'sub_domain': 'synchronization',
  'difficulty': 'hard',
  'stem': "Why must a condition variable wait call (such as pthread_cond_wait) always be wrapped inside a 'while' loop "
          'checking the state predicate?',
  'options_json': [{'id': 'a',
                    'text': 'To guard against spurious wakeups and handle race conditions where another thread '
                            'consumes the condition before the waking thread reacquires the mutex.'},
                   {'id': 'b', 'text': 'Because condition variables can only be signaled once in their lifetime.'},
                   {'id': 'c', 'text': 'To prevent compiler optimization from stripping the wait function call.'},
                   {'id': 'd', 'text': 'Because POSIX threads do not permit mutex unlocking inside condition calls.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Threads may wake spuriously or another thread may modify the shared state between wake-up and lock '
                 're-acquisition, necessitating a re-check in a while loop.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_028',
  'skill': 'OS',
  'sub_domain': 'security',
  'difficulty': 'hard',
  'stem': 'Which microarchitectural hardware behavior was exploited by the Meltdown vulnerability to read privileged '
          'kernel memory from user space?',
  'options_json': [{'id': 'a',
                    'text': 'Speculative out-of-order execution executing instructions past permission checks, leaving '
                            'observable traces in the CPU cache hierarchy via side-channel analysis.'},
                   {'id': 'b', 'text': 'A buffer overflow bug in the Linux system call dispatch assembly stub.'},
                   {'id': 'c',
                    'text': 'Weak cryptographic key generation in operating system random number generators.'},
                   {'id': 'd', 'text': 'Stack smashing attacks bypassing Address Space Layout Randomization (ASLR).'}],
  'correct_option_ids': ['a'],
  'explanation': 'Meltdown exploited out-of-order speculative execution where the CPU loads kernel memory before '
                 'privilege checks retire, leaking data through cache timing side-channels.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_029',
  'skill': 'OS',
  'sub_domain': 'realtime',
  'difficulty': 'hard',
  'stem': 'Under Rate Monotonic Scheduling (RMS) for periodic real-time tasks, what criterion determines the static '
          'priority assigned to a task?',
  'options_json': [{'id': 'a', 'text': 'Tasks with shorter repetition periods receive higher static priorities.'},
                   {'id': 'b', 'text': 'Tasks with longer execution times receive higher static priorities.'},
                   {'id': 'c', 'text': 'Tasks with earlier absolute deadlines receive higher dynamic priorities.'},
                   {'id': 'd', 'text': 'Tasks with the highest process ID receive priority.'}],
  'correct_option_ids': ['a'],
  'explanation': 'RMS is an optimal static priority algorithm: shorter period = higher rate = higher priority assigned '
                 'to the task.',
  'negative_marking': 0.25},
 {'id': 'mcq_os_030',
  'skill': 'OS',
  'sub_domain': 'io',
  'difficulty': 'hard',
  'stem': 'How does the Linux io_uring subsystem achieve high-throughput asynchronous I/O compared to traditional '
          'epoll-based architectures?',
  'options_json': [{'id': 'a',
                    'text': 'By using two ring buffers (submission and completion queues) in shared memory, allowing '
                            'lockless zero-copy submission and completion without per-I/O system calls.'},
                   {'id': 'b', 'text': 'By offloading all file system operations to graphics processing units (GPUs).'},
                   {'id': 'c',
                    'text': 'By compressing disk blocks in user space before transmitting across Unix domain sockets.'},
                   {'id': 'd', 'text': 'By enforcing synchronous single-threaded execution across worker threads.'}],
  'correct_option_ids': ['a'],
  'explanation': 'io_uring shares submission and completion ring buffers directly between user space and kernel space, '
                 'enabling batched and polling operations without syscall overhead.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_001',
  'skill': 'Computer Networks',
  'sub_domain': 'osi_model',
  'difficulty': 'easy',
  'stem': 'Which layer of the OSI model provides end-to-end communication, segmentation, and reliability services '
          'between application processes?',
  'options_json': [{'id': 'a', 'text': 'Transport Layer (Layer 4)'},
                   {'id': 'b', 'text': 'Network Layer (Layer 3)'},
                   {'id': 'c', 'text': 'Data Link Layer (Layer 2)'},
                   {'id': 'd', 'text': 'Session Layer (Layer 5)'}],
  'correct_option_ids': ['a'],
  'explanation': 'The Transport Layer (e.g. TCP, UDP) is responsible for process-to-process communication, data '
                 'segmentation, flow control, and end-to-end error recovery.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_002',
  'skill': 'Computer Networks',
  'sub_domain': 'protocols',
  'difficulty': 'easy',
  'stem': 'What distinguishes TCP from UDP regarding connection establishment and delivery guarantees?',
  'options_json': [{'id': 'a',
                    'text': 'TCP is connection-oriented and guarantees reliable, ordered packet delivery, whereas UDP '
                            'is connectionless and best-effort.'},
                   {'id': 'b',
                    'text': 'TCP is connectionless and faster, whereas UDP establishes a three-way handshake.'},
                   {'id': 'c',
                    'text': 'TCP transmits exclusively over optical fiber, whereas UDP operates only on copper '
                            'wiring.'},
                   {'id': 'd',
                    'text': 'TCP encrypts all packet payloads by default, whereas UDP transmits plaintext.'}],
  'correct_option_ids': ['a'],
  'explanation': 'TCP establishes a stateful connection with handshakes, sequence numbers, and retransmissions, '
                 'whereas UDP sends datagrams without establishing a connection.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_003',
  'skill': 'Computer Networks',
  'sub_domain': 'ip_addressing',
  'difficulty': 'easy',
  'stem': 'What is the bit length of an IPv6 address compared to a standard IPv4 address?',
  'options_json': [{'id': 'a', 'text': 'IPv6 addresses are 128 bits long, whereas IPv4 addresses are 32 bits long.'},
                   {'id': 'b', 'text': 'IPv6 addresses are 64 bits long, whereas IPv4 addresses are 16 bits long.'},
                   {'id': 'c', 'text': 'IPv6 addresses are 256 bits long, whereas IPv4 addresses are 64 bits long.'},
                   {'id': 'd', 'text': 'IPv6 addresses are 512 bits long, whereas IPv4 addresses are 128 bits long.'}],
  'correct_option_ids': ['a'],
  'explanation': 'IPv4 uses 32-bit addresses (4 octets), providing ~4.3 billion addresses, while IPv6 uses 128-bit '
                 'addresses (16 octets) to provide a vast address space.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_004',
  'skill': 'Computer Networks',
  'sub_domain': 'dns',
  'difficulty': 'easy',
  'stem': 'What is the primary role of the Domain Name System (DNS) on the internet?',
  'options_json': [{'id': 'a', 'text': 'Translating human-readable domain names into numerical IP addresses.'},
                   {'id': 'b', 'text': 'Encrypting web pages during transport over HTTP connections.'},
                   {'id': 'c', 'text': 'Allocating physical MAC addresses to network interface cards.'},
                   {'id': 'd', 'text': 'Routing optical signals through undersea telecommunication cables.'}],
  'correct_option_ids': ['a'],
  'explanation': "DNS serves as the internet's directory service, resolving domain names (like example.com) to "
                 'corresponding IP addresses.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_005',
  'skill': 'Computer Networks',
  'sub_domain': 'security',
  'difficulty': 'easy',
  'stem': 'What security protocol distinguishes HTTPS traffic from standard HTTP traffic?',
  'options_json': [{'id': 'a',
                    'text': 'Transport Layer Security (TLS/SSL) providing encryption and server authentication.'},
                   {'id': 'b', 'text': 'Simple Mail Transfer Protocol (SMTP).'},
                   {'id': 'c', 'text': 'Border Gateway Protocol (BGP).'},
                   {'id': 'd', 'text': 'Dynamic Host Configuration Protocol (DHCP).'}],
  'correct_option_ids': ['a'],
  'explanation': 'HTTPS runs standard HTTP communication over a cryptographically secured TLS session, ensuring '
                 'confidentiality and integrity.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_006',
  'skill': 'Computer Networks',
  'sub_domain': 'data_link',
  'difficulty': 'easy',
  'stem': 'At which layer of the OSI architecture does a 48-bit Media Access Control (MAC) address operate?',
  'options_json': [{'id': 'a', 'text': 'Data Link Layer (Layer 2)'},
                   {'id': 'b', 'text': 'Network Layer (Layer 3)'},
                   {'id': 'c', 'text': 'Physical Layer (Layer 1)'},
                   {'id': 'd', 'text': 'Transport Layer (Layer 4)'}],
  'correct_option_ids': ['a'],
  'explanation': 'MAC addresses are physical layer-2 hardware identifiers used by network interface cards and local '
                 'Ethernet switches to deliver frames within a local link.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_007',
  'skill': 'Computer Networks',
  'sub_domain': 'devices',
  'difficulty': 'easy',
  'stem': 'What primary OSI layer distinction separates a Network Router from a standard Layer 2 Ethernet Switch?',
  'options_json': [{'id': 'a',
                    'text': 'A router forwards packets based on Layer 3 IP addresses across networks, whereas a switch '
                            'forwards frames based on Layer 2 MAC addresses within a network.'},
                   {'id': 'b', 'text': 'A router operates at Layer 7, whereas a switch operates at Layer 1.'},
                   {'id': 'c',
                    'text': 'A router handles wireless connections only, whereas a switch connects wired fiber.'},
                   {'id': 'd', 'text': 'A router converts digital signals into analog sound waves.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Routers operate at Layer 3 (Network) using IP routing tables, while Layer 2 switches use MAC address '
                 'tables to forward Ethernet frames within a single broadcast domain.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_008',
  'skill': 'Computer Networks',
  'sub_domain': 'transport',
  'difficulty': 'easy',
  'stem': 'What are the standard default TCP port numbers assigned for HTTP and HTTPS services?',
  'options_json': [{'id': 'a', 'text': 'Port 80 for HTTP and Port 443 for HTTPS.'},
                   {'id': 'b', 'text': 'Port 21 for HTTP and Port 22 for HTTPS.'},
                   {'id': 'c', 'text': 'Port 25 for HTTP and Port 110 for HTTPS.'},
                   {'id': 'd', 'text': 'Port 53 for HTTP and Port 67 for HTTPS.'}],
  'correct_option_ids': ['a'],
  'explanation': 'IANA assigns well-known port 80 to unencrypted HTTP and well-known port 443 to TLS-encrypted HTTPS.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_009',
  'skill': 'Computer Networks',
  'sub_domain': 'network_layer',
  'difficulty': 'easy',
  'stem': "Which protocol is utilized by the 'ping' utility to test network reachability and measure round-trip time?",
  'options_json': [{'id': 'a', 'text': 'Internet Control Message Protocol (ICMP)'},
                   {'id': 'b', 'text': 'Transmission Control Protocol (TCP)'},
                   {'id': 'c', 'text': 'User Datagram Protocol (UDP)'},
                   {'id': 'd', 'text': 'File Transfer Protocol (FTP)'}],
  'correct_option_ids': ['a'],
  'explanation': 'Ping sends ICMP Echo Request messages and waits for corresponding ICMP Echo Reply messages from the '
                 'destination host.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_010',
  'skill': 'Computer Networks',
  'sub_domain': 'ip_addressing',
  'difficulty': 'easy',
  'stem': 'What is the primary function of a subnet mask in IPv4 addressing?',
  'options_json': [{'id': 'a',
                    'text': 'Distinguishing the network identifier portion from the host identifier portion of an IP '
                            'address.'},
                   {'id': 'b', 'text': 'Encrypting the source IP address in packet headers.'},
                   {'id': 'c', 'text': 'Assigning DNS domain suffixes to local devices.'},
                   {'id': 'd', 'text': 'Controlling the physical baud rate of network cables.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A subnet mask uses contiguous 1 bits to delineate the network prefix and 0 bits to identify host '
                 'addresses within that subnetwork.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_011',
  'skill': 'Computer Networks',
  'sub_domain': 'tcp',
  'difficulty': 'medium',
  'stem': 'What is the exact sequence of flag packets exchanged during the standard TCP Three-Way Handshake?',
  'options_json': [{'id': 'a', 'text': 'SYN -> SYN-ACK -> ACK'},
                   {'id': 'b', 'text': 'ACK -> SYN -> SYN-ACK'},
                   {'id': 'c', 'text': 'SYN -> ACK -> DATA'},
                   {'id': 'd', 'text': 'FIN -> ACK -> FIN-ACK'}],
  'correct_option_ids': ['a'],
  'explanation': 'The client initiates connection with SYN; the server responds with SYN-ACK; the client completes '
                 'connection establishment with ACK.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_012',
  'skill': 'Computer Networks',
  'sub_domain': 'tcp',
  'difficulty': 'medium',
  'stem': 'What is the primary purpose of the TIME_WAIT state entered by an active TCP endpoint during connection '
          'termination?',
  'options_json': [{'id': 'a',
                    'text': 'Ensuring the final ACK is received by the remote peer and allowing lingering duplicate '
                            'segments to expire in the network.'},
                   {'id': 'b', 'text': 'Waiting for the application to compile pending database queries.'},
                   {'id': 'c', 'text': 'Negotiating higher MTU sizes for future connections.'},
                   {'id': 'd', 'text': 'Allowing the operating system to perform memory compaction.'}],
  'correct_option_ids': ['a'],
  'explanation': 'TIME_WAIT lasts 2*MSL to ensure the remote peer received the final ACK and to prevent stale delayed '
                 'segments from a closed connection corrupting a new connection on the same port.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_013',
  'skill': 'Computer Networks',
  'sub_domain': 'congestion_control',
  'difficulty': 'medium',
  'stem': 'In TCP Tahoe/Reno congestion control, what algorithm governs the initial exponential growth of the '
          'congestion window (cwnd)?',
  'options_json': [{'id': 'a', 'text': 'Slow Start algorithm'},
                   {'id': 'b', 'text': 'Congestion Avoidance algorithm'},
                   {'id': 'c', 'text': 'Fast Recovery algorithm'},
                   {'id': 'd', 'text': 'Additive Increase Multiplicative Decrease (AIMD)'}],
  'correct_option_ids': ['a'],
  'explanation': 'During Slow Start, TCP doubles its congestion window every round-trip time (incrementing cwnd by 1 '
                 'MSS for each ACK received) until ssthresh is reached.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_014',
  'skill': 'Computer Networks',
  'sub_domain': 'nat',
  'difficulty': 'medium',
  'stem': 'How does Network Address and Port Translation (NAPT/PAT) allow multiple private IP hosts to share a single '
          'public IPv4 address?',
  'options_json': [{'id': 'a',
                    'text': 'By translating internal private IP and source port combinations into the single public IP '
                            'with unique external source ports.'},
                   {'id': 'b', 'text': 'By assigning fractional IP addresses to connected clients.'},
                   {'id': 'c', 'text': 'By compressing all outgoing packets into a single TCP connection.'},
                   {'id': 'd', 'text': 'By converting IPv4 packets into IPv6 tunnels automatically.'}],
  'correct_option_ids': ['a'],
  'explanation': "NAPT maps private socket pairs (private IP + port) to the router's public IP address with distinct "
                 'translated source port numbers in a NAT translation table.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_015',
  'skill': 'Computer Networks',
  'sub_domain': 'arp',
  'difficulty': 'medium',
  'stem': 'What is the primary function of the Address Resolution Protocol (ARP) within a local network?',
  'options_json': [{'id': 'a',
                    'text': 'Resolving a known target IPv4 address to its corresponding physical MAC hardware '
                            'address.'},
                   {'id': 'b', 'text': 'Assigning dynamic IP addresses to newly booted client machines.'},
                   {'id': 'c', 'text': 'Encrypting local Ethernet broadcast packets.'},
                   {'id': 'd', 'text': 'Determining the optimal internet route across autonomous systems.'}],
  'correct_option_ids': ['a'],
  'explanation': "ARP broadcasts a query asking 'Who has IP X.X.X.X? Tell MAC Y:Y:Y:Y', mapping logical Layer 3 "
                 'addresses to physical Layer 2 link addresses.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_016',
  'skill': 'Computer Networks',
  'sub_domain': 'routing',
  'difficulty': 'medium',
  'stem': 'What distinguishes Link-State routing protocols (such as OSPF) from Distance-Vector routing protocols (such '
          'as RIP)?',
  'options_json': [{'id': 'a',
                    'text': 'Link-State routers flood topological information so every router builds a complete map of '
                            'the entire network graph, whereas Distance-Vector routers exchange distance vectors only '
                            'with immediate neighbors.'},
                   {'id': 'b', 'text': 'Link-State protocols are limited to 15 hops maximum.'},
                   {'id': 'c', 'text': "Distance-Vector protocols compute shortest paths using Dijkstra's algorithm."},
                   {'id': 'd',
                    'text': 'Link-State protocols route packets without inspecting destination IP addresses.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Link-State protocols (OSPF, IS-IS) flood LSA states to build a full global topology map and run '
                 "Dijkstra's algorithm locally; Distance-Vector protocols (RIP, BGP) share bellman-ford vectors.",
  'negative_marking': 0.25},
 {'id': 'mcq_cn_017',
  'skill': 'Computer Networks',
  'sub_domain': 'tls',
  'difficulty': 'medium',
  'stem': 'What optimization in TLS 1.3 reduces connection latency during initial cryptographic negotiation compared '
          'to TLS 1.2?',
  'options_json': [{'id': 'a',
                    'text': 'Reducing the full cryptographic handshake from two round trips (2-RTT) down to a single '
                            'round trip (1-RTT).'},
                   {'id': 'b', 'text': 'Eliminating symmetric key encryption entirely.'},
                   {'id': 'c', 'text': 'Transferring certificate authority verification to local client disk cache.'},
                   {'id': 'd', 'text': 'Enforcing static pre-shared passwords across all websites.'}],
  'correct_option_ids': ['a'],
  'explanation': 'TLS 1.3 combines key-share guessing in the ClientHello with cipher selection, reducing full '
                 'handshake latency to 1-RTT, and supports 0-RTT resumption.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_018',
  'skill': 'Computer Networks',
  'sub_domain': 'tcp',
  'difficulty': 'medium',
  'stem': 'What is the fundamental difference between Flow Control and Congestion Control in TCP?',
  'options_json': [{'id': 'a',
                    'text': "Flow control prevents the sender from overwhelming the receiver's receive buffer, whereas "
                            'congestion control prevents the sender from overwhelming network links.'},
                   {'id': 'b',
                    'text': 'Flow control is managed by intermediate routers; congestion control is managed by the '
                            'destination host.'},
                   {'id': 'c',
                    'text': 'Flow control controls packet routing paths; congestion control manages packet '
                            'encryption.'},
                   {'id': 'd', 'text': 'Flow control applies only to UDP traffic.'}],
  'correct_option_ids': ['a'],
  'explanation': "Flow control is an end-to-end mechanism based on the receiver's advertised window (rwnd); congestion "
                 'control dynamically modulates cwnd to protect shared network capacity.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_019',
  'skill': 'Computer Networks',
  'sub_domain': 'application_layer',
  'difficulty': 'medium',
  'stem': 'How does HTTP/2 solve application-layer Head-of-Line (HoL) blocking experienced in HTTP/1.1?',
  'options_json': [{'id': 'a',
                    'text': 'By multiplexing multiple concurrent bidirectional request and response streams as binary '
                            'frames over a single shared TCP connection.'},
                   {'id': 'b', 'text': 'By opening a separate TCP connection for every single asset file.'},
                   {'id': 'c', 'text': 'By replacing TCP entirely with raw UDP sockets.'},
                   {'id': 'd', 'text': 'By caching all possible server responses inside local DNS resolvers.'}],
  'correct_option_ids': ['a'],
  'explanation': 'HTTP/2 introduces a binary framing layer that interleaves frames from multiple requests and '
                 'responses over a single TCP socket, preventing one slow request from blocking others.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_020',
  'skill': 'Computer Networks',
  'sub_domain': 'routing',
  'difficulty': 'medium',
  'stem': 'Which routing protocol architecture characterizes the Border Gateway Protocol (BGP) used to route traffic '
          'between Autonomous Systems (AS)?',
  'options_json': [{'id': 'a',
                    'text': 'Path-Vector protocol that records the entire sequence of Autonomous Systems along a route '
                            'to prevent routing loops.'},
                   {'id': 'b', 'text': 'Pure Link-State protocol running Dijkstra across all global hosts.'},
                   {'id': 'c', 'text': 'Centralized master-slave routing database hosted by ICANN.'},
                   {'id': 'd', 'text': 'Broadcasting routing tables via ICMP redirect frames.'}],
  'correct_option_ids': ['a'],
  'explanation': 'BGP is a path-vector protocol; routing updates include the AS_PATH attribute, listing all autonomous '
                 'systems traversed, allowing loop detection and policy-based routing.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_021',
  'skill': 'Computer Networks',
  'sub_domain': 'protocols',
  'difficulty': 'hard',
  'stem': 'How does HTTP/3 / QUIC eliminate transport-layer Head-of-Line (HoL) blocking that persists in HTTP/2 over '
          'TCP?',
  'options_json': [{'id': 'a',
                    'text': 'By implementing independent stream handling directly over UDP, so a dropped packet delays '
                            'only the affected stream rather than all streams.'},
                   {'id': 'b', 'text': 'By disabling packet retransmission across all streams.'},
                   {'id': 'c', 'text': 'By guaranteeing 100 percent packet delivery over physical radio waves.'},
                   {'id': 'd', 'text': 'By forcing client devices to connect via multiple physical Ethernet cards.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In TCP, a single lost packet halts delivery of all data in the stream buffer. QUIC runs streams over '
                 'UDP, isolating loss recovery so lost packets only block the stream they belong to.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_022',
  'skill': 'Computer Networks',
  'sub_domain': 'congestion_control',
  'difficulty': 'hard',
  'stem': "How does Google's BBR (Bottleneck Bandwidth and RTT) congestion control algorithm differ fundamentally from "
          'loss-based algorithms like TCP CUBIC?',
  'options_json': [{'id': 'a',
                    'text': 'It constructs an explicit model of the network bottleneck by measuring delivery rate and '
                            'round-trip time, operating at the Kleinrock optimum without relying on packet loss as a '
                            'congestion signal.'},
                   {'id': 'b',
                    'text': 'It increases the sending rate exponentially until bufferbloat causes 50 percent packet '
                            'drops.'},
                   {'id': 'c', 'text': 'It requires special hardware support on all intermediate commercial routers.'},
                   {'id': 'd', 'text': 'It operates strictly on local area network switches.'}],
  'correct_option_ids': ['a'],
  'explanation': 'BBR measures bottleneck bandwidth and minimum RTT to establish the optimal inflight data volume, '
                 'preventing bufferbloat and avoiding the loss-driven oscillations of Reno/CUBIC.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_023',
  'skill': 'Computer Networks',
  'sub_domain': 'security',
  'difficulty': 'hard',
  'stem': 'How does the SYN Cookies technique protect a server against TCP SYN flood attacks without exhausting kernel '
          'memory?',
  'options_json': [{'id': 'a',
                    'text': 'The server encodes connection state into the initial sequence number (ISN) and allocates '
                            'zero kernel state until receiving the valid client ACK.'},
                   {'id': 'b',
                    'text': 'The server drops all incoming SYN packets originating from outside its subnet.'},
                   {'id': 'c',
                    'text': 'The server allocates double memory buffers in RAM for each pending connection.'},
                   {'id': 'd', 'text': 'The server forces the client to compute a proof-of-work cryptographic hash.'}],
  'correct_option_ids': ['a'],
  'explanation': "SYN cookies calculate a cryptographic hash of client/server IPs, ports, and a secret as the server's "
                 'ISN, deferring SYN queue allocation until the client returns the ACK.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_024',
  'skill': 'Computer Networks',
  'sub_domain': 'routing',
  'difficulty': 'hard',
  'stem': 'How does BGP Anycast routing enable global Content Delivery Networks (CDNs) and DNS root servers to route '
          'users to the topologically nearest point of presence?',
  'options_json': [{'id': 'a',
                    'text': 'Multiple geographically dispersed servers announce the exact same IP address prefix via '
                            'BGP, allowing internet routing to direct packets along the shortest AS path.'},
                   {'id': 'b',
                    'text': 'A central DNS server tracks client GPS coordinates and updates IP assignments '
                            'dynamically.'},
                   {'id': 'c',
                    'text': 'Packets are duplicated and broadcast across all global data centers simultaneously.'},
                   {'id': 'd', 'text': 'Clients establish peer-to-peer mesh connections to find nearby servers.'}],
  'correct_option_ids': ['a'],
  'explanation': 'With Anycast, identical IP addresses are advertised by multiple nodes across different network '
                 'locations; BGP routing directs traffic to the nearest instance according to routing metrics.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_025',
  'skill': 'Computer Networks',
  'sub_domain': 'network_layer',
  'difficulty': 'hard',
  'stem': 'How does Path MTU Discovery (PMTUD) determine the largest permissible IP packet size along a network path '
          'without IP fragmentation?',
  'options_json': [{'id': 'a',
                    'text': "The sender sets the Don't Fragment (DF) bit in IP headers, and intermediate routers with "
                            "smaller MTU drop the packet and return ICMP 'Fragmentation Needed' with their next-hop "
                            'MTU.'},
                   {'id': 'b',
                    'text': 'The sender queries the DNS server for the router hardware specifications along the path.'},
                   {'id': 'c', 'text': 'The receiver fragments packets and reassembles them in user space.'},
                   {'id': 'd', 'text': 'The sender tests every packet size from 64 to 65535 bytes sequentially.'}],
  'correct_option_ids': ['a'],
  'explanation': 'PMTUD sets the DF flag; if a router encounters an MTU restriction, it drops the packet and responds '
                 'with ICMP Type 3 Code 4 specifying the maximum acceptable next-hop MTU.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_026',
  'skill': 'Computer Networks',
  'sub_domain': 'tcp',
  'difficulty': 'hard',
  'stem': 'Why is the TCP TIME_WAIT state duration traditionally defined as 2 * Maximum Segment Lifetime (2MSL)?',
  'options_json': [{'id': 'a',
                    'text': 'To account for the maximum time a final ACK can travel to the destination plus the time '
                            'for a retransmitted FIN to arrive in case the ACK was lost.'},
                   {'id': 'b', 'text': 'To allow the client operating system to cool down CPU clock temperatures.'},
                   {'id': 'c', 'text': 'To permit DHCP lease renewal before releasing socket resources.'},
                   {'id': 'd', 'text': 'To give the application time to flush logs to persistent magnetic disk.'}],
  'correct_option_ids': ['a'],
  'explanation': 'MSL is the maximum time a segment can exist in the network. Waiting 2*MSL ensures any delayed '
                 'segments from the previous connection incarnation have completely expired.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_027',
  'skill': 'Computer Networks',
  'sub_domain': 'dns',
  'difficulty': 'hard',
  'stem': 'What cryptographic validation mechanism allows DNSSEC to establish authenticity and data integrity for DNS '
          'responses?',
  'options_json': [{'id': 'a',
                    'text': 'Digital signatures (RRSIG records) generated over resource record sets (RRsets), '
                            'validated against a chain of trust anchored at the root zone DNSKEY.'},
                   {'id': 'b', 'text': 'Encrypting all DNS UDP payloads with symmetric AES-256 keys.'},
                   {'id': 'c',
                    'text': 'Establishing mandatory TLS tunnels between all client machines and root DNS servers.'},
                   {'id': 'd', 'text': 'Validating client IP addresses against a global whitelist.'}],
  'correct_option_ids': ['a'],
  'explanation': 'DNSSEC signs RRsets with private keys producing RRSIG records; resolvers verify the cryptographic '
                 'signature using DNSKEY and DS records ascending to the trust root.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_028',
  'skill': 'Computer Networks',
  'sub_domain': 'transport',
  'difficulty': 'hard',
  'stem': "How does Nagle's algorithm prevent the proliferation of tiny packets ('Silly Window Syndrome' on the sender "
          'side)?',
  'options_json': [{'id': 'a',
                    'text': 'It delays sending small data segments if there is unacknowledged data in flight, '
                            'buffering until a full Maximum Segment Size (MSS) accumulates or an ACK is received.'},
                   {'id': 'b', 'text': 'It drops packets smaller than 512 bytes automatically.'},
                   {'id': 'c', 'text': 'It forces the receiver to open a 64KB receive window upon connection setup.'},
                   {'id': 'd', 'text': 'It encrypts packet headers to compress them down to zero bytes.'}],
  'correct_option_ids': ['a'],
  'explanation': "Nagle's algorithm buffers outgoing small chunks if any previously sent segment remains unACKed, "
                 'transmitting immediately only when a full MSS is ready or pending ACKs arrive.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_029',
  'skill': 'Computer Networks',
  'sub_domain': 'routing',
  'difficulty': 'hard',
  'stem': 'In an OSPF network, how does the link-state flooding mechanism ensure that all routers converge on an '
          'identical Link-State Database (LSDB)?',
  'options_json': [{'id': 'a',
                    'text': 'Routers flood Link-State Advertisements (LSAs) containing link metrics, acknowledging '
                            'receipt with Link-State ACKs and tracking sequence numbers to prevent stale updates.'},
                   {'id': 'b',
                    'text': 'The designated router collects routing tables and copies them to routers via FTP.'},
                   {'id': 'c', 'text': 'Routers poll neighbor routing tables every 30 seconds over UDP.'},
                   {'id': 'd', 'text': 'Routers exchange only the single best next hop for each known destination.'}],
  'correct_option_ids': ['a'],
  'explanation': 'OSPF ensures LSDB synchronization by flooding LSAs with age and sequence numbers, ensuring every '
                 'router within an area builds the identical topological graph.',
  'negative_marking': 0.25},
 {'id': 'mcq_cn_030',
  'skill': 'Computer Networks',
  'sub_domain': 'tcp',
  'difficulty': 'hard',
  'stem': 'How does the TCP Selective Acknowledgment (SACK) option improve retransmission efficiency when multiple '
          'packets are dropped in a single window?',
  'options_json': [{'id': 'a',
                    'text': 'The receiver explicitly reports non-contiguous received byte blocks in TCP header '
                            'options, enabling the sender to retransmit only the missing segments.'},
                   {'id': 'b',
                    'text': 'The sender resets the entire TCP connection and re-establishes the three-way handshake.'},
                   {'id': 'c', 'text': 'The receiver retransmits the dropped packets on behalf of the sender.'},
                   {'id': 'd',
                    'text': 'The sender retransmits all packets starting from the first dropped segment up to the '
                            'current window.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Standard TCP cumulative ACK forces retransmission of all subsequent packets (Go-Back-N); SACK '
                 'identifies isolated gaps so the sender retransmits only lost segments.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_001',
  'skill': 'DSA',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'Which element access order characterizes a standard Stack data structure?',
  'options_json': [{'id': 'a', 'text': 'Last-In, First-Out (LIFO)'},
                   {'id': 'b', 'text': 'First-In, First-Out (FIFO)'},
                   {'id': 'c', 'text': 'Priority-ordered access'},
                   {'id': 'd', 'text': 'Random index access'}],
  'correct_option_ids': ['a'],
  'explanation': 'A stack operates on the Last-In, First-Out (LIFO) principle, where the most recently added element '
                 'is the first one removed.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_002',
  'skill': 'DSA',
  'sub_domain': 'algorithms',
  'difficulty': 'easy',
  'stem': 'What is the worst-case time complexity of Binary Search executed on a sorted array of N elements?',
  'options_json': [{'id': 'a', 'text': 'O(log n)'},
                   {'id': 'b', 'text': 'O(n)'},
                   {'id': 'c', 'text': 'O(n log n)'},
                   {'id': 'd', 'text': 'O(1)'}],
  'correct_option_ids': ['a'],
  'explanation': 'Binary search halves the remaining search space with each comparison, running in O(log n) '
                 'logarithmic time.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_003',
  'skill': 'DSA',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'What fundamental components comprise a standard node in a Singly Linked List?',
  'options_json': [{'id': 'a', 'text': 'A data payload and a pointer/reference to the subsequent node.'},
                   {'id': 'b', 'text': 'A data payload, a previous pointer, and a next pointer.'},
                   {'id': 'c', 'text': 'A key, a value, and a hash code.'},
                   {'id': 'd', 'text': 'An array of fixed memory addresses.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A singly linked list node contains the element value and a single link pointer pointing to the next '
                 'node in the sequence.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_004',
  'skill': 'DSA',
  'sub_domain': 'data_structures',
  'difficulty': 'easy',
  'stem': 'What is the time complexity to retrieve an element by its index in a contiguous memory array?',
  'options_json': [{'id': 'a', 'text': 'O(1) constant time'},
                   {'id': 'b', 'text': 'O(log n) logarithmic time'},
                   {'id': 'c', 'text': 'O(n) linear time'},
                   {'id': 'd', 'text': 'O(n^2) quadratic time'}],
  'correct_option_ids': ['a'],
  'explanation': 'Array elements occupy contiguous memory, allowing immediate address computation (base + index * '
                 'element_size) in O(1) time.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_005',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'easy',
  'stem': 'What ordering invariant must hold for every node X in a valid Binary Search Tree (BST)?',
  'options_json': [{'id': 'a',
                    'text': "All keys in X's left subtree are strictly less than X's key, and all keys in X's right "
                            'subtree are strictly greater.'},
                   {'id': 'b', 'text': 'All parent nodes must contain values smaller than their child nodes.'},
                   {'id': 'c', 'text': 'The depth of left and right subtrees must be identical across all levels.'},
                   {'id': 'd', 'text': 'Nodes must contain exactly two children without exception.'}],
  'correct_option_ids': ['a'],
  'explanation': 'The BST property dictates that for any node X, all left descendant keys are less than X.key, and all '
                 'right descendant keys are greater than X.key.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_006',
  'skill': 'DSA',
  'sub_domain': 'hashing',
  'difficulty': 'easy',
  'stem': 'What is the average-case time complexity of inserting a key-value pair into a Hash Table with a uniform '
          'hash distribution?',
  'options_json': [{'id': 'a', 'text': 'O(1)'},
                   {'id': 'b', 'text': 'O(log n)'},
                   {'id': 'c', 'text': 'O(n)'},
                   {'id': 'd', 'text': 'O(n log n)'}],
  'correct_option_ids': ['a'],
  'explanation': 'With a good hash function and appropriate load factor management, hash table insertions and lookups '
                 'execute in average O(1) time.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_007',
  'skill': 'DSA',
  'sub_domain': 'sorting',
  'difficulty': 'easy',
  'stem': 'What is the average and worst-case time complexity of standard Bubble Sort on an array of size N?',
  'options_json': [{'id': 'a', 'text': 'O(n^2)'},
                   {'id': 'b', 'text': 'O(n log n)'},
                   {'id': 'c', 'text': 'O(n)'},
                   {'id': 'd', 'text': 'O(log n)'}],
  'correct_option_ids': ['a'],
  'explanation': 'Bubble sort performs repeated passes over the array comparing adjacent pairs, yielding O(n^2) '
                 'comparisons and swaps in both average and worst cases.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_008',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'easy',
  'stem': 'Which tree traversal order visits the nodes of a Binary Search Tree in strictly ascending sorted numerical '
          'order?',
  'options_json': [{'id': 'a', 'text': 'Inorder Traversal (Left, Root, Right)'},
                   {'id': 'b', 'text': 'Preorder Traversal (Root, Left, Right)'},
                   {'id': 'c', 'text': 'Postorder Traversal (Left, Right, Root)'},
                   {'id': 'd', 'text': 'Level-order Traversal'}],
  'correct_option_ids': ['a'],
  'explanation': 'Inorder traversal visits the left subtree, then the root, then the right subtree, producing keys in '
                 'sorted order for any valid BST.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_009',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'easy',
  'stem': 'What is the primary memory advantage of representing a sparse graph with V vertices and E edges using an '
          'Adjacency List instead of an Adjacency Matrix?',
  'options_json': [{'id': 'a',
                    'text': 'Adjacency lists consume O(V + E) space, which is far lower than the O(V^2) space consumed '
                            'by an adjacency matrix when E is small.'},
                   {'id': 'b',
                    'text': 'Adjacency lists allow O(1) edge existence queries between any pair of vertices.'},
                   {'id': 'c', 'text': 'Adjacency lists eliminate the need to store vertex values in memory.'},
                   {'id': 'd', 'text': 'Adjacency lists are stored in CPU L1 cache exclusively.'}],
  'correct_option_ids': ['a'],
  'explanation': 'For sparse graphs where E << V^2, an adjacency list stores only existing edges taking O(V + E) '
                 'space, whereas an adjacency matrix always allocates V x V cells.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_010',
  'skill': 'DSA',
  'sub_domain': 'heaps',
  'difficulty': 'easy',
  'stem': 'What structural condition defines a Min-Heap binary tree?',
  'options_json': [{'id': 'a',
                    'text': 'The key at the root is the minimum in the tree, and the key of every node is less than or '
                            'equal to the keys of its children.'},
                   {'id': 'b',
                    'text': 'Every left child must be strictly smaller than every right child across all levels.'},
                   {'id': 'c', 'text': 'Leaf nodes contain the smallest values in the data structure.'},
                   {'id': 'd', 'text': 'All nodes in the tree must have two children.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In a min-heap, the min-heap property requires parent <= children for every node, placing the global '
                 'minimum at the root.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_011',
  'skill': 'DSA',
  'sub_domain': 'sorting',
  'difficulty': 'medium',
  'stem': 'Under what circumstance does standard QuickSort degrade to its worst-case time complexity of O(n^2)?',
  'options_json': [{'id': 'a',
                    'text': 'When the chosen pivot repeatedly partitions the array into one empty subarray and one '
                            'subarray of size n - 1.'},
                   {'id': 'b', 'text': 'When the array elements are completely random with uniform distribution.'},
                   {'id': 'c', 'text': 'When the pivot always divides the array into two exactly equal halves.'},
                   {'id': 'd', 'text': 'When the array size is a power of two.'}],
  'correct_option_ids': ['a'],
  'explanation': 'QuickSort degrades to O(n^2) when partitions are maximally unbalanced (e.g. selecting the first/last '
                 'element on an already sorted array without randomization).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_012',
  'skill': 'DSA',
  'sub_domain': 'sorting',
  'difficulty': 'medium',
  'stem': 'What is the auxiliary space complexity of standard Merge Sort implemented on an array of size N?',
  'options_json': [{'id': 'a', 'text': 'O(n) auxiliary memory to hold temporary arrays during the merge operation.'},
                   {'id': 'b', 'text': 'O(1) in-place auxiliary memory.'},
                   {'id': 'c', 'text': 'O(log n) auxiliary memory.'},
                   {'id': 'd', 'text': 'O(n^2) auxiliary memory.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Standard array-based merge sort requires O(n) temporary buffer space to merge two sorted halves into '
                 'a combined sorted sequence.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_013',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'medium',
  'stem': 'Which graph traversal algorithm guarantees finding the shortest path (minimum edge count) between two '
          'vertices in an unweighted graph?',
  'options_json': [{'id': 'a', 'text': 'Breadth-First Search (BFS)'},
                   {'id': 'b', 'text': 'Depth-First Search (DFS)'},
                   {'id': 'c', 'text': 'Inorder Traversal'},
                   {'id': 'd', 'text': 'Topological Sort'}],
  'correct_option_ids': ['a'],
  'explanation': 'BFS explores vertices in increasing order of distance from the source using a queue, guaranteeing '
                 'the shortest path in unweighted graphs.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_014',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'medium',
  'stem': 'How can Depth-First Search (DFS) detect cycles in a directed graph during traversal?',
  'options_json': [{'id': 'a',
                    'text': 'By detecting a back-edge pointing to an ancestor vertex currently active on the recursion '
                            'call stack.'},
                   {'id': 'b', 'text': 'By counting whether total edges exceed total vertices.'},
                   {'id': 'c', 'text': 'By verifying whether all vertices have even degrees.'},
                   {'id': 'd', 'text': 'By calculating the sum of edge weights.'}],
  'correct_option_ids': ['a'],
  'explanation': 'In directed graphs, a cycle exists if and only if DFS encounters a back edge to a node that is '
                 'currently in the recursion stack (grey node in 3-color model).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_015',
  'skill': 'DSA',
  'sub_domain': 'hashing',
  'difficulty': 'medium',
  'stem': 'What primary trade-off distinguishes Open Addressing (with Linear Probing) from Separate Chaining for hash '
          'collision resolution?',
  'options_json': [{'id': 'a',
                    'text': 'Open addressing provides superior CPU cache locality by storing all entries in the '
                            'primary table array, but suffers from clustering as load factor rises.'},
                   {'id': 'b', 'text': 'Open addressing permits an infinite load factor greater than 1.0.'},
                   {'id': 'c', 'text': 'Separate chaining consumes zero pointer overhead.'},
                   {'id': 'd', 'text': 'Separate chaining requires sorted hash buckets.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Open addressing stores items contiguously in the table for great cache performance, but clustering '
                 'degrades performance when full; chaining uses linked lists per bucket.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_016',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'medium',
  'stem': 'What balance invariant must hold at every node in an AVL self-balancing binary search tree?',
  'options_json': [{'id': 'a',
                    'text': 'The balance factor (height difference between left and right subtrees) must be within '
                            '{-1, 0, +1}.'},
                   {'id': 'b', 'text': 'The number of nodes in left and right subtrees must differ by at most one.'},
                   {'id': 'c', 'text': 'All leaves must reside on the exact same depth level.'},
                   {'id': 'd', 'text': 'Every node must be colored either red or black.'}],
  'correct_option_ids': ['a'],
  'explanation': 'An AVL tree maintains height balance by guaranteeing that for every node, |height(left) - '
                 'height(right)| <= 1, restoring balance via rotations when violated.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_017',
  'skill': 'DSA',
  'sub_domain': 'heaps',
  'difficulty': 'medium',
  'stem': 'What are the time complexities for pushing a new element and popping the minimum element in a binary '
          'min-heap containing N elements?',
  'options_json': [{'id': 'a', 'text': 'O(log n) for push, and O(log n) for pop.'},
                   {'id': 'b', 'text': 'O(1) for push, and O(n) for pop.'},
                   {'id': 'c', 'text': 'O(n) for push, and O(1) for pop.'},
                   {'id': 'd', 'text': 'O(1) for push, and O(log n) for pop.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Push adds an element at the end and sifts up in O(log n); pop removes the root, swaps the last '
                 'element to the root, and sifts down in O(log n).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_018',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'medium',
  'stem': "What is the time complexity of Dijkstra's algorithm implemented with a binary min-heap priority queue on a "
          'graph with V vertices and E edges?',
  'options_json': [{'id': 'a', 'text': 'O((V + E) log V)'},
                   {'id': 'b', 'text': 'O(V^2)'},
                   {'id': 'c', 'text': 'O(V * E)'},
                   {'id': 'd', 'text': 'O(E * log E + V^2)'}],
  'correct_option_ids': ['a'],
  'explanation': 'With a binary heap, extracting min takes O(V log V) and decreasing keys / pushing edges takes O(E '
                 'log V), yielding O((V + E) log V).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_019',
  'skill': 'DSA',
  'sub_domain': 'data_structures',
  'difficulty': 'medium',
  'stem': 'What is the amortized time complexity per operation in a Disjoint Set Union (DSU / Union-Find) data '
          'structure employing both Path Compression and Union by Rank?',
  'options_json': [{'id': 'a',
                    'text': 'O(alpha(n)), where alpha is the inverse Ackermann function, effectively constant time.'},
                   {'id': 'b', 'text': 'O(log n) strictly.'},
                   {'id': 'c', 'text': 'O(n) linear time.'},
                   {'id': 'd', 'text': 'O(n log n).'}],
  'correct_option_ids': ['a'],
  'explanation': 'Combining path compression and union by rank yields an amortized operational complexity of '
                 'O(alpha(n)), which is less than 5 for all practical input sizes.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_020',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'medium',
  'stem': 'What mathematical graph property is strictly required for a graph to possess a valid Topological Ordering?',
  'options_json': [{'id': 'a', 'text': 'The graph must be a Directed Acyclic Graph (DAG).'},
                   {'id': 'b', 'text': 'The graph must be strongly connected and undirected.'},
                   {'id': 'c', 'text': 'The graph must be bipartite.'},
                   {'id': 'd', 'text': 'The graph must have an Eulerian circuit.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Topological sorting linearly orders vertices such that for every directed edge u -> v, u comes '
                 'before v. This is possible if and only if the graph has no directed cycles (DAG).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_021',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'hard',
  'stem': 'Which structural invariant must a valid Red-Black Tree satisfy regarding paths from any node to its '
          'descendant null leaves?',
  'options_json': [{'id': 'a',
                    'text': 'Every path from a node to any of its descendant null leaves contains the exact same '
                            'number of black nodes (uniform black-height).'},
                   {'id': 'b', 'text': 'All red nodes must be positioned exclusively at leaf positions.'},
                   {'id': 'c', 'text': 'The total count of red nodes must exceed the total count of black nodes.'},
                   {'id': 'd', 'text': 'The root node must always be colored red.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A key Red-Black tree invariant is that all simple paths from any node to descendant leaves must '
                 'contain the identical count of black nodes, bounding maximum path length to 2*log(n).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_022',
  'skill': 'DSA',
  'sub_domain': 'strings',
  'difficulty': 'hard',
  'stem': 'What is the time complexity to precompute the Longest Prefix Suffix (LPS) lookup array in the '
          'Knuth-Morris-Pratt (KMP) string search algorithm for a pattern of length M?',
  'options_json': [{'id': 'a', 'text': 'O(m) linear time in the length of the pattern.'},
                   {'id': 'b', 'text': 'O(m^2) quadratic time.'},
                   {'id': 'c', 'text': 'O(m log m).'},
                   {'id': 'd', 'text': 'O(2^m) exponential time.'}],
  'correct_option_ids': ['a'],
  'explanation': "KMP's preprocessing builds the LPS array in O(m) time using two pointers and dynamic matching, "
                 'enabling the main text scan to execute in O(n) without backtracking.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_023',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'hard',
  'stem': "How does Tarjan's algorithm identify Strongly Connected Components (SCCs) in a directed graph within a "
          'single DFS traversal?',
  'options_json': [{'id': 'a',
                    'text': 'By maintaining discovery timestamps and low-link values on a stack, identifying an SCC '
                            'root when low-link equals discovery timestamp.'},
                   {'id': 'b', 'text': 'By reversing all graph edges and running a second DFS pass.'},
                   {'id': 'c', 'text': 'By performing all-pairs shortest paths matrix exponentiation.'},
                   {'id': 'd', 'text': 'By computing the minimum spanning tree of the undirected graph.'}],
  'correct_option_ids': ['a'],
  'explanation': "Tarjan's algorithm assigns discovery times and computes low-link values using a single DFS traversal "
                 'and an explicit stack, isolating SCCs in O(V + E) time.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_024',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'hard',
  'stem': 'What are the time complexities for point updates and range sum queries on a standard Segment Tree '
          'constructed over an array of size N?',
  'options_json': [{'id': 'a', 'text': 'O(log n) for point update, and O(log n) for range query.'},
                   {'id': 'b', 'text': 'O(1) for point update, and O(n) for range query.'},
                   {'id': 'c', 'text': 'O(n) for point update, and O(1) for range query.'},
                   {'id': 'd', 'text': 'O(log n) for point update, and O(n log n) for range query.'}],
  'correct_option_ids': ['a'],
  'explanation': 'A segment tree has height O(log n); updating a single leaf traverses up the tree in O(log n), and '
                 'canonical range queries inspect at most 4 nodes per level in O(log n).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_025',
  'skill': 'DSA',
  'sub_domain': 'dynamic_programming',
  'difficulty': 'hard',
  'stem': 'What is the dynamic programming recurrence and time complexity of the Floyd-Warshall algorithm for '
          'all-pairs shortest paths on V vertices?',
  'options_json': [{'id': 'a',
                    'text': 'dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j]) running in O(V^3) time across three '
                            'nested loops.'},
                   {'id': 'b', 'text': 'dist[i][j] = dist[i][j-1] + dist[i-1][j] running in O(V^2) time.'},
                   {'id': 'c', 'text': 'dist[i][j] = max(dist[i][k], dist[k][j]) running in O(V * log V) time.'},
                   {'id': 'd', 'text': 'dist[i] = min(dist[i], dist[u] + weight(u, i)) running in O(V * E) time.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Floyd-Warshall iteratively checks whether an intermediate vertex k improves the path between i and j '
                 'via three nested loops over V vertices, taking O(V^3) time.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_026',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'hard',
  'stem': 'What action occurs in a B-Tree of order M when a key insertion causes a node to contain M keys (exceeding '
          'maximum capacity M - 1)?',
  'options_json': [{'id': 'a',
                    'text': 'The node splits into two sibling nodes of floor((M-1)/2) keys, and the median key is '
                            'promoted up into the parent node.'},
                   {'id': 'b', 'text': 'The oldest key in the node is evicted to disk swap.'},
                   {'id': 'c', 'text': 'The entire B-Tree is rebuilt from scratch via bulk loading.'},
                   {'id': 'd', 'text': 'The tree rotates the root node 90 degrees.'}],
  'correct_option_ids': ['a'],
  'explanation': 'When an internal node overflows in a B-Tree of order M, it splits into two halves around the median '
                 'key, which is pushed up into the parent node.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_027',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'hard',
  'stem': 'How does the Bellman-Ford algorithm detect the presence of a negative-weight cycle reachable from the '
          'source vertex?',
  'options_json': [{'id': 'a',
                    'text': 'By performing a V-th relaxation pass over all edges; if any edge distance can still be '
                            'relaxed after V - 1 iterations, a negative cycle exists.'},
                   {'id': 'b', 'text': 'By checking if total vertex distances become zero.'},
                   {'id': 'c', 'text': 'By calculating the determinant of the graph adjacency matrix.'},
                   {'id': 'd', 'text': 'By verifying if the graph can be topographically sorted.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Shortest paths in a cycle-free graph contain at most V - 1 edges. If relaxing all edges on iteration '
                 'V produces further distance reductions, a negative cycle exists.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_028',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'hard',
  'stem': 'What is the time complexity of searching for a word of length L in a Trie containing N stored words of '
          'maximum length M?',
  'options_json': [{'id': 'a',
                    'text': 'O(L) time, dependent only on the length of the query word and independent of N.'},
                   {'id': 'b', 'text': 'O(log N) time.'},
                   {'id': 'c', 'text': 'O(N * L) time.'},
                   {'id': 'd', 'text': 'O(M * log N) time.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Trie lookups traverse down one edge per character in the search string, completing in O(L) time '
                 'regardless of the total number of words N in the tree.',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_029',
  'skill': 'DSA',
  'sub_domain': 'graphs',
  'difficulty': 'hard',
  'stem': 'In the Edmonds-Karp implementation of the Ford-Fulkerson method for Maximum Flow, what guarantees '
          'polynomial time complexity of O(V * E^2)?',
  'options_json': [{'id': 'a',
                    'text': 'Using Breadth-First Search (BFS) to find the shortest augmenting path in terms of edge '
                            'count in each iteration.'},
                   {'id': 'b', 'text': 'Using Depth-First Search with randomized edge selection.'},
                   {'id': 'c', 'text': 'Assigning infinite capacity to all backward residual edges.'},
                   {'id': 'd', 'text': 'Restricting the network to planar graphs.'}],
  'correct_option_ids': ['a'],
  'explanation': 'Edmonds-Karp specifically chooses augmenting paths with the fewest edges using BFS. This guarantees '
                 'the shortest path distance is monotonically non-decreasing, bounding runtime to O(V * E^2).',
  'negative_marking': 0.25},
 {'id': 'mcq_dsa_030',
  'skill': 'DSA',
  'sub_domain': 'trees',
  'difficulty': 'hard',
  'stem': "How does a Fenwick Tree (Binary Indexed Tree) isolate the lowest set bit of an integer index 'i' to "
          'traverse parent and update indices?',
  'options_json': [{'id': 'a', 'text': "Using the bitwise expression 'i & (-i)' via two's complement arithmetic."},
                   {'id': 'b', 'text': "Using the bitwise expression 'i | (~i)'."},
                   {'id': 'c', 'text': "Using 'i >> 1' logical right shift."},
                   {'id': 'd', 'text': "Using 'i ^ (i - 1)'."}],
  'correct_option_ids': ['a'],
  'explanation': "In two's complement, -i = (~i + 1). Performing i & (-i) isolates the least significant bit (LSB) "
                 'that is set to 1, allowing O(log n) tree updates and queries.',
  'negative_marking': 0.25}]

PHASE2_SQL_BANK: list[dict[str, Any]] = [{'id': 'sql_prob_001',
  'difficulty': 'easy',
  'prompt': '### High-Value Customers\n'
            '\n'
            'Write a query to find the names and total spending of active customers who have spent strictly more than '
            '100 in total across all their orders.\n'
            '\n'
            '**Output columns:** `name`, `total_spent`\n'
            '\n'
            'Order results by `total_spent` in descending order, then by `name` in ascending order.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT c.name, SUM(o.amount) AS total_spent\n'
                     '            FROM customers c\n'
                     '            JOIN orders o ON c.id = o.customer_id\n'
                     "            WHERE c.status = 'active'\n"
                     '            GROUP BY c.id, c.name\n'
                     '            HAVING SUM(o.amount) > 100\n'
                     '            ORDER BY total_spent DESC, c.name ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'All inactive or zero matching rows',
             'seed_data': '\n'
                          '                    INSERT INTO customers (id, name, status) VALUES\n'
                          "                        (1, 'Grace', 'inactive'),\n"
                          "                        (2, 'Heidi', 'pending');\n"
                          '                    INSERT INTO orders (id, customer_id, amount) VALUES\n'
                          '                        (1, 1, 500.0),\n'
                          '                        (2, 2, 600.0);\n'
                          '                '}]},
 {'id': 'sql_prob_002',
  'difficulty': 'easy',
  'prompt': '### Employee Department Directory\n'
            '\n'
            'Write a query to list the employee name, department name, and salary for all employees whose salary is at '
            'least 50000.\n'
            '\n'
            '**Output columns:** `employee_name`, `department_name`, `salary`\n'
            '\n'
            'Order by `salary` descending, then `employee_name` ascending.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT e.name AS employee_name, d.name AS department_name, e.salary\n'
                     '            FROM employees e\n'
                     '            JOIN departments d ON e.department_id = d.id\n'
                     '            WHERE e.salary >= 50000\n'
                     '            ORDER BY e.salary DESC, employee_name ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample employees and departments',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, "
                          "'Sales');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Alice', 1, 75000),\n"
                          "                        (2, 'Bob', 2, 48000),\n"
                          "                        (3, 'Charlie', 1, 50000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Tied salaries and varied departments',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'HR'), (2, 'Finance'), "
                          "(3, 'Legal');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Dan', 1, 60000),\n"
                          "                        (2, 'Carol', 2, 60000),\n"
                          "                        (3, 'Eve', 3, 90000),\n"
                          "                        (4, 'Frank', 1, 30000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Boundary check exactly 50000 and below',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (10, 'Operations');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Grace', 10, 49999.99),\n"
                          "                        (2, 'Hank', 10, 50000.00);\n"
                          '                '}]},
 {'id': 'sql_prob_003',
  'difficulty': 'easy',
  'prompt': '### Product Category Inventory\n'
            '\n'
            'Write a query to calculate total stock quantity per product category for categories where category is not '
            'null and total stock exceeds 10 units.\n'
            '\n'
            '**Output columns:** `category`, `total_stock`\n'
            '\n'
            'Order by `total_stock` descending, then `category` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE products (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                name TEXT NOT NULL,\n'
                '                category TEXT,\n'
                '                stock_quantity INTEGER NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT category, SUM(stock_quantity) AS total_stock\n'
                     '            FROM products\n'
                     '            WHERE category IS NOT NULL\n'
                     '            GROUP BY category\n'
                     '            HAVING SUM(stock_quantity) > 10\n'
                     '            ORDER BY total_stock DESC, category ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample product inventory',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category, stock_quantity) VALUES\n'
                          "                        (1, 'Laptop', 'Electronics', 5),\n"
                          "                        (2, 'Mouse', 'Electronics', 10),\n"
                          "                        (3, 'Desk', 'Furniture', 3),\n"
                          "                        (4, 'Pen', NULL, 100);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Exact threshold 10 and null categories',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category, stock_quantity) VALUES\n'
                          "                        (1, 'Chair', 'Furniture', 10),\n"
                          "                        (2, 'Sofa', 'Furniture', 1),\n"
                          "                        (3, 'Apples', 'Grocery', 10),\n"
                          "                        (4, 'Oranges', 'Grocery', 0),\n"
                          "                        (5, 'Notebook', 'Stationery', 25);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'All categories below threshold',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category, stock_quantity) VALUES\n'
                          "                        (1, 'Item A', 'CatA', 2),\n"
                          "                        (2, 'Item B', 'CatA', 3),\n"
                          "                        (3, 'Item C', 'CatB', 9);\n"
                          '                '}]},
 {'id': 'sql_prob_004',
  'difficulty': 'easy',
  'prompt': '### Average Book Price by Publisher\n'
            '\n'
            'Write a query to find the rounded average book price (to 2 decimal places) for publishers that have '
            'published at least 2 books.\n'
            '\n'
            '**Output columns:** `publisher`, `avg_price`\n'
            '\n'
            'Order by `avg_price` descending, then `publisher` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE books (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                title TEXT NOT NULL,\n'
                '                publisher TEXT NOT NULL,\n'
                '                price REAL NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT publisher, ROUND(AVG(price), 2) AS avg_price\n'
                     '            FROM books\n'
                     '            GROUP BY publisher\n'
                     '            HAVING COUNT(*) >= 2\n'
                     '            ORDER BY avg_price DESC, publisher ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample books across publishers',
             'seed_data': '\n'
                          '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                          "                        (1, 'Book A', 'OReilly', 45.50),\n"
                          "                        (2, 'Book B', 'OReilly', 54.50),\n"
                          "                        (3, 'Book C', 'Manning', 39.99),\n"
                          "                        (4, 'Book D', 'Addison-Wesley', 60.00);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Multiple publishers with varying book counts',
             'seed_data': '\n'
                          '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                          "                        (1, 'Book 1', 'Manning', 40.00),\n"
                          "                        (2, 'Book 2', 'Manning', 50.00),\n"
                          "                        (3, 'Book 3', 'Manning', 60.00),\n"
                          "                        (4, 'Book 4', 'Packt', 25.00),\n"
                          "                        (5, 'Book 5', 'Packt', 35.00),\n"
                          "                        (6, 'Book 6', 'Springer', 120.00);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Decimal rounding verification',
             'seed_data': '\n'
                          '                    INSERT INTO books (id, title, publisher, price) VALUES\n'
                          "                        (1, 'Intro', 'TechPress', 10.333),\n"
                          "                        (2, 'Advanced', 'TechPress', 20.333);\n"
                          '                '}]},
 {'id': 'sql_prob_005',
  'difficulty': 'easy',
  'prompt': '### Most Recent User Login\n'
            '\n'
            'Write a query to find the username and latest login timestamp for each user who has at least one recorded '
            'login.\n'
            '\n'
            '**Output columns:** `username`, `last_login`\n'
            '\n'
            'Order by `username` in ascending alphabetical order.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT u.username, MAX(l.login_timestamp) AS last_login\n'
                     '            FROM users u\n'
                     '            JOIN logins l ON u.id = l.user_id\n'
                     '            GROUP BY u.id, u.username\n'
                     '            ORDER BY u.username ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample users and login timestamps',
             'seed_data': '\n'
                          "                    INSERT INTO users (id, username) VALUES (1, 'alice'), (2, 'bob'), (3, "
                          "'charlie');\n"
                          '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                          "                        (1, 1, '2026-01-01 10:00:00'),\n"
                          "                        (2, 1, '2026-01-02 12:00:00'),\n"
                          "                        (3, 2, '2026-01-01 08:30:00');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'User without logins and out-of-order timestamps',
             'seed_data': '\n'
                          "                    INSERT INTO users (id, username) VALUES (1, 'zara'), (2, 'adam'), (3, "
                          "'no_login');\n"
                          '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                          "                        (1, 1, '2026-02-15 09:00:00'),\n"
                          "                        (2, 1, '2026-02-10 11:00:00'),\n"
                          "                        (3, 2, '2026-01-20 14:00:00');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single login per user',
             'seed_data': '\n'
                          "                    INSERT INTO users (id, username) VALUES (1, 'echo'), (2, 'delta');\n"
                          '                    INSERT INTO logins (id, user_id, login_timestamp) VALUES\n'
                          "                        (1, 1, '2026-03-01 00:00:00'),\n"
                          "                        (2, 2, '2026-03-02 00:00:00');\n"
                          '                '}]},
 {'id': 'sql_prob_006',
  'difficulty': 'easy',
  'prompt': '### Top Selling Products by Volume\n'
            '\n'
            'Write a query to retrieve the top 3 selling products based on total units sold.\n'
            '\n'
            '**Output columns:** `name`, `total_sold`\n'
            '\n'
            'Order by `total_sold` descending, then `name` ascending. Limit to 3 rows.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT p.name, SUM(oi.quantity) AS total_sold\n'
                     '            FROM products p\n'
                     '            JOIN order_items oi ON p.id = oi.product_id\n'
                     '            GROUP BY p.id, p.name\n'
                     '            ORDER BY total_sold DESC, p.name ASC\n'
                     '            LIMIT 3;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample sales data with 4 products',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name) VALUES\n'
                          "                        (1, 'Keyboard'), (2, 'Monitor'), (3, 'Mouse'), (4, 'Headphones');\n"
                          '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                          '                        (1, 1, 10), (2, 2, 5), (3, 3, 15), (4, 4, 8), (5, 1, 5);\n'
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Tie breaker on name and multiple orders',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name) VALUES\n'
                          "                        (1, 'Alpha'), (2, 'Beta'), (3, 'Gamma'), (4, 'Delta');\n"
                          '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                          '                        (1, 1, 20), (2, 2, 20), (3, 3, 30), (4, 4, 5);\n'
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Fewer than 3 products in database',
             'seed_data': '\n'
                          "                    INSERT INTO products (id, name) VALUES (1, 'Solo'), (2, 'Duo');\n"
                          '                    INSERT INTO order_items (id, product_id, quantity) VALUES\n'
                          '                        (1, 1, 50), (2, 2, 25);\n'
                          '                '}]},
 {'id': 'sql_prob_007',
  'difficulty': 'easy',
  'prompt': '### Unassigned High-Priority Tickets\n'
            '\n'
            "Write a query to list the id and title of all support tickets with 'high' priority that have not been "
            'assigned to any agent (`agent_id` is NULL).\n'
            '\n'
            '**Output columns:** `id`, `title`\n'
            '\n'
            'Order by `id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE tickets (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                title TEXT NOT NULL,\n'
                '                agent_id INTEGER,\n'
                '                priority TEXT NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT id, title\n'
                     '            FROM tickets\n'
                     "            WHERE agent_id IS NULL AND priority = 'high'\n"
                     '            ORDER BY id ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample tickets with mixed priorities and assignments',
             'seed_data': '\n'
                          '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                          "                        (1, 'Server down', NULL, 'high'),\n"
                          "                        (2, 'Email bounce', 3, 'high'),\n"
                          "                        (3, 'Password reset', NULL, 'low'),\n"
                          "                        (4, 'Data loss', NULL, 'high');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'All tickets assigned or non-high priority',
             'seed_data': '\n'
                          '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                          "                        (10, 'Bug A', 1, 'high'),\n"
                          "                        (11, 'Bug B', NULL, 'medium'),\n"
                          "                        (12, 'Bug C', 2, 'low');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Multiple unassigned high priority tickets',
             'seed_data': '\n'
                          '                    INSERT INTO tickets (id, title, agent_id, priority) VALUES\n'
                          "                        (101, 'Outage Alpha', NULL, 'high'),\n"
                          "                        (102, 'Outage Beta', NULL, 'high'),\n"
                          "                        (103, 'Outage Gamma', NULL, 'high');\n"
                          '                '}]},
 {'id': 'sql_prob_008',
  'difficulty': 'easy',
  'prompt': '### Student Exam Pass Summary\n'
            '\n'
            "Write a query to list each student's name and the total number of exams they have passed (where `score` "
            '>= 60). Include only students who have at least one passed exam.\n'
            '\n'
            '**Output columns:** `name`, `passed_count`\n'
            '\n'
            'Order by `passed_count` descending, then `name` ascending.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT s.name, COUNT(*) AS passed_count\n'
                     '            FROM students s\n'
                     '            JOIN exam_scores e ON s.id = e.student_id\n'
                     '            WHERE e.score >= 60\n'
                     '            GROUP BY s.id, s.name\n'
                     '            ORDER BY passed_count DESC, s.name ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample students and exam scores',
             'seed_data': '\n'
                          "                    INSERT INTO students (id, name) VALUES (1, 'Alice'), (2, 'Bob'), (3, "
                          "'Charlie');\n"
                          '                    INSERT INTO exam_scores (id, student_id, subject, score) VALUES\n'
                          "                        (1, 1, 'Math', 85),\n"
                          "                        (2, 1, 'Physics', 60),\n"
                          "                        (3, 2, 'Math', 55),\n"
                          "                        (4, 3, 'Chemistry', 92);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Threshold boundary at 59 and 60',
             'seed_data': '\n'
                          "                    INSERT INTO students (id, name) VALUES (1, 'Dan'), (2, 'Emma');\n"
                          '                    INSERT INTO exam_scores (id, student_id, subject, score) VALUES\n'
                          "                        (1, 1, 'Biology', 59),\n"
                          "                        (2, 1, 'History', 60),\n"
                          "                        (3, 2, 'History', 59);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Equal passed counts checking tie break',
             'seed_data': '\n'
                          "                    INSERT INTO students (id, name) VALUES (1, 'Zack'), (2, 'Abby');\n"
                          '                    INSERT INTO exam_scores (id, student_id, subject, score) VALUES\n'
                          "                        (1, 1, 'Art', 70),\n"
                          "                        (2, 2, 'Art', 75);\n"
                          '                '}]},
 {'id': 'sql_prob_009',
  'difficulty': 'easy',
  'prompt': '### Unique Daily Checkout Visitors\n'
            '\n'
            "Write a query to count the number of unique visitors who visited any page starting with '/checkout' on "
            'each day.\n'
            '\n'
            '**Output columns:** `view_date`, `unique_visitors`\n'
            '\n'
            'Order by `view_date` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE page_views (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                visitor_id INTEGER NOT NULL,\n'
                '                view_date TEXT NOT NULL,\n'
                '                page_url TEXT NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT view_date, COUNT(DISTINCT visitor_id) AS unique_visitors\n'
                     '            FROM page_views\n'
                     "            WHERE page_url LIKE '/checkout%'\n"
                     '            GROUP BY view_date\n'
                     '            ORDER BY view_date ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample page views across multiple dates',
             'seed_data': '\n'
                          '                    INSERT INTO page_views (id, visitor_id, view_date, page_url) VALUES\n'
                          "                        (1, 101, '2026-03-01', '/checkout/step1'),\n"
                          "                        (2, 101, '2026-03-01', '/checkout/step2'),\n"
                          "                        (3, 102, '2026-03-01', '/home'),\n"
                          "                        (4, 103, '2026-03-01', '/checkout/pay'),\n"
                          "                        (5, 101, '2026-03-02', '/checkout/step1');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'URL pattern matching and deduplication',
             'seed_data': '\n'
                          '                    INSERT INTO page_views (id, visitor_id, view_date, page_url) VALUES\n'
                          "                        (1, 1, '2026-04-10', '/checkout'),\n"
                          "                        (2, 1, '2026-04-10', '/checkout/confirm'),\n"
                          "                        (3, 2, '2026-04-10', '/products/checkout-item'),\n"
                          "                        (4, 3, '2026-04-11', '/checkout');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'No checkout visits',
             'seed_data': '\n'
                          '                    INSERT INTO page_views (id, visitor_id, view_date, page_url) VALUES\n'
                          "                        (1, 5, '2026-05-01', '/about'),\n"
                          "                        (2, 6, '2026-05-01', '/contact');\n"
                          '                '}]},
 {'id': 'sql_prob_010',
  'difficulty': 'easy',
  'prompt': '### High Volume Warehouses\n'
            '\n'
            'Write a query to calculate total inventory quantity per warehouse city for warehouses holding at least '
            '500 total items.\n'
            '\n'
            '**Output columns:** `city`, `total_quantity`\n'
            '\n'
            'Order by `total_quantity` descending, then `city` ascending.',
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
                '        ',
  'reference_query': '\n'
                     '            SELECT w.city, SUM(i.quantity) AS total_quantity\n'
                     '            FROM warehouses w\n'
                     '            JOIN inventory i ON w.id = i.warehouse_id\n'
                     '            GROUP BY w.id, w.city\n'
                     '            HAVING SUM(i.quantity) >= 500\n'
                     '            ORDER BY total_quantity DESC, w.city ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample warehouses and inventory counts',
             'seed_data': '\n'
                          "                    INSERT INTO warehouses (id, city) VALUES (1, 'Chicago'), (2, 'Dallas'), "
                          "(3, 'Seattle');\n"
                          '                    INSERT INTO inventory (id, warehouse_id, item_sku, quantity) VALUES\n'
                          "                        (1, 1, 'SKU-01', 300),\n"
                          "                        (2, 1, 'SKU-02', 250),\n"
                          "                        (3, 2, 'SKU-01', 100),\n"
                          "                        (4, 3, 'SKU-03', 500);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Exact 500 threshold and multiple warehouses',
             'seed_data': '\n'
                          "                    INSERT INTO warehouses (id, city) VALUES (1, 'Boston'), (2, 'Austin');\n"
                          '                    INSERT INTO inventory (id, warehouse_id, item_sku, quantity) VALUES\n'
                          "                        (1, 1, 'A', 499),\n"
                          "                        (2, 2, 'B', 250),\n"
                          "                        (3, 2, 'C', 250);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Tied totals verifying alphabetical city tie break',
             'seed_data': '\n'
                          "                    INSERT INTO warehouses (id, city) VALUES (1, 'Denver'), (2, "
                          "'Atlanta');\n"
                          '                    INSERT INTO inventory (id, warehouse_id, item_sku, quantity) VALUES\n'
                          "                        (1, 1, 'X', 600),\n"
                          "                        (2, 2, 'Y', 600);\n"
                          '                '}]},
 {'id': 'sql_prob_011',
  'difficulty': 'medium',
  'prompt': '### Monthly Revenue Aggregation\n'
            '\n'
            'Write a query to calculate monthly revenue trends from positive transactions (`amount` > 0). For each '
            'month with at least 1000 in total revenue, return the month string (`YYYY-MM`), count of transactions, '
            'and total revenue rounded to 2 decimal places.\n'
            '\n'
            '**Output columns:** `month`, `tx_count`, `total_revenue`\n'
            '\n'
            'Order by `month` in ascending order.',
  'schema_ddl': '\n'
                '            CREATE TABLE transactions (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                amount REAL NOT NULL,\n'
                '                tx_date TEXT NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample transactions across months',
             'seed_data': '\n'
                          '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                          "                        (1, 600.0, '2026-01-05'),\n"
                          "                        (2, 500.0, '2026-01-15'),\n"
                          "                        (3, -50.0, '2026-01-20'),\n"
                          "                        (4, 800.0, '2026-02-01'),\n"
                          "                        (5, 150.0, '2026-02-14');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Multiple months meeting threshold and negative transaction filtering',
             'seed_data': '\n'
                          '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                          "                        (1, 1000.0, '2026-03-01'),\n"
                          "                        (2, 400.0, '2026-04-01'),\n"
                          "                        (3, 700.0, '2026-04-15'),\n"
                          "                        (4, -200.0, '2026-04-20'),\n"
                          "                        (5, 999.99, '2026-05-10');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'All months below threshold or negative amounts',
             'seed_data': '\n'
                          '                    INSERT INTO transactions (id, amount, tx_date) VALUES\n'
                          "                        (1, 200.0, '2026-06-01'),\n"
                          "                        (2, 300.0, '2026-06-02'),\n"
                          "                        (3, -1500.0, '2026-06-03');\n"
                          '                '}]},
 {'id': 'sql_prob_012',
  'difficulty': 'medium',
  'prompt': '### Second Highest Distinct Salary\n'
            '\n'
            'Write a query to find the second highest distinct salary among all employees. If there is no second '
            'highest salary, return NULL as `second_highest_salary`.\n'
            '\n'
            '**Output columns:** `second_highest_salary`',
  'schema_ddl': '\n'
                '            CREATE TABLE employees (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                name TEXT NOT NULL,\n'
                '                department TEXT NOT NULL,\n'
                '                salary REAL NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT (\n'
                     '                SELECT DISTINCT salary\n'
                     '                FROM employees\n'
                     '                ORDER BY salary DESC\n'
                     '                LIMIT 1 OFFSET 1\n'
                     '            ) AS second_highest_salary;\n'
                     '        ',
  'checks_json': {'order_matters': False, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample employees with distinct salaries',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, department, salary) VALUES\n'
                          "                        (1, 'Alice', 'Tech', 100),\n"
                          "                        (2, 'Bob', 'Tech', 200),\n"
                          "                        (3, 'Charlie', 'HR', 300);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Duplicate top salaries testing distinct requirement',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, department, salary) VALUES\n'
                          "                        (1, 'Dave', 'Finance', 500),\n"
                          "                        (2, 'Erin', 'Finance', 500),\n"
                          "                        (3, 'Frank', 'Sales', 400),\n"
                          "                        (4, 'Grace', 'Sales', 300);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Only one distinct salary in table (should return NULL)',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, department, salary) VALUES\n'
                          "                        (1, 'Hank', 'IT', 100),\n"
                          "                        (2, 'Ivy', 'IT', 100);\n"
                          '                '}]},
 {'id': 'sql_prob_013',
  'difficulty': 'medium',
  'prompt': '### Multi-Year Repeat Customers\n'
            '\n'
            'Write a query to find the customer IDs of customers who placed at least one order in 2024 AND at least '
            'one order in 2025.\n'
            '\n'
            '**Output columns:** `customer_id`\n'
            '\n'
            'Order by `customer_id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE orders (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                customer_id INTEGER NOT NULL,\n'
                '                order_date TEXT NOT NULL,\n'
                '                total_amount REAL NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT customer_id\n'
                     '            FROM orders\n'
                     '            GROUP BY customer_id\n'
                     "            HAVING SUM(CASE WHEN strftime('%Y', order_date) = '2024' THEN 1 ELSE 0 END) > 0\n"
                     "               AND SUM(CASE WHEN strftime('%Y', order_date) = '2025' THEN 1 ELSE 0 END) > 0\n"
                     '            ORDER BY customer_id ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample orders across 2024, 2025, and 2026',
             'seed_data': '\n'
                          '                    INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES\n'
                          "                        (1, 101, '2024-05-10', 50.0),\n"
                          "                        (2, 101, '2025-01-15', 75.0),\n"
                          "                        (3, 102, '2024-11-20', 100.0),\n"
                          "                        (4, 103, '2025-03-01', 20.0),\n"
                          "                        (5, 104, '2026-01-01', 10.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Multiple orders per year and boundary years',
             'seed_data': '\n'
                          '                    INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES\n'
                          "                        (1, 1, '2024-01-01', 10.0),\n"
                          "                        (2, 1, '2024-12-31', 20.0),\n"
                          "                        (3, 1, '2025-01-01', 30.0),\n"
                          "                        (4, 2, '2023-12-31', 100.0),\n"
                          "                        (5, 2, '2024-06-01', 100.0),\n"
                          "                        (6, 3, '2025-06-01', 50.0),\n"
                          "                        (7, 4, '2024-03-01', 15.0),\n"
                          "                        (8, 4, '2025-09-01', 25.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'No customer meeting condition',
             'seed_data': '\n'
                          '                    INSERT INTO orders (id, customer_id, order_date, total_amount) VALUES\n'
                          "                        (1, 10, '2023-05-01', 50.0),\n"
                          "                        (2, 20, '2026-05-01', 50.0);\n"
                          '                '}]},
 {'id': 'sql_prob_014',
  'difficulty': 'medium',
  'prompt': '### Department Highest Earners\n'
            '\n'
            'Write a query to find the employees who earn the highest salary in each department. If there are ties for '
            'the maximum salary in a department, include all tied employees.\n'
            '\n'
            '**Output columns:** `department_name`, `employee_name`, `salary`\n'
            '\n'
            'Order by `department_name` ascending, then `employee_name` ascending.',
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
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample employees with distinct maximum salaries per dept',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, "
                          "'Sales');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Alice', 1, 90000),\n"
                          "                        (2, 'Bob', 1, 80000),\n"
                          "                        (3, 'Charlie', 2, 70000),\n"
                          "                        (4, 'David', 2, 65000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Tied highest salaries within the same department',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Design'), (2, "
                          "'Marketing');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Zoe', 1, 85000),\n"
                          "                        (2, 'Amy', 1, 85000),\n"
                          "                        (3, 'Brian', 1, 70000),\n"
                          "                        (4, 'Chloe', 2, 95000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single employee per department',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Support');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES (1, '
                          "'Solo', 1, 50000);\n"
                          '                '}]},
 {'id': 'sql_prob_015',
  'difficulty': 'medium',
  'prompt': '### Running Balance of Bank Accounts\n'
            '\n'
            'Write a query to calculate the cumulative running balance for each bank account over time.\n'
            '\n'
            '**Output columns:** `account_id`, `id`, `tx_date`, `amount`, `running_balance`\n'
            '\n'
            'Order by `account_id` ascending, `tx_date` ascending, and `id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE bank_transactions (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                account_id INTEGER NOT NULL,\n'
                '                tx_date TEXT NOT NULL,\n'
                '                amount REAL NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample transactions for two accounts',
             'seed_data': '\n'
                          '                    INSERT INTO bank_transactions (id, account_id, tx_date, amount) VALUES\n'
                          "                        (1, 100, '2026-01-01', 500.0),\n"
                          "                        (2, 100, '2026-01-02', -100.0),\n"
                          "                        (3, 100, '2026-01-03', 250.0),\n"
                          "                        (4, 200, '2026-01-01', 1000.0),\n"
                          "                        (5, 200, '2026-01-05', -400.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Multiple transactions on the same date with tie breaking by id',
             'seed_data': '\n'
                          '                    INSERT INTO bank_transactions (id, account_id, tx_date, amount) VALUES\n'
                          "                        (1, 1, '2026-02-01', 100.0),\n"
                          "                        (2, 1, '2026-02-01', 50.0),\n"
                          "                        (3, 1, '2026-02-01', -20.0),\n"
                          "                        (4, 2, '2026-02-01', 500.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Negative starting balances and fluctuating balances',
             'seed_data': '\n'
                          '                    INSERT INTO bank_transactions (id, account_id, tx_date, amount) VALUES\n'
                          "                        (1, 5, '2026-03-01', -50.0),\n"
                          "                        (2, 5, '2026-03-02', 100.0),\n"
                          "                        (3, 5, '2026-03-03', -100.0);\n"
                          '                '}]},
 {'id': 'sql_prob_016',
  'difficulty': 'medium',
  'prompt': '### Days Between Consecutive Customer Orders\n'
            '\n'
            "Write a query to calculate the number of days elapsed between each customer's consecutive orders. For a "
            "customer's first order, `days_since_prev` should be NULL.\n"
            '\n'
            '**Output columns:** `customer_id`, `id`, `order_date`, `days_since_prev`\n'
            '\n'
            'Order by `customer_id` ascending, `order_date` ascending, and `id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE customer_orders (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                customer_id INTEGER NOT NULL,\n'
                '                order_date TEXT NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample orders with multi-day intervals',
             'seed_data': '\n'
                          '                    INSERT INTO customer_orders (id, customer_id, order_date) VALUES\n'
                          "                        (1, 10, '2026-01-01'),\n"
                          "                        (2, 10, '2026-01-05'),\n"
                          "                        (3, 10, '2026-01-15'),\n"
                          "                        (4, 20, '2026-02-01');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Orders on consecutive days and same customer multiple orders',
             'seed_data': '\n'
                          '                    INSERT INTO customer_orders (id, customer_id, order_date) VALUES\n'
                          "                        (1, 1, '2026-03-01'),\n"
                          "                        (2, 1, '2026-03-02'),\n"
                          "                        (3, 1, '2026-03-10'),\n"
                          "                        (4, 2, '2026-03-05'),\n"
                          "                        (5, 2, '2026-03-25');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'All customers have only one order (all NULL days_since_prev)',
             'seed_data': '\n'
                          '                    INSERT INTO customer_orders (id, customer_id, order_date) VALUES\n'
                          "                        (1, 100, '2026-04-01'),\n"
                          "                        (2, 200, '2026-04-02');\n"
                          '                '}]},
 {'id': 'sql_prob_017',
  'difficulty': 'medium',
  'prompt': '### Above Average Category Products\n'
            '\n'
            'Write a query to find products whose price is strictly greater than the average price of all products '
            'within their category.\n'
            '\n'
            '**Output columns:** `name`, `category_id`, `price`\n'
            '\n'
            'Order by `category_id` ascending, then `price` descending, then `name` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE products (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                name TEXT NOT NULL,\n'
                '                category_id INTEGER NOT NULL,\n'
                '                price REAL NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample products across two categories',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                          "                        (1, 'Laptop', 1, 1200.0),\n"
                          "                        (2, 'Keyboard', 1, 80.0),\n"
                          "                        (3, 'Mouse', 1, 40.0),\n"
                          "                        (4, 'Desk', 2, 350.0),\n"
                          "                        (5, 'Chair', 2, 150.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Categories where all products have identical prices (no above average)',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                          "                        (1, 'Apple', 10, 2.0),\n"
                          "                        (2, 'Banana', 10, 2.0),\n"
                          "                        (3, 'Carrot', 20, 5.0),\n"
                          "                        (4, 'Dill', 20, 10.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Multiple categories with tie breaks',
             'seed_data': '\n'
                          '                    INSERT INTO products (id, name, category_id, price) VALUES\n'
                          "                        (1, 'Pro A', 100, 50.0),\n"
                          "                        (2, 'Pro B', 100, 50.0),\n"
                          "                        (3, 'Basic', 100, 20.0);\n"
                          '                '}]},
 {'id': 'sql_prob_018',
  'difficulty': 'medium',
  'prompt': '### Inactive User Detection\n'
            '\n'
            "Write a query to find all users who have had zero activity after '2025-06-01' (including users who have "
            'never logged any activity at all).\n'
            '\n'
            '**Output columns:** `username`, `created_at`\n'
            '\n'
            'Order by `username` ascending.',
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
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample users with active and inactive timelines',
             'seed_data': '\n'
                          '                    INSERT INTO users (id, username, created_at) VALUES\n'
                          "                        (1, 'alice', '2025-01-01'),\n"
                          "                        (2, 'bob', '2025-02-01'),\n"
                          "                        (3, 'charlie', '2025-03-01');\n"
                          '                    INSERT INTO activity_logs (id, user_id, activity_date) VALUES\n'
                          "                        (1, 1, '2025-05-15'),\n"
                          "                        (2, 2, '2025-07-20');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': "Boundary date exactly '2025-06-01' and users with zero logs",
             'seed_data': '\n'
                          '                    INSERT INTO users (id, username, created_at) VALUES\n'
                          "                        (1, 'david', '2025-01-10'),\n"
                          "                        (2, 'emma', '2025-02-15'),\n"
                          "                        (3, 'frank', '2025-03-20');\n"
                          '                    INSERT INTO activity_logs (id, user_id, activity_date) VALUES\n'
                          "                        (1, 1, '2025-06-01'),\n"
                          "                        (2, 2, '2025-06-02');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'All users active after the threshold date',
             'seed_data': '\n'
                          '                    INSERT INTO users (id, username, created_at) VALUES\n'
                          "                        (1, 'grace', '2025-04-01'),\n"
                          "                        (2, 'hank', '2025-04-01');\n"
                          '                    INSERT INTO activity_logs (id, user_id, activity_date) VALUES\n'
                          "                        (1, 1, '2025-08-01'),\n"
                          "                        (2, 2, '2025-09-01');\n"
                          '                '}]},
 {'id': 'sql_prob_019',
  'difficulty': 'medium',
  'prompt': '### Managers Earning Less Than Subordinates\n'
            '\n'
            'Write a query to identify all managers who earn strictly less salary than at least one of their direct '
            'subordinates.\n'
            '\n'
            '**Output columns:** `manager_id`, `manager_name`, `manager_salary`\n'
            '\n'
            'Return distinct managers ordered by `manager_id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE employees (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                name TEXT NOT NULL,\n'
                '                salary REAL NOT NULL,\n'
                '                manager_id INTEGER\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT DISTINCT m.id AS manager_id, m.name AS manager_name, m.salary AS '
                     'manager_salary\n'
                     '            FROM employees m\n'
                     '            JOIN employees e ON m.id = e.manager_id\n'
                     '            WHERE m.salary < e.salary\n'
                     '            ORDER BY manager_id ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample manager hierarchy with salary disparities',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, salary, manager_id) VALUES\n'
                          "                        (1, 'Boss', 70000, NULL),\n"
                          "                        (2, 'Lead Dev', 80000, 1),\n"
                          "                        (3, 'Junior Dev', 50000, 2),\n"
                          "                        (4, 'Senior Dev', 90000, 2);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Equal salaries (should not qualify as strictly less)',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, salary, manager_id) VALUES\n'
                          "                        (10, 'Director', 100000, NULL),\n"
                          "                        (20, 'Manager A', 100000, 10),\n"
                          "                        (30, 'Staff', 95000, 20);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Multiple subordinate violations per manager',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, salary, manager_id) VALUES\n'
                          "                        (1, 'Lead', 60000, NULL),\n"
                          "                        (2, 'Sub1', 65000, 1),\n"
                          "                        (3, 'Sub2', 75000, 1),\n"
                          "                        (4, 'Sub3', 85000, 1);\n"
                          '                '}]},
 {'id': 'sql_prob_020',
  'difficulty': 'medium',
  'prompt': '### Cumulative Percentage of Product Sales\n'
            '\n'
            "Write a query to calculate each product's units sold and the cumulative percentage of overall company "
            'sales (rounded to 2 decimal places, e.g. 50.00 for 50%).\n'
            '\n'
            '**Output columns:** `product_name`, `units_sold`, `cumulative_pct`\n'
            '\n'
            'Order by `units_sold` descending, then `product_name` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE sales (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                product_name TEXT NOT NULL,\n'
                '                units_sold INTEGER NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample sales data summing to 100 units',
             'seed_data': '\n'
                          '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                          "                        (1, 'Phone', 50),\n"
                          "                        (2, 'Laptop', 30),\n"
                          "                        (3, 'Tablet', 20);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Arbitrary total units with decimal precision rounding',
             'seed_data': '\n'
                          '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                          "                        (1, 'Alpha', 33),\n"
                          "                        (2, 'Beta', 33),\n"
                          "                        (3, 'Gamma', 34);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single product in table',
             'seed_data': '\n'
                          '                    INSERT INTO sales (id, product_name, units_sold) VALUES\n'
                          "                        (1, 'OnlyOne', 42);\n"
                          '                '}]},
 {'id': 'sql_prob_021',
  'difficulty': 'hard',
  'prompt': '### Longest Consecutive Active Day Streak\n'
            '\n'
            'Write a query using islands-and-gaps technique to calculate the length of the longest consecutive active '
            'days streak for each user.\n'
            '\n'
            '**Output columns:** `user_id`, `max_streak_days`\n'
            '\n'
            'Order by `max_streak_days` descending, then `user_id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE user_activity (\n'
                '                user_id INTEGER NOT NULL,\n'
                '                activity_date TEXT NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single day activity for all users (all streak 1)',
             'seed_data': '\n'
                          '                    INSERT INTO user_activity (user_id, activity_date) VALUES\n'
                          "                        (100, '2026-03-01'),\n"
                          "                        (200, '2026-03-05');\n"
                          '                '}]},
 {'id': 'sql_prob_022',
  'difficulty': 'hard',
  'prompt': '### Recursive Organization Hierarchy Depth\n'
            '\n'
            'Write a recursive query using `WITH RECURSIVE` to determine the reporting level of each employee in the '
            'company hierarchy. The top executive (whose `manager_id` is NULL) is at level 1, direct reports to level '
            '1 are at level 2, and so on.\n'
            '\n'
            '**Output columns:** `id`, `name`, `level`\n'
            '\n'
            'Order by `level` ascending, then `id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE employees (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                name TEXT NOT NULL,\n'
                '                manager_id INTEGER\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample 3-tier company org hierarchy',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                          "                        (1, 'CEO Alice', NULL),\n"
                          "                        (2, 'VP Bob', 1),\n"
                          "                        (3, 'VP Charlie', 1),\n"
                          "                        (4, 'Engineer Dave', 2);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Deep 5-level hierarchy chain',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                          "                        (10, 'Level1', NULL),\n"
                          "                        (20, 'Level2', 10),\n"
                          "                        (30, 'Level3', 20),\n"
                          "                        (40, 'Level4', 30),\n"
                          "                        (50, 'Level5', 40);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Multiple branches at each level',
             'seed_data': '\n'
                          '                    INSERT INTO employees (id, name, manager_id) VALUES\n'
                          "                        (1, 'Boss', NULL),\n"
                          "                        (2, 'M1', 1),\n"
                          "                        (3, 'M2', 1),\n"
                          "                        (4, 'W1', 2),\n"
                          "                        (5, 'W2', 2),\n"
                          "                        (6, 'W3', 3);\n"
                          '                '}]},
 {'id': 'sql_prob_023',
  'difficulty': 'hard',
  'prompt': '### Median Order Amount per Region\n'
            '\n'
            'Write a query to calculate the median order `amount` for each region (rounded to 2 decimal places). If a '
            'region has an even count of orders, the median is the average of the two middle values.\n'
            '\n'
            '**Output columns:** `region`, `median_amount`\n'
            '\n'
            'Order by `region` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE orders (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                region TEXT NOT NULL,\n'
                '                amount REAL NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            WITH ranked AS (\n'
                     '                SELECT\n'
                     '                    region,\n'
                     '                    amount,\n'
                     '                    ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount ASC, id ASC) AS '
                     'rnk_asc,\n'
                     '                    ROW_NUMBER() OVER (PARTITION BY region ORDER BY amount DESC, id DESC) AS '
                     'rnk_desc\n'
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Tied values in middle positions',
             'seed_data': '\n'
                          '                    INSERT INTO orders (id, region, amount) VALUES\n'
                          "                        (1, 'East', 50.0),\n"
                          "                        (2, 'East', 50.0),\n"
                          "                        (3, 'East', 50.0),\n"
                          "                        (4, 'East', 50.0),\n"
                          "                        (5, 'West', 15.5),\n"
                          "                        (6, 'West', 25.5);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single order per region',
             'seed_data': '\n'
                          '                    INSERT INTO orders (id, region, amount) VALUES\n'
                          "                        (1, 'Central', 99.99);\n"
                          '                '}]},
 {'id': 'sql_prob_024',
  'difficulty': 'hard',
  'prompt': '### Monthly User Cohort Retention\n'
            '\n'
            'Write a query to perform cohort retention analysis. For each user `signup_month` (formatted `YYYY-MM`), '
            'report the total cohort size (`cohort_size`), and the number of users who had at least one activity event '
            'in Month 0 (`m0_active`), Month 1 (`m1_active`), and Month 2 (`m2_active`) relative to their signup '
            'month.\n'
            '\n'
            '**Output columns:** `signup_month`, `cohort_size`, `m0_active`, `m1_active`, `m2_active`\n'
            '\n'
            'Order by `signup_month` ascending.',
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
                '        ',
  'reference_query': '\n'
                     '            WITH user_activity_offsets AS (\n'
                     '                SELECT\n'
                     '                    u.signup_month,\n'
                     '                    u.id AS user_id,\n'
                     '                    MAX(CASE WHEN e.event_month = u.signup_month THEN 1 ELSE 0 END) AS in_m0,\n'
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
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
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Empty events table (all retention 0)',
             'seed_data': '\n'
                          '                    INSERT INTO users (id, signup_month) VALUES\n'
                          "                        (1, '2026-05');\n"
                          '                '}]},
 {'id': 'sql_prob_025',
  'difficulty': 'hard',
  'prompt': '### Overlapping Room Reservations\n'
            '\n'
            'Write a query to identify all pairs of conflicting/overlapping reservations for the same room. Two '
            'reservations A and B for the same room conflict if `A.start_time < B.end_time` and `B.start_time < '
            'A.end_time`. To eliminate duplicates and self-joins, report pairs where `A.id < B.id`.\n'
            '\n'
            '**Output columns:** `room_id`, `res1_id`, `res2_id`\n'
            '\n'
            'Order by `room_id` ascending, `res1_id` ascending, then `res2_id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE reservations (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                room_id INTEGER NOT NULL,\n'
                '                start_time TEXT NOT NULL,\n'
                '                end_time TEXT NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample overlapping and adjacent room reservations',
             'seed_data': '\n'
                          '                    INSERT INTO reservations (id, room_id, start_time, end_time) VALUES\n'
                          "                        (1, 101, '2026-01-10 09:00', '2026-01-10 11:00'),\n"
                          "                        (2, 101, '2026-01-10 10:30', '2026-01-10 12:00'),\n"
                          "                        (3, 101, '2026-01-10 13:00', '2026-01-10 14:00'),\n"
                          "                        (4, 102, '2026-01-10 09:00', '2026-01-10 10:00');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Touching boundary times (start == end is not an overlap)',
             'seed_data': '\n'
                          '                    INSERT INTO reservations (id, room_id, start_time, end_time) VALUES\n'
                          "                        (1, 1, '2026-02-01 08:00', '2026-02-01 09:00'),\n"
                          "                        (2, 1, '2026-02-01 09:00', '2026-02-01 10:00'),\n"
                          "                        (3, 1, '2026-02-01 08:30', '2026-02-01 09:30');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Multiple overlapping reservations across distinct rooms',
             'seed_data': '\n'
                          '                    INSERT INTO reservations (id, room_id, start_time, end_time) VALUES\n'
                          "                        (10, 5, '2026-03-01 10:00', '2026-03-01 12:00'),\n"
                          "                        (11, 5, '2026-03-01 11:00', '2026-03-01 13:00'),\n"
                          "                        (12, 6, '2026-03-01 10:00', '2026-03-01 12:00'),\n"
                          "                        (13, 6, '2026-03-01 10:30', '2026-03-01 11:30');\n"
                          '                '}]},
 {'id': 'sql_prob_026',
  'difficulty': 'hard',
  'prompt': '### Top Two Salary Ranks per Department\n'
            '\n'
            'Write a query using `DENSE_RANK()` to find the employees in the top 2 highest salary tiers for each '
            'department. Include all employees tied for rank 1 or rank 2.\n'
            '\n'
            '**Output columns:** `department_name`, `employee_name`, `salary`, `salary_rank`\n'
            '\n'
            'Order by `department_name` ascending, `salary_rank` ascending, `salary` descending, and `employee_name` '
            'ascending.',
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
                '        ',
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
                     '            ORDER BY department_name ASC, salary_rank ASC, salary DESC, employee_name ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample employees with salary ties in rank 1 and 2',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, "
                          "'Marketing');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Alice', 1, 100000),\n"
                          "                        (2, 'Bob', 1, 100000),\n"
                          "                        (3, 'Charlie', 1, 90000),\n"
                          "                        (4, 'David', 1, 80000),\n"
                          "                        (5, 'Eve', 2, 70000),\n"
                          "                        (6, 'Frank', 2, 65000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Ties for second rank',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Finance');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES\n'
                          "                        (1, 'Gary', 1, 120000),\n"
                          "                        (2, 'Helen', 1, 110000),\n"
                          "                        (3, 'Ian', 1, 110000),\n"
                          "                        (4, 'Jack', 1, 90000);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Departments with only 1 employee',
             'seed_data': '\n'
                          "                    INSERT INTO departments (id, name) VALUES (1, 'Legal');\n"
                          '                    INSERT INTO employees (id, name, department_id, salary) VALUES (1, '
                          "'Solo', 1, 80000);\n"
                          '                '}]},
 {'id': 'sql_prob_027',
  'difficulty': 'hard',
  'prompt': '### User Clickstream Sessionization\n'
            '\n'
            'Write a query to group user clicks into sessions. A new session begins if strictly more than 1800 seconds '
            "(30 minutes) have elapsed since the user's previous click. For each user session, return the user ID, "
            'session start time (`session_start`), and total count of clicks in that session (`click_count`).\n'
            '\n'
            '**Output columns:** `user_id`, `session_start`, `click_count`\n'
            '\n'
            'Order by `user_id` ascending, then `session_start` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE clicks (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                user_id INTEGER NOT NULL,\n'
                '                click_time TEXT NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            WITH click_diffs AS (\n'
                     '                SELECT\n'
                     '                    user_id,\n'
                     '                    click_time,\n'
                     '                    CASE\n'
                     '                        WHEN (julianday(click_time) - julianday(\n'
                     '                            LAG(click_time) OVER (PARTITION BY user_id ORDER BY click_time ASC, '
                     'id ASC)\n'
                     '                        )) * 86400 > 1800\n'
                     '                        OR LAG(click_time) OVER (PARTITION BY user_id ORDER BY click_time ASC, '
                     'id ASC) IS NULL\n'
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample clicks with gaps below and above 30 minutes',
             'seed_data': '\n'
                          '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                          "                        (1, 1, '2026-01-01 10:00:00'),\n"
                          "                        (2, 1, '2026-01-01 10:15:00'),\n"
                          "                        (3, 1, '2026-01-01 11:00:00'),\n"
                          "                        (4, 2, '2026-01-01 12:00:00');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Boundary exactly at 1800 seconds and multi-click sessions',
             'seed_data': '\n'
                          '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                          "                        (1, 10, '2026-02-01 08:00:00'),\n"
                          "                        (2, 10, '2026-02-01 08:30:00'),\n"
                          "                        (3, 10, '2026-02-01 09:00:01'),\n"
                          "                        (4, 20, '2026-02-01 09:00:00'),\n"
                          "                        (5, 20, '2026-02-01 09:05:00'),\n"
                          "                        (6, 20, '2026-02-01 09:10:00');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Single click per user',
             'seed_data': '\n'
                          '                    INSERT INTO clicks (id, user_id, click_time) VALUES\n'
                          "                        (1, 100, '2026-03-01 10:00:00'),\n"
                          "                        (2, 200, '2026-03-01 11:00:00');\n"
                          '                '}]},
 {'id': 'sql_prob_028',
  'difficulty': 'hard',
  'prompt': '### Market Basket Analysis: Co-Purchased Item Pairs\n'
            '\n'
            'Write a query to perform market basket analysis. Find all distinct pairs of items (`item_a`, `item_b` '
            'where `item_a < item_b`) that were purchased together in the same order at least 2 times.\n'
            '\n'
            '**Output columns:** `item_a`, `item_b`, `co_purchase_count`\n'
            '\n'
            'Order by `co_purchase_count` descending, `item_a` ascending, and `item_b` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE order_items (\n'
                '                order_id INTEGER NOT NULL,\n'
                '                item_name TEXT NOT NULL\n'
                '            );\n'
                '        ',
  'reference_query': '\n'
                     '            SELECT\n'
                     '                i1.item_name AS item_a,\n'
                     '                i2.item_name AS item_b,\n'
                     '                COUNT(*) AS co_purchase_count\n'
                     '            FROM order_items i1\n'
                     '            JOIN order_items i2 ON i1.order_id = i2.order_id AND i1.item_name < i2.item_name\n'
                     '            GROUP BY item_a, item_b\n'
                     '            HAVING COUNT(*) >= 2\n'
                     '            ORDER BY co_purchase_count DESC, item_a ASC, item_b ASC;\n'
                     '        ',
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample orders with overlapping items',
             'seed_data': '\n'
                          '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                          "                        (1, 'Bread'), (1, 'Butter'), (1, 'Milk'),\n"
                          "                        (2, 'Bread'), (2, 'Butter'),\n"
                          "                        (3, 'Bread'), (3, 'Jam');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Multiple items with higher co-purchase counts and ties',
             'seed_data': '\n'
                          '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                          "                        (10, 'Coffee'), (10, 'Sugar'), (10, 'Cream'),\n"
                          "                        (20, 'Coffee'), (20, 'Sugar'), (20, 'Cream'),\n"
                          "                        (30, 'Coffee'), (30, 'Sugar'),\n"
                          "                        (40, 'Tea'),    (40, 'Honey');\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'No item pairs meeting threshold of 2',
             'seed_data': '\n'
                          '                    INSERT INTO order_items (order_id, item_name) VALUES\n'
                          "                        (1, 'Pencil'), (1, 'Eraser'),\n"
                          "                        (2, 'Pen'), (2, 'Paper');\n"
                          '                '}]},
 {'id': 'sql_prob_029',
  'difficulty': 'hard',
  'prompt': '### Inventory Stockout Date Simulation\n'
            '\n'
            'Write a query to calculate cumulative running inventory for each item based on inventory change events. '
            'Identify the earliest event date on which each item experienced a stockout (cumulative stock fell '
            'strictly below zero). For each such item, report the item ID, the stockout event date (`stockout_date`), '
            'and the stock level at that moment (`stockout_level`).\n'
            '\n'
            '**Output columns:** `item_id`, `stockout_date`, `stockout_level`\n'
            '\n'
            'Order by `item_id` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE stock_events (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                item_id INTEGER NOT NULL,\n'
                '                event_date TEXT NOT NULL,\n'
                '                change_qty INTEGER NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample stock changes with one item going below zero',
             'seed_data': '\n'
                          '                    INSERT INTO stock_events (id, item_id, event_date, change_qty) VALUES\n'
                          "                        (1, 101, '2026-01-01', 10),\n"
                          "                        (2, 101, '2026-01-05', -15),\n"
                          "                        (3, 101, '2026-01-10', 20),\n"
                          "                        (4, 102, '2026-01-01', 50),\n"
                          "                        (5, 102, '2026-01-02', -10);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Items recovering from negative and dipping multiple times',
             'seed_data': '\n'
                          '                    INSERT INTO stock_events (id, item_id, event_date, change_qty) VALUES\n'
                          "                        (1, 1, '2026-02-01', 5),\n"
                          "                        (2, 1, '2026-02-02', -8),\n"
                          "                        (3, 1, '2026-02-03', 10),\n"
                          "                        (4, 1, '2026-02-04', -20),\n"
                          "                        (5, 2, '2026-02-01', -1);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Stock reaching exactly 0 (not a stockout)',
             'seed_data': '\n'
                          '                    INSERT INTO stock_events (id, item_id, event_date, change_qty) VALUES\n'
                          "                        (1, 50, '2026-03-01', 10),\n"
                          "                        (2, 50, '2026-03-02', -10);\n"
                          '                '}]},
 {'id': 'sql_prob_030',
  'difficulty': 'hard',
  'prompt': '### Quarterly Category Sales Pivot\n'
            '\n'
            'Write a query to pivot quarterly revenue by category into separate columns for `Q1`, `Q2`, `Q3`, and '
            '`Q4`, along with the `total_revenue` across the year.\n'
            '\n'
            '**Output columns:** `category`, `q1_revenue`, `q2_revenue`, `q3_revenue`, `q4_revenue`, `total_revenue`\n'
            '\n'
            'Order by `total_revenue` descending, then `category` ascending.',
  'schema_ddl': '\n'
                '            CREATE TABLE category_sales (\n'
                '                id INTEGER PRIMARY KEY,\n'
                '                category TEXT NOT NULL,\n'
                '                sale_quarter TEXT NOT NULL,\n'
                '                revenue REAL NOT NULL\n'
                '            );\n'
                '        ',
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
  'checks_json': {'order_matters': True, 'forbidden_constructs': []},
  'cases': [{'case_type': 'visible_sample',
             'sort_order': 0,
             'description': 'Sample sales data across all four quarters',
             'seed_data': '\n'
                          '                    INSERT INTO category_sales (id, category, sale_quarter, revenue) '
                          'VALUES\n'
                          "                        (1, 'Electronics', 'Q1', 100.0),\n"
                          "                        (2, 'Electronics', 'Q2', 150.0),\n"
                          "                        (3, 'Electronics', 'Q3', 200.0),\n"
                          "                        (4, 'Electronics', 'Q4', 250.0),\n"
                          "                        (5, 'Clothing', 'Q1', 50.0),\n"
                          "                        (6, 'Clothing', 'Q2', 75.0);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 1,
             'description': 'Categories missing multiple quarters and decimals',
             'seed_data': '\n'
                          '                    INSERT INTO category_sales (id, category, sale_quarter, revenue) '
                          'VALUES\n'
                          "                        (1, 'Books', 'Q3', 45.50),\n"
                          "                        (2, 'Books', 'Q4', 54.50),\n"
                          "                        (3, 'Furniture', 'Q1', 300.25),\n"
                          "                        (4, 'Furniture', 'Q4', 199.75);\n"
                          '                '},
            {'case_type': 'hidden_case',
             'sort_order': 2,
             'description': 'Tied total revenue verifying category tie break',
             'seed_data': '\n'
                          '                    INSERT INTO category_sales (id, category, sale_quarter, revenue) '
                          'VALUES\n'
                          "                        (1, 'Zeta', 'Q1', 100.0),\n"
                          "                        (2, 'Alpha', 'Q2', 100.0);\n"
                          '                '}]}]

def seed_phase2_content_bank(session: Session) -> None:
    """Idempotently seed all 150 MCQs and 30 SQL problems into the database."""
    # 1. Ensure core skills exist
    skill_names = {"DBMS", "Python", "OS", "Computer Networks", "DSA"}
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
