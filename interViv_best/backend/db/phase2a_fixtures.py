"""Phase 2A reviewed fixtures for MCQ and SQL problem engine validation.

Includes:
- 15 verified MCQs across 5 core skills (DBMS, Python, OS, Computer Networks, DSA).
  Each has exactly one defensible correct answer, no negative phrasing, and valid distractors.
- 2 verified SQL problems, each with 1 visible sample and 2 hidden evaluation cases.
"""

from __future__ import annotations

from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.sqlalchemy_models import MCQQuestionRow, SQLProblemRow, SQLProblemCaseRow, SkillRow


PHASE2A_MCQ_FIXTURES: list[dict[str, Any]] = [
    # --- DBMS (4 questions) ---
    {
        "id": "mcq_dbms_001",
        "skill": "DBMS",
        "sub_domain": "indexing",
        "difficulty": "easy",
        "stem": "What is the primary operational advantage of a B+ tree index over a hash index in relational databases?",
        "options_json": [
            {"id": "a", "text": "B+ trees execute exact-match lookups in strictly O(1) time complexity."},
            {"id": "b", "text": "B+ trees efficiently support range queries and ordered scans because leaf nodes are linked in sequential order."},
            {"id": "c", "text": "B+ trees require zero storage overhead on disk compared to the underlying table heap."},
            {"id": "d", "text": "B+ trees avoid hash collisions by eliminating disk read operations."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "B+ tree leaves form a doubly linked list, enabling efficient range scans and sorted traversals, unlike hash indexes which only support equality lookups.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_dbms_002",
        "skill": "DBMS",
        "sub_domain": "concurrency",
        "difficulty": "medium",
        "stem": "Under the ANSI SQL Read Committed isolation level, what concurrency phenomenon remains possible during concurrent transaction execution?",
        "options_json": [
            {"id": "a", "text": "Dirty read: a transaction reading uncommitted data written by a concurrent transaction."},
            {"id": "b", "text": "Non-repeatable read: re-reading the same row within a transaction returns values modified by a committed concurrent transaction."},
            {"id": "c", "text": "Write-write conflict on uncommitted rows that produces cascade aborts."},
            {"id": "d", "text": "Dirty write: concurrent uncommitted transactions overwriting each other's uncommitted rows."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "Read Committed prevents dirty reads by only reading committed rows, but allows non-repeatable reads since rows read earlier can be updated and committed by other transactions.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_dbms_003",
        "skill": "DBMS",
        "sub_domain": "normalization",
        "difficulty": "easy",
        "stem": "What condition must a relation satisfy to be in Third Normal Form (3NF)?",
        "options_json": [
            {"id": "a", "text": "It is in 2NF and every non-prime attribute is non-transitively dependent on every candidate key."},
            {"id": "b", "text": "It is in 1NF and all non-key columns depend on part of a composite primary key."},
            {"id": "c", "text": "Every functional dependency X -> Y has Y as a superkey of the relation."},
            {"id": "d", "text": "It eliminates multivalued dependencies across independent attribute sets."}
        ],
        "correct_option_ids": ["a"],
        "explanation": "3NF requires 2NF plus the elimination of transitive dependencies for non-prime attributes on candidate keys.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_dbms_004",
        "skill": "DBMS",
        "sub_domain": "transactions",
        "difficulty": "hard",
        "stem": "In write-ahead logging (WAL) using the ARIES recovery algorithm, which phase reconstructs the exact state of the buffer pool at the moment of system crash?",
        "options_json": [
            {"id": "a", "text": "The Undo phase, which rolls back all active transactions in reverse chronological order."},
            {"id": "b", "text": "The Analysis phase, which scans log records backward to locate the earliest checkpoint."},
            {"id": "c", "text": "The Redo phase, which repeats history starting from the smallest dirty page table RecLSN to restore the crash state."},
            {"id": "d", "text": "The Checkpoint phase, which flushes dirty pages synchronously during crash recovery."}
        ],
        "correct_option_ids": ["c"],
        "explanation": "ARIES Redo repeats history from the earliest dirty page RecLSN up to the crash point, restoring the exact state prior to crash before undoing uncommitted transactions.",
        "negative_marking": 0.25,
    },

    # --- Python (3 questions) ---
    {
        "id": "mcq_python_001",
        "skill": "Python",
        "sub_domain": "data_structures",
        "difficulty": "easy",
        "stem": "What is the key functional difference between a Python tuple and a Python list?",
        "options_json": [
            {"id": "a", "text": "Tuples support indexing while lists require key-value iteration."},
            {"id": "b", "text": "Tuples are immutable sequences whose elements cannot be added or replaced after creation, whereas lists are mutable."},
            {"id": "c", "text": "Lists can only hold primitive types while tuples can hold arbitrary objects."},
            {"id": "d", "text": "Tuples are always stored on disk while lists reside exclusively in heap memory."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "Tuples are immutable fixed-size sequences, whereas lists are mutable dynamic arrays.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_python_002",
        "skill": "Python",
        "sub_domain": "memory_management",
        "difficulty": "medium",
        "stem": "How does CPython primarily track object lifetimes to determine when an object can be freed immediately?",
        "options_json": [
            {"id": "a", "text": "Mark-and-sweep garbage collection running on a fixed periodic timer."},
            {"id": "b", "text": "Reference counting, where an object is deallocated as soon as its reference count drops to zero."},
            {"id": "c", "text": "Static compile-time memory analysis that assigns all objects to fixed stack frames."},
            {"id": "d", "text": "Generational mark-compact allocation without reference counters."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "CPython's primary memory management is reference counting; the generational cyclic GC only cleans up reference cycles.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_python_003",
        "skill": "Python",
        "sub_domain": "generators",
        "difficulty": "hard",
        "stem": "What occurs when execution reaches the 'yield' expression inside a Python generator function?",
        "options_json": [
            {"id": "a", "text": "The function terminates permanently and clears all local frame variables from memory."},
            {"id": "b", "text": "The current frame state and instruction pointer are suspended, yielding the value to the caller until __next__() is invoked."},
            {"id": "c", "text": "The function raises an unhandled StopIteration exception immediately."},
            {"id": "d", "text": "The function clones itself into a background OS thread to execute asynchronously."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "Yield produces a value and suspends execution, preserving the local frame state until the next item is requested.",
        "negative_marking": 0.25,
    },

    # --- Operating Systems (3 questions) ---
    {
        "id": "mcq_os_001",
        "skill": "OS",
        "sub_domain": "processes",
        "difficulty": "easy",
        "stem": "What is the primary distinction between a process and a thread in modern operating systems?",
        "options_json": [
            {"id": "a", "text": "Threads possess dedicated virtual memory spaces, while processes share the kernel page tables."},
            {"id": "b", "text": "Processes have independent virtual address spaces and resources, while threads of the same process share virtual address space and heap."},
            {"id": "c", "text": "Processes can only be executed sequentially on a single core, while threads automatically distribute across cluster nodes."},
            {"id": "d", "text": "Threads require hardware hypervisors to execute."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "Processes have independent virtual memory address spaces, while threads within a process share memory, open files, and address space.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_os_002",
        "skill": "OS",
        "sub_domain": "synchronization",
        "difficulty": "medium",
        "stem": "Which set of four conditions must hold simultaneously for a system deadlock to arise?",
        "options_json": [
            {"id": "a", "text": "Mutual exclusion, Hold and wait, No preemption, and Circular wait."},
            {"id": "b", "text": "Preemption, Starvation, Aging, and Context switching."},
            {"id": "c", "text": "Paging, Virtual memory, Busy waiting, and Race condition."},
            {"id": "d", "text": "Round-robin scheduling, Multitasking, Semaphore signaling, and Truncation."}
        ],
        "correct_option_ids": ["a"],
        "explanation": "Coffman's four conditions for deadlock are Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_os_003",
        "skill": "OS",
        "sub_domain": "virtual_memory",
        "difficulty": "hard",
        "stem": "In a demand-paged virtual memory system, what hardware exception is triggered when a process references a valid virtual address whose page is absent from physical RAM?",
        "options_json": [
            {"id": "a", "text": "General protection fault."},
            {"id": "b", "text": "Page fault, prompting the OS kernel page-fault handler to bring the required frame from disk."},
            {"id": "c", "text": "Segmentation violation (SIGSEGV) resulting in process abort."},
            {"id": "d", "text": "Translation Lookaside Buffer writeback interrupt."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "A page fault occurs when a program accesses a page mapped in address space but not currently loaded in physical memory.",
        "negative_marking": 0.25,
    },

    # --- Computer Networks (3 questions) ---
    {
        "id": "mcq_cn_001",
        "skill": "Computer Networks",
        "sub_domain": "transport",
        "difficulty": "easy",
        "stem": "What sequence of packets establishes a reliable connection in the standard TCP three-way handshake?",
        "options_json": [
            {"id": "a", "text": "SYN -> SYN-ACK -> ACK"},
            {"id": "b", "text": "ACK -> SYN -> ACK-SYN"},
            {"id": "c", "text": "FIN -> ACK -> FIN-ACK"},
            {"id": "d", "text": "RST -> SYN -> ACK"}
        ],
        "correct_option_ids": ["a"],
        "explanation": "TCP connection establishment starts with SYN from client, SYN-ACK from server, and ACK from client.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_cn_002",
        "skill": "Computer Networks",
        "sub_domain": "routing",
        "difficulty": "medium",
        "stem": "What mechanism does the IPv4 protocol use to prevent packets from looping endlessly across misconfigured routers?",
        "options_json": [
            {"id": "a", "text": "The Sequence Number field which rejects duplicated packets."},
            {"id": "b", "text": "The Time-to-Live (TTL) field, decremented at each router hop, causing packet drop when it reaches zero."},
            {"id": "c", "text": "Periodic ARP broadcast verification at each subnet boundary."},
            {"id": "d", "text": "TCP Selective Acknowledgment (SACK)."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "IPv4 TTL is decremented by 1 at each router; when TTL reaches 0, the packet is discarded and an ICMP Time Exceeded message is returned.",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_cn_003",
        "skill": "Computer Networks",
        "sub_domain": "congestion_control",
        "difficulty": "hard",
        "stem": "In TCP Reno congestion control, how does the sender respond upon receiving three duplicate ACKs for the same packet?",
        "options_json": [
            {"id": "a", "text": "It resets cwnd to 1 MSS and enters the initial Slow Start phase."},
            {"id": "b", "text": "It enters Fast Retransmit to immediately resend the missing segment, sets ssthresh to cwnd/2, and enters Fast Recovery."},
            {"id": "c", "text": "It terminates the TCP connection with a RST flag."},
            {"id": "d", "text": "It doubles cwnd exponentially assuming link capacity expanded."}
        ],
        "correct_option_ids": ["b"],
        "explanation": "Three duplicate ACKs trigger Fast Retransmit (resending the missing segment) and Fast Recovery (halving cwnd rather than resetting to 1).",
        "negative_marking": 0.25,
    },

    # --- DSA (2 questions) ---
    {
        "id": "mcq_dsa_001",
        "skill": "DSA",
        "sub_domain": "hashing",
        "difficulty": "easy",
        "stem": "What is the average-case time complexity of inserting a key into a hash table implemented with separate chaining?",
        "options_json": [
            {"id": "a", "text": "O(1)"},
            {"id": "b", "text": "O(log n)"},
            {"id": "c", "text": "O(n)"},
            {"id": "d", "text": "O(n log n)"}
        ],
        "correct_option_ids": ["a"],
        "explanation": "Assuming a uniform hash function and appropriate load factor, insertion into a hash table is average O(1).",
        "negative_marking": 0.25,
    },
    {
        "id": "mcq_dsa_002",
        "skill": "DSA",
        "sub_domain": "sorting",
        "difficulty": "medium",
        "stem": "Which sorting algorithm guarantees O(n log n) worst-case time complexity while requiring only O(1) auxiliary space?",
        "options_json": [
            {"id": "a", "text": "Merge Sort"},
            {"id": "b", "text": "Quick Sort"},
            {"id": "c", "text": "Heap Sort"},
            {"id": "d", "text": "Insertion Sort"}
        ],
        "correct_option_ids": ["c"],
        "explanation": "Heap Sort sorts in-place using O(1) auxiliary space and guarantees O(n log n) in all cases (best, average, worst).",
        "negative_marking": 0.25,
    },
]


PHASE2A_SQL_FIXTURES: list[dict[str, Any]] = [
    # --- SQL Problem 1: High Earners per Department ---
    {
        "id": "sql_hr_high_earners",
        "difficulty": "medium",
        "prompt": "Find the names and salaries of all employees who earn strictly more than the average salary of their respective department. Return 'name' and 'salary'. Order-insensitive.",
        "schema_ddl": """
            CREATE TABLE departments (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                salary REAL,
                department_id INTEGER,
                FOREIGN KEY (department_id) REFERENCES departments(id)
            );
        """,
        "reference_query": """
            SELECT e.name, e.salary
            FROM employees e
            JOIN (
                SELECT department_id, AVG(salary) AS avg_sal
                FROM employees
                WHERE department_id IS NOT NULL AND salary IS NOT NULL
                GROUP BY department_id
            ) d_avg ON e.department_id = d_avg.department_id
            WHERE e.salary > d_avg.avg_sal;
        """,
        "checks_json": {"order_matters": False, "require_column_names": False, "forbidden": []},
        "cases": [
            {
                "case_type": "visible_sample",
                "description": "Standard two department sample",
                "sort_order": 0,
                "seed_data": """
                    INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, 'Sales');
                    INSERT INTO employees (id, name, salary, department_id) VALUES
                        (1, 'Alice', 90000.0, 1),
                        (2, 'Bob', 70000.0, 1),
                        (3, 'Charlie', 50000.0, 2),
                        (4, 'Diana', 80000.0, 2);
                """,
            },
            {
                "case_type": "hidden_case",
                "description": "Edge case: NULL department and NULL salaries",
                "sort_order": 1,
                "seed_data": """
                    INSERT INTO departments (id, name) VALUES (1, 'Engineering'), (2, 'HR'), (3, 'Legal');
                    INSERT INTO employees (id, name, salary, department_id) VALUES
                        (1, 'Eve', 120000.0, 1),
                        (2, 'Frank', 60000.0, 1),
                        (3, 'Grace', NULL, 1),
                        (4, 'Heidi', 50000.0, NULL),
                        (5, 'Ivan', 70000.0, 2);
                """,
            },
            {
                "case_type": "hidden_case",
                "description": "Edge case: Equal salaries and multiple departments",
                "sort_order": 2,
                "seed_data": """
                    INSERT INTO departments (id, name) VALUES (1, 'Design'), (2, 'Marketing');
                    INSERT INTO employees (id, name, salary, department_id) VALUES
                        (1, 'Judy', 80000.0, 1),
                        (2, 'Mallory', 80000.0, 1),
                        (3, 'Niaj', 95000.0, 2),
                        (4, 'Oscar', 60000.0, 2),
                        (5, 'Peggy', 60000.0, 2);
                """,
            },
        ],
    },

    # --- SQL Problem 2: Customers with Significant Orders ---
    {
        "id": "sql_orders_aggregation",
        "difficulty": "easy",
        "prompt": "List the customer names and their total order amounts for customers who have placed at least one order and whose total order amount exceeds 100. Return 'customer_name' and 'total_spent'.",
        "schema_ddl": """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );
        """,
        "reference_query": """
            SELECT c.name, SUM(o.amount) AS total_spent
            FROM customers c
            JOIN orders o ON c.id = o.customer_id
            GROUP BY c.id, c.name
            HAVING SUM(o.amount) > 100.0;
        """,
        "checks_json": {"order_matters": False, "require_column_names": False, "forbidden": []},
        "cases": [
            {
                "case_type": "visible_sample",
                "description": "Sample orders with 3 customers",
                "sort_order": 0,
                "seed_data": """
                    INSERT INTO customers (id, name) VALUES (1, 'Alice'), (2, 'Bob'), (3, 'Carol');
                    INSERT INTO orders (id, customer_id, amount) VALUES
                        (1, 1, 60.0), (2, 1, 55.0),
                        (3, 2, 40.0),
                        (4, 3, 150.0);
                """,
            },
            {
                "case_type": "hidden_case",
                "description": "Edge case: Customer with exactly 100 total (boundary condition)",
                "sort_order": 1,
                "seed_data": """
                    INSERT INTO customers (id, name) VALUES (1, 'Dave'), (2, 'Erin');
                    INSERT INTO orders (id, customer_id, amount) VALUES
                        (1, 1, 100.0),
                        (2, 2, 100.01);
                """,
            },
            {
                "case_type": "hidden_case",
                "description": "Edge case: Customer with zero orders and multiple small orders",
                "sort_order": 2,
                "seed_data": """
                    INSERT INTO customers (id, name) VALUES (1, 'Frank'), (2, 'Grace'), (3, 'Heidi');
                    INSERT INTO orders (id, customer_id, amount) VALUES
                        (1, 1, 20.0), (2, 1, 30.0), (3, 1, 40.0), (4, 1, 15.0),
                        (5, 3, 250.0);
                """,
            },
        ],
    },
]


def seed_phase2a_fixtures(session: Session) -> None:
    """Idempotently seed Phase 2A MCQ and SQL problem fixtures."""
    # 1. Ensure skills exist
    skill_names = {"DBMS", "Python", "OS", "Computer Networks", "DSA"}
    existing_skills = {s.canonical_name: s.id for s in session.scalars(select(SkillRow)).all()}
    for name in skill_names:
        if name not in existing_skills:
            s_row = SkillRow(canonical_name=name, sub_domain="general")
            session.add(s_row)
            session.flush()
            existing_skills[name] = s_row.id

    # 2. Seed MCQs
    for fixture in PHASE2A_MCQ_FIXTURES:
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

    # 3. Seed SQL problems and cases
    for prob_fixture in PHASE2A_SQL_FIXTURES:
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
