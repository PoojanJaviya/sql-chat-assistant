import re

def is_safe_query(sql: str) -> tuple[bool, str]:
    """
    Analyzes a SQL query for safety violations.
    Returns (True, "") if safe, or (False, "Reason") if unsafe.
    """
    if not sql:
        return False, "Empty query provided."

    # Normalize for inspection
    cleaned_sql = sql.strip()
    upper_sql = cleaned_sql.upper()

    # Rule 3: Block multiple statements
    # Allow a semicolon only if it's the very last character
    if ';' in cleaned_sql[:-1]:
        return False, "Multiple SQL statements are not allowed."

    # Rule 1: Block dangerous commands
    # Using word boundaries (\b) to ensure we don't catch parts of other words
    forbidden_commands = ["DROP", "TRUNCATE", "ALTER", "ATTACH", "DETACH", "GRANT", "REVOKE", "PRAGMA"]
    
    for cmd in forbidden_commands:
        if re.search(r'\b' + cmd + r'\b', upper_sql):
            return False, f"Dangerous command forbidden: {cmd}"

    # Rule 2: Strict checks for DELETE and UPDATE
    is_delete = re.search(r'^\s*DELETE\b', upper_sql)
    is_update = re.search(r'^\s*UPDATE\b', upper_sql)

    if is_delete or is_update:
        # Check for existence of WHERE
        if "WHERE" not in upper_sql:
            return False, "Destructive command (DELETE/UPDATE) requires a WHERE clause."
        
        # Extract condition after WHERE
        # Split on the first occurrence of WHERE
        parts = upper_sql.split("WHERE", 1)
        if len(parts) < 2:
            return False, "Invalid WHERE clause format."
            
        condition = parts[1].strip()

        # Check for vague conditions (e.g., 1=1, TRUE)
        # Matches 1=1, 0=0, 99 = 99
        if re.search(r'(\d+)\s*=\s*\1', condition):
            return False, "Unsafe WHERE clause detected (Identity pattern 1=1)."
            
        # Matches explicit TRUE
        if re.search(r'\bTRUE\b', condition):
            return False, "Unsafe WHERE clause detected (TRUE)."

    # Rule 4: SELECT queries are generally safe (passed implicitly if no other rules broke)
    return True, ""

