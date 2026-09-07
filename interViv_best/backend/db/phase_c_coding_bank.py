"""Phase C coding bank: 15 original Python problems (6 easy, 6 medium, 3 hard).

Every problem carries 3 visible and 5 hidden tests, an original reference
solution passing all 8, and one plausible incorrect ("mutant") solution
that passes all 3 visible tests but fails at least one hidden test.
Statements, tests, and solutions below were authored originally for this
repository. See tests/test_coding_bank.py for the mechanical property
check (counts, reference-all-pass, mutant-visible-pass plus hidden-fail).
"""

from __future__ import annotations

from typing import Any


CODING_PROBLEMS: list[dict[str, Any]] = [
    {
        "id": "coding_two_sum",
        "title": "Two Sum",
        "difficulty": "easy",
        "topics": ["arrays", "hashing"],
        "statement": (
            "Given a list of integers nums and an integer target, return the "
            "indices [i, j] with i < j such that nums[i] + nums[j] == target. "
            "Exactly one solution exists."
        ),
        "constraints": [
            "2 <= len(nums) <= 10^4",
            "-10^9 <= nums[i], target <= 10^9",
            "Exactly one valid pair exists.",
        ],
        "function": "two_sum",
        "starter_code": (
            "def two_sum(nums, target):\n"
            '    """Return [i, j] with i < j and nums[i] + nums[j] == target."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[2, 7, 11, 15], 9]}, "expected": [0, 1]},
            {"input": {"args": [[1, 2, 3, 4], 7]}, "expected": [2, 3]},
            {"input": {"args": [[5, 1, 9, 3], 12]}, "expected": [2, 3]},
        ],
        "hidden_tests": [
            {"input": {"args": [[0, 4, 3, 0], 0]}, "expected": [0, 3]},
            {"input": {"args": [[-3, 4, 3, 90], 0]}, "expected": [0, 2]},
            {"input": {"args": [[3, 3], 6]}, "expected": [0, 1]},
            {"input": {"args": [[1, 2, 3, 4, 5], 9]}, "expected": [3, 4]},
            {"input": {"args": [[5, 75, 25], 100]}, "expected": [1, 2]},
        ],
        "reference_solution": (
            "def two_sum(nums, target):\n"
            "    seen = {}\n"
            "    for i, x in enumerate(nums):\n"
            "        need = target - x\n"
            "        if need in seen:\n"
            "            return [seen[need], i]\n"
            "        seen[x] = i\n"
            "    return []\n"
        ),
        "mutant_solution": (
            "def two_sum(nums, target):\n"
            "    for i, x in enumerate(nums):\n"
            "        need = target - x\n"
            "        j = nums.index(need) if need in nums else -1\n"
            "        if j != -1:\n"
            "            return [i, j]\n"
            "    return []\n"
        ),
    },
    {
        "id": "coding_valid_parentheses",
        "title": "Valid Parentheses",
        "difficulty": "easy",
        "topics": ["strings", "stack"],
        "statement": (
            "Given a string s containing only '(', ')', '{', '}', '[' and "
            "']', return True when every opener is closed by the matching "
            "closer in the correct nesting order."
        ),
        "constraints": [
            "1 <= len(s) <= 10^4",
            "s consists only of bracket characters.",
        ],
        "function": "is_valid",
        "starter_code": (
            "def is_valid(s):\n"
            '    """Return True when the brackets are correctly nested."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": ["()"]}, "expected": True},
            {"input": {"args": ["()[]{}"]}, "expected": True},
            {"input": {"args": ["(]"]}, "expected": False},
        ],
        "hidden_tests": [
            {"input": {"args": ["([)]"]}, "expected": False},
            {"input": {"args": ["{[]}"]}, "expected": True},
            {"input": {"args": ["((()))"]}, "expected": True},
            {"input": {"args": ["(("]}, "expected": False},
            {"input": {"args": ["]"]}, "expected": False},
        ],
        "reference_solution": (
            "def is_valid(s):\n"
            '    pairs = {")": "(", "]": "[", "}": "{"}\n'
            "    stack = []\n"
            "    for ch in s:\n"
            "        if ch in pairs.values():\n"
            "            stack.append(ch)\n"
            "        elif ch in pairs:\n"
            "            if not stack or stack.pop() != pairs[ch]:\n"
            "                return False\n"
            "        else:\n"
            "            return False\n"
            "    return not stack\n"
        ),
        "mutant_solution": (
            "def is_valid(s):\n"
            "    return (\n"
            '        s.count("(") == s.count(")")\n'
            '        and s.count("[") == s.count("]")\n'
            '        and s.count("{") == s.count("}")\n'
            "    )\n"
        ),
    },
    {
        "id": "coding_max_profit",
        "title": "Best Time to Buy and Sell",
        "difficulty": "easy",
        "topics": ["arrays", "greedy"],
        "statement": (
            "Given daily prices, return the maximum profit from one buy "
            "followed later by one sell. Return 0 when no profit is possible."
        ),
        "constraints": [
            "1 <= len(prices) <= 10^5",
            "0 <= prices[i] <= 10^4",
        ],
        "function": "max_profit",
        "starter_code": (
            "def max_profit(prices):\n"
            '    """Return the best single-transaction profit, or 0."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 5, 3, 6, 4]]}, "expected": 5},
            {"input": {"args": [[5, 5, 5]]}, "expected": 0},
            {"input": {"args": [[1, 2]]}, "expected": 1},
        ],
        "hidden_tests": [
            {"input": {"args": [[2, 4, 1]]}, "expected": 2},
            {"input": {"args": [[3, 2, 6, 1, 5]]}, "expected": 4},
            {"input": {"args": [[7, 6, 4, 3, 1]]}, "expected": 0},
            {"input": {"args": [[1, 2, 3, 4, 5]]}, "expected": 4},
            {"input": {"args": [[2, 1, 2, 0, 1]]}, "expected": 1},
        ],
        "reference_solution": (
            "def max_profit(prices):\n"
            "    best = 0\n"
            "    low = float('inf')\n"
            "    for p in prices:\n"
            "        if p < low:\n"
            "            low = p\n"
            "        elif p - low > best:\n"
            "            best = p - low\n"
            "    return best\n"
        ),
        "mutant_solution": (
            "def max_profit(prices):\n"
            "    if not prices:\n"
            "        return 0\n"
            "    return max(prices) - min(prices)\n"
        ),
    },
    {
        "id": "coding_is_palindrome",
        "title": "Alphanumeric Palindrome",
        "difficulty": "easy",
        "topics": ["strings"],
        "statement": (
            "Return True when the string reads the same forward and backward "
            "after keeping only letters and digits and ignoring case."
        ),
        "constraints": [
            "0 <= len(s) <= 10^5",
            "s holds printable ASCII characters.",
        ],
        "function": "is_palindrome",
        "starter_code": (
            "def is_palindrome(s):\n"
            '    """Return True for alphanumeric case-insensitive palindromes."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": ["racecar"]}, "expected": True},
            {"input": {"args": ["hello"]}, "expected": False},
            {"input": {"args": ["Madam"]}, "expected": True},
        ],
        "hidden_tests": [
            {"input": {"args": ["A man, a plan, a canal: Panama"]},
             "expected": True},
            {"input": {"args": ["No 'x' in Nixon"]}, "expected": True},
            {"input": {"args": ["12321"]}, "expected": True},
            {"input": {"args": ["ab"]}, "expected": False},
            {"input": {"args": [""]}, "expected": True},
        ],
        "reference_solution": (
            "def is_palindrome(s):\n"
            "    cleaned = ''.join(ch.lower() for ch in s if ch.isalnum())\n"
            "    return cleaned == cleaned[::-1]\n"
        ),
        "mutant_solution": (
            "def is_palindrome(s):\n"
            "    lowered = s.lower()\n"
            "    return lowered == lowered[::-1]\n"
        ),
    },
    {
        "id": "coding_missing_number",
        "title": "Missing Number",
        "difficulty": "easy",
        "topics": ["arrays", "math"],
        "statement": (
            "Given n distinct integers from the range 0..n, return the one "
            "number in the range that is missing."
        ),
        "constraints": [
            "1 <= len(nums) <= 10^4",
            "0 <= nums[i] <= len(nums)",
            "All values are distinct.",
        ],
        "function": "missing_number",
        "starter_code": (
            "def missing_number(nums):\n"
            '    """Return the missing value from 0..n."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[3, 0, 1]]}, "expected": 2},
            {"input": {"args": [[0, 2]]}, "expected": 1},
            {"input": {"args": [[1, 0, 3]]}, "expected": 2},
        ],
        "hidden_tests": [
            {"input": {"args": [[0, 1, 2]]}, "expected": 3},
            {"input": {"args": [[0]]}, "expected": 1},
            {"input": {"args": [[0, 1]]}, "expected": 2},
            {"input": {"args": [[9, 6, 4, 2, 3, 5, 7, 0, 1]]},
             "expected": 8},
            {"input": {"args": [[2, 0]]}, "expected": 1},
        ],
        "reference_solution": (
            "def missing_number(nums):\n"
            "    n = len(nums)\n"
            "    return n * (n + 1) // 2 - sum(nums)\n"
        ),
        "mutant_solution": (
            "def missing_number(nums):\n"
            "    m = max(nums)\n"
            "    return m * (m + 1) // 2 - sum(nums)\n"
        ),
    },
    {
        "id": "coding_dedup_order",
        "title": "Deduplicate Preserving Order",
        "difficulty": "easy",
        "topics": ["arrays", "hashing"],
        "statement": (
            "Return a new list with duplicate values removed, keeping the "
            "first occurrence of each value in its original position."
        ),
        "constraints": [
            "0 <= len(nums) <= 10^4",
            "-10^9 <= nums[i] <= 10^9",
        ],
        "function": "dedup",
        "starter_code": (
            "def dedup(nums):\n"
            '    """Return nums without duplicates, first-occurrence order."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 2, 2, 3]]}, "expected": [1, 2, 3]},
            {"input": {"args": [[1, 1, 1]]}, "expected": [1]},
            {"input": {"args": [[]]}, "expected": []},
        ],
        "hidden_tests": [
            {"input": {"args": [[3, 1, 3, 2, 1]]}, "expected": [3, 1, 2]},
            {"input": {"args": [[5, 4, 3]]}, "expected": [5, 4, 3]},
            {"input": {"args": [[2, 2, 1, 1, 3, 3]]}, "expected": [2, 1, 3]},
            {"input": {"args": [[1, 2, 3]]}, "expected": [1, 2, 3]},
            {"input": {"args": [[0, -1, 0, 2]]}, "expected": [0, -1, 2]},
        ],
        "reference_solution": (
            "def dedup(nums):\n"
            "    seen = set()\n"
            "    out = []\n"
            "    for x in nums:\n"
            "        if x not in seen:\n"
            "            seen.add(x)\n"
            "            out.append(x)\n"
            "    return out\n"
        ),
        "mutant_solution": (
            "def dedup(nums):\n"
            "    return sorted(set(nums))\n"
        ),
    },
    {
        "id": "coding_longest_substring",
        "title": "Longest Substring Without Repeats",
        "difficulty": "medium",
        "topics": ["strings", "sliding-window", "hashing"],
        "statement": (
            "Given a string s, return the length of the longest substring "
            "without repeating characters."
        ),
        "constraints": [
            "0 <= len(s) <= 10^4",
            "s holds printable ASCII characters.",
        ],
        "function": "length_of_longest_substring",
        "starter_code": (
            "def length_of_longest_substring(s):\n"
            '    """Return the longest repeat-free substring length."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": ["abcabcbb"]}, "expected": 3},
            {"input": {"args": ["bbbbb"]}, "expected": 1},
            {"input": {"args": ["pwwkew"]}, "expected": 3},
        ],
        "hidden_tests": [
            {"input": {"args": ["abba"]}, "expected": 2},
            {"input": {"args": [""]}, "expected": 0},
            {"input": {"args": ["abcdef"]}, "expected": 6},
            {"input": {"args": ["tmmzuxt"]}, "expected": 5},
            {"input": {"args": ["dvdf"]}, "expected": 3},
        ],
        "reference_solution": (
            "def length_of_longest_substring(s):\n"
            "    last = {}\n"
            "    left = 0\n"
            "    best = 0\n"
            "    for right, ch in enumerate(s):\n"
            "        if ch in last:\n"
            "            left = max(left, last[ch] + 1)\n"
            "        last[ch] = right\n"
            "        best = max(best, right - left + 1)\n"
            "    return best\n"
        ),
        "mutant_solution": (
            "def length_of_longest_substring(s):\n"
            "    last = {}\n"
            "    left = 0\n"
            "    best = 0\n"
            "    for right, ch in enumerate(s):\n"
            "        if ch in last:\n"
            "            left = last[ch] + 1\n"
            "        last[ch] = right\n"
            "        best = max(best, right - left + 1)\n"
            "    return best\n"
        ),
    },
    {
        "id": "coding_product_except_self",
        "title": "Product of Array Except Self",
        "difficulty": "medium",
        "topics": ["arrays"],
        "statement": (
            "Given a list nums, return a list where each entry i holds the "
            "product of every element except nums[i]. Do not use division."
        ),
        "constraints": [
            "1 <= len(nums) <= 10^4",
            "-30 <= nums[i] <= 30",
        ],
        "function": "product_except_self",
        "starter_code": (
            "def product_except_self(nums):\n"
            '    """Return products of all elements except self."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 2, 3, 4]]}, "expected": [24, 12, 8, 6]},
            {"input": {"args": [[2, 3, 4, 5]]}, "expected": [60, 40, 30, 24]},
            {"input": {"args": [[-1, 2, -3, 4]]},
             "expected": [-24, 12, -8, 6]},
        ],
        "hidden_tests": [
            {"input": {"args": [[0, 1, 2, 3]]}, "expected": [6, 0, 0, 0]},
            {"input": {"args": [[1, 0]]}, "expected": [0, 1]},
            {"input": {"args": [[0, 0, 3]]}, "expected": [0, 0, 0]},
            {"input": {"args": [[5]]}, "expected": [1]},
            {"input": {"args": [[2, 2, 2]]}, "expected": [4, 4, 4]},
        ],
        "reference_solution": (
            "def product_except_self(nums):\n"
            "    n = len(nums)\n"
            "    out = [1] * n\n"
            "    prefix = 1\n"
            "    for i in range(n):\n"
            "        out[i] = prefix\n"
            "        prefix *= nums[i]\n"
            "    suffix = 1\n"
            "    for i in range(n - 1, -1, -1):\n"
            "        out[i] *= suffix\n"
            "        suffix *= nums[i]\n"
            "    return out\n"
        ),
        "mutant_solution": (
            "def product_except_self(nums):\n"
            "    total = 1\n"
            "    for x in nums:\n"
            "        total *= x\n"
            "    return [total // x for x in nums]\n"
        ),
    },
    {
        "id": "coding_trapping_rain_water",
        "title": "Trapping Rain Water",
        "difficulty": "medium",
        "topics": ["arrays", "two-pointers"],
        "statement": (
            "Given bar heights, compute how much rain water is trapped after "
            "raining. Each bar has width 1."
        ),
        "constraints": [
            "0 <= len(height) <= 10^4",
            "0 <= height[i] <= 10^4",
        ],
        "function": "trap",
        "starter_code": (
            "def trap(height):\n"
            '    """Return the total trapped rain water."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[0, 1, 0, 2, 1, 0, 1, 3]]}, "expected": 5},
            {"input": {"args": [[4, 2, 0, 3, 2, 5]]}, "expected": 9},
            {"input": {"args": [[1, 0, 1]]}, "expected": 1},
        ],
        "hidden_tests": [
            {"input": {"args": [[3, 0, 2, 0, 4]]}, "expected": 7},
            {"input": {"args": [[5, 4, 1, 2]]}, "expected": 1},
            {"input": {"args": [[2, 0, 2, 0, 1]]}, "expected": 3},
            {"input": {"args": [[1, 0, 2]]}, "expected": 1},
            {"input": {"args": [[3, 2, 1]]}, "expected": 0},
        ],
        "reference_solution": (
            "def trap(height):\n"
            "    left, right = 0, len(height) - 1\n"
            "    left_max = right_max = 0\n"
            "    water = 0\n"
            "    while left < right:\n"
            "        if height[left] < height[right]:\n"
            "            if height[left] >= left_max:\n"
            "                left_max = height[left]\n"
            "            else:\n"
            "                water += left_max - height[left]\n"
            "            left += 1\n"
            "        else:\n"
            "            if height[right] >= right_max:\n"
            "                right_max = height[right]\n"
            "            else:\n"
            "                water += right_max - height[right]\n"
            "            right -= 1\n"
            "    return water\n"
        ),
        "mutant_solution": (
            "def trap(height):\n"
            "    left_max = 0\n"
            "    water = 0\n"
            "    for h in height:\n"
            "        if h >= left_max:\n"
            "            left_max = h\n"
            "        else:\n"
            "            water += left_max - h\n"
            "    return water\n"
        ),
    },
    {
        "id": "coding_merge_intervals",
        "title": "Merge Intervals",
        "difficulty": "medium",
        "topics": ["arrays", "sorting"],
        "statement": (
            "Given a list of [start, end] intervals, merge every overlapping "
            "pair and return the merged intervals sorted by start."
        ),
        "constraints": [
            "0 <= len(intervals) <= 10^4",
            "start <= end for every interval.",
        ],
        "function": "merge_intervals",
        "starter_code": (
            "def merge_intervals(intervals):\n"
            '    """Merge overlaps; return sorted by start."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[[1, 3], [2, 6], [8, 10]]]},
             "expected": [[1, 6], [8, 10]]},
            {"input": {"args": [[[1, 4], [4, 5]]]}, "expected": [[1, 5]]},
            {"input": {"args": [[[1, 2]]]}, "expected": [[1, 2]]},
        ],
        "hidden_tests": [
            {"input": {"args": [[[8, 10], [1, 3], [2, 6]]]},
             "expected": [[1, 6], [8, 10]]},
            {"input": {"args": [[[1, 4], [0, 2]]]}, "expected": [[0, 4]]},
            {"input": {"args": [[[1, 4], [0, 0]]]},
             "expected": [[0, 0], [1, 4]]},
            {"input": {"args": [[[2, 3], [4, 5], [6, 7]]]},
             "expected": [[2, 3], [4, 5], [6, 7]]},
            {"input": {"args": [[]]}, "expected": []},
        ],
        "reference_solution": (
            "def merge_intervals(intervals):\n"
            "    if not intervals:\n"
            "        return []\n"
            "    spans = sorted(intervals, key=lambda iv: (iv[0], iv[1]))\n"
            "    merged = [[spans[0][0], spans[0][1]]]\n"
            "    for s, e in spans[1:]:\n"
            "        if s <= merged[-1][1]:\n"
            "            if e > merged[-1][1]:\n"
            "                merged[-1][1] = e\n"
            "        else:\n"
            "            merged.append([s, e])\n"
            "    return merged\n"
        ),
        "mutant_solution": (
            "def merge_intervals(intervals):\n"
            "    if not intervals:\n"
            "        return []\n"
            "    merged = [[intervals[0][0], intervals[0][1]]]\n"
            "    for s, e in intervals[1:]:\n"
            "        if s <= merged[-1][1]:\n"
            "            if e > merged[-1][1]:\n"
            "                merged[-1][1] = e\n"
            "        else:\n"
            "            merged.append([s, e])\n"
            "    return merged\n"
        ),
    },
    {
        "id": "coding_coin_change",
        "title": "Coin Change Fewest Coins",
        "difficulty": "medium",
        "topics": ["dp"],
        "statement": (
            "Given coin denominations and an amount, return the fewest coins "
            "needed to make the amount, or -1 when impossible. Coins are "
            "unlimited."
        ),
        "constraints": [
            "1 <= len(coins) <= 12",
            "0 <= amount <= 500",
        ],
        "function": "coin_change",
        "starter_code": (
            "def coin_change(coins, amount):\n"
            '    """Return fewest coins for amount, or -1."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 2, 5], 11]}, "expected": 3},
            {"input": {"args": [[2], 3]}, "expected": -1},
            {"input": {"args": [[1], 0]}, "expected": 0},
        ],
        "hidden_tests": [
            {"input": {"args": [[1, 3, 4], 6]}, "expected": 2},
            {"input": {"args": [[1, 5, 6, 9], 11]}, "expected": 2},
            {"input": {"args": [[2, 5], 11]}, "expected": 4},
            {"input": {"args": [[1, 2, 5], 0]}, "expected": 0},
            {"input": {"args": [[3, 7], 14]}, "expected": 2},
        ],
        "reference_solution": (
            "def coin_change(coins, amount):\n"
            "    INF = amount + 1\n"
            "    dp = [0] + [INF] * amount\n"
            "    for a in range(1, amount + 1):\n"
            "        best = INF\n"
            "        for c in coins:\n"
            "            if c <= a and dp[a - c] + 1 < best:\n"
            "                best = dp[a - c] + 1\n"
            "        dp[a] = best\n"
            "    return -1 if dp[amount] >= INF else dp[amount]\n"
        ),
        "mutant_solution": (
            "def coin_change(coins, amount):\n"
            "    count = 0\n"
            "    for c in sorted(coins, reverse=True):\n"
            "        while amount >= c:\n"
            "            amount -= c\n"
            "            count += 1\n"
            "    return count if amount == 0 else -1\n"
        ),
    },
    {
        "id": "coding_top_k_frequent",
        "title": "Top K Frequent Elements",
        "difficulty": "medium",
        "topics": ["hashing", "sorting"],
        "statement": (
            "Return the k most frequent values. Break frequency ties by "
            "smaller value first."
        ),
        "constraints": [
            "1 <= k <= len(nums) <= 10^4",
            "-10^4 <= nums[i] <= 10^4",
        ],
        "function": "top_k_frequent",
        "starter_code": (
            "def top_k_frequent(nums, k):\n"
            '    """Return k most frequent values, ties smaller-first."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 1, 1, 2, 2, 3], 2]}, "expected": [1, 2]},
            {"input": {"args": [[4, 4, 4, 4], 1]}, "expected": [4]},
            {"input": {"args": [[1], 1]}, "expected": [1]},
        ],
        "hidden_tests": [
            {"input": {"args": [[3, 1, 2, 2, 1, 3], 2]}, "expected": [1, 2]},
            {"input": {"args": [[5, 5, 4, 4, 3], 2]}, "expected": [4, 5]},
            {"input": {"args": [[1, 2, 3, 4], 3]}, "expected": [1, 2, 3]},
            {"input": {"args": [[2, 2, 1, 1, 1], 1]}, "expected": [1]},
            {"input": {"args": [[7, 7, 7, 8, 8, 9], 3]},
             "expected": [7, 8, 9]},
        ],
        "reference_solution": (
            "def top_k_frequent(nums, k):\n"
            "    from collections import Counter\n"
            "    freq = Counter(nums)\n"
            "    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))\n"
            "    return [v for v, _ in ranked[:k]]\n"
        ),
        "mutant_solution": (
            "def top_k_frequent(nums, k):\n"
            "    from collections import Counter\n"
            "    freq = Counter(nums)\n"
            "    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], -kv[0]))\n"
            "    return [v for v, _ in ranked[:k]]\n"
        ),
    },
    {
        "id": "coding_median_sorted_arrays",
        "title": "Median of Two Sorted Arrays",
        "difficulty": "hard",
        "topics": ["arrays"],
        "statement": (
            "Given two sorted lists, return the median of all values "
            "combined as a float. Either list may be empty, but not both."
        ),
        "constraints": [
            "0 <= len(nums1), len(nums2) <= 10^3",
            "len(nums1) + len(nums2) >= 1",
            "Both lists are sorted ascending.",
        ],
        "function": "find_median",
        "starter_code": (
            "def find_median(nums1, nums2):\n"
            '    """Return the combined median as a float."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": [[1, 3], [2]]}, "expected": 2.0},
            {"input": {"args": [[1, 2], [3, 4, 5]]}, "expected": 3.0},
            {"input": {"args": [[0, 0], [0, 0]]}, "expected": 0.0},
        ],
        "hidden_tests": [
            {"input": {"args": [[1, 2], [3, 4]]}, "expected": 2.5},
            {"input": {"args": [[1, 3, 5], [2, 4]]}, "expected": 3.0},
            {"input": {"args": [[], [1]]}, "expected": 1.0},
            {"input": {"args": [[2], []]}, "expected": 2.0},
            {"input": {"args": [[1, 2, 3, 4, 5, 6], [7, 8]]},
             "expected": 4.5},
        ],
        "reference_solution": (
            "def find_median(nums1, nums2):\n"
            "    merged = sorted(nums1 + nums2)\n"
            "    n = len(merged)\n"
            "    mid = n // 2\n"
            "    if n % 2 == 1:\n"
            "        return float(merged[mid])\n"
            "    return (merged[mid - 1] + merged[mid]) / 2\n"
        ),
        "mutant_solution": (
            "def find_median(nums1, nums2):\n"
            "    merged = sorted(nums1 + nums2)\n"
            "    return float(merged[(len(merged) - 1) // 2])\n"
        ),
    },
    {
        "id": "coding_word_ladder",
        "title": "Word Ladder Length",
        "difficulty": "hard",
        "topics": ["strings", "graphs", "bfs"],
        "statement": (
            "Given begin and end words plus a word list, return the length "
            "of the shortest transformation sequence from begin to end "
            "changing one letter at a time with every intermediate word in "
            "the list. Return 0 when no sequence exists, and 1 when begin "
            "equals end."
        ),
        "constraints": [
            "All words share one length between 1 and 10.",
            "0 <= len(word_list) <= 500",
        ],
        "function": "ladder_length",
        "starter_code": (
            "def ladder_length(begin_word, end_word, word_list):\n"
            '    """Return the shortest ladder length, or 0."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": ["hit", "cog",
                                ["hot", "dot", "dog", "lot", "log", "cog"]]},
             "expected": 5},
            {"input": {"args": ["hit", "cog",
                                ["hot", "dot", "dog", "lot", "log"]]},
             "expected": 0},
            {"input": {"args": ["a", "b", ["a", "b", "c"]]},
             "expected": 2},
        ],
        "hidden_tests": [
            {"input": {"args": ["a", "d", ["b", "c", "d"]]}, "expected": 2},
            {"input": {"args": ["hit", "cog",
                                ["hot", "dot", "dog", "lot", "log", "cog"]]},
             "expected": 5},
            {"input": {"args": ["lost", "cost",
                                ["most", "cost", "lost", "fost"]]},
             "expected": 2},
            {"input": {"args": ["a", "a", ["a"]]}, "expected": 1},
            {"input": {"args": ["ab", "cd", ["ad", "cb", "cd"]]},
             "expected": 3},
        ],
        "reference_solution": (
            "def ladder_length(begin_word, end_word, word_list):\n"
            "    from collections import deque\n"
            "    words = set(word_list)\n"
            "    if end_word not in words:\n"
            "        return 0\n"
            "    if begin_word == end_word:\n"
            "        return 1\n"
            "    queue = deque([(begin_word, 1)])\n"
            "    seen = {begin_word}\n"
            "    while queue:\n"
            "        word, dist = queue.popleft()\n"
            "        for i in range(len(word)):\n"
            "            for c in 'abcdefghijklmnopqrstuvwxyz':\n"
            "                nxt = word[:i] + c + word[i + 1:]\n"
            "                if nxt == end_word:\n"
            "                    return dist + 1\n"
            "                if nxt in words and nxt not in seen:\n"
            "                    seen.add(nxt)\n"
            "                    queue.append((nxt, dist + 1))\n"
            "    return 0\n"
        ),
        "mutant_solution": (
            "def ladder_length(begin_word, end_word, word_list):\n"
            "    words = set(word_list)\n"
            "    if end_word not in words:\n"
            "        return 0\n"
            "    best = [0]\n"
            "    def differs_by_one(a, b):\n"
            "        return sum(1 for x, y in zip(a, b) if x != y) == 1\n"
            "    def dfs(word, length, visited):\n"
            "        if word == end_word:\n"
            "            if best[0] == 0:\n"
            "                best[0] = length\n"
            "            return True\n"
            "        for nxt in sorted(words):\n"
            "            if nxt not in visited and differs_by_one(word, nxt):\n"
            "                visited.add(nxt)\n"
            "                if dfs(nxt, length + 1, visited):\n"
            "                    return True\n"
            "        return False\n"
            "    dfs(begin_word, 1, {begin_word})\n"
            "    return best[0]\n"
        ),
    },
    {
        "id": "coding_min_window",
        "title": "Minimum Window Substring",
        "difficulty": "hard",
        "topics": ["strings", "sliding-window", "hashing"],
        "statement": (
            "Given strings s and t, return the shortest substring of s that "
            "contains every character of t with multiplicity, or an empty "
            "string when no such window exists."
        ),
        "constraints": [
            "0 <= len(s) <= 10^4",
            "0 <= len(t) <= 100",
        ],
        "function": "min_window",
        "starter_code": (
            "def min_window(s, t):\n"
            '    """Return the shortest covering window, or ""."""\n'
            "    pass\n"
        ),
        "visible_tests": [
            {"input": {"args": ["ADOBECODEBANC", "ABC"]}, "expected": "BANC"},
            {"input": {"args": ["a", "a"]}, "expected": "a"},
            {"input": {"args": ["a", "b"]}, "expected": ""},
        ],
        "hidden_tests": [
            {"input": {"args": ["aaab", "aab"]}, "expected": "aab"},
            {"input": {"args": ["ab", "b"]}, "expected": "b"},
            {"input": {"args": ["abc", "ac"]}, "expected": "abc"},
            {"input": {"args": ["abca", "aa"]}, "expected": "abca"},
            {"input": {"args": ["xyz", "z"]}, "expected": "z"},
        ],
        "reference_solution": (
            "def min_window(s, t):\n"
            "    from collections import Counter\n"
            "    if not t or not s:\n"
            "        return ''\n"
            "    need = Counter(t)\n"
            "    missing = len(t)\n"
            "    have = {}\n"
            "    best = ''\n"
            "    left = 0\n"
            "    for right, ch in enumerate(s):\n"
            "        if have.get(ch, 0) < need.get(ch, 0):\n"
            "            missing -= 1\n"
            "        have[ch] = have.get(ch, 0) + 1\n"
            "        while missing == 0:\n"
            "            window = s[left:right + 1]\n"
            "            if not best or len(window) < len(best):\n"
            "                best = window\n"
            "            out = s[left]\n"
            "            if have.get(out, 0) <= need.get(out, 0):\n"
            "                missing += 1\n"
            "            have[out] -= 1\n"
            "            left += 1\n"
            "    return best\n"
        ),
        "mutant_solution": (
            "def min_window(s, t):\n"
            "    from collections import Counter\n"
            "    need = Counter(t)\n"
            "    have = Counter()\n"
            "    best = ''\n"
            "    left = 0\n"
            "    for right, ch in enumerate(s):\n"
            "        have[ch] += 1\n"
            "        while all(have[c] > 0 for c in need):\n"
            "            window = s[left:right + 1]\n"
            "            if not best or len(window) < len(best):\n"
            "                best = window\n"
            "            have[s[left]] -= 1\n"
            "            left += 1\n"
            "    return best\n"
        ),
    },
]


def get_coding_problem(problem_id: str) -> dict[str, Any] | None:
    """Return the bank problem with this id, or None."""
    for problem in CODING_PROBLEMS:
        if problem.get("id") == problem_id:
            return problem
    return None


def list_coding_problems(
    *,
    difficulty: str | None = None,
    topic: str | None = None,
) -> list[dict[str, Any]]:
    """Bank problems in stable order, optionally filtered."""
    items = list(CODING_PROBLEMS)
    if difficulty:
        wanted = str(difficulty).strip().lower()
        items = [p for p in items
                 if str(p.get("difficulty", "")).lower() == wanted]
    if topic:
        wanted_topic = str(topic).strip().lower()
        items = [p for p in items
                 if wanted_topic in [str(t).lower()
                                     for t in (p.get("topics") or [])]]
    return items


def public_coding_problem(problem: dict[str, Any]) -> dict[str, Any]:
    """Candidate-safe projection of one bank problem.

    Exposes the statement, constraints, starter code, and visible
    examples only. Hidden tests, reference solutions, and mutant
    solutions never leave the server.
    """
    return {
        "id": problem.get("id"),
        "type": "coding",
        "category": "coding",
        "title": problem.get("title"),
        "difficulty": problem.get("difficulty"),
        "topics": list(problem.get("topics") or []),
        "statement": problem.get("statement"),
        "constraints": list(problem.get("constraints") or []),
        "function": problem.get("function"),
        "starter_code": problem.get("starter_code"),
        "visible_tests": [
            {
                "input": dict(case.get("input") or {}),
                "expected": case.get("expected"),
            }
            for case in (problem.get("visible_tests") or [])
        ],
    }

