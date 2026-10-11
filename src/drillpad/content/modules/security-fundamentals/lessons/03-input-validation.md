# Input Validation & Injection: SQL, XSS, Command Injection

## The Core Principle

**Never trust user input.**

Treat all input as potentially malicious:
- Query parameters
- POST body
- Headers
- File uploads
- Cookies

## Injection Attacks: How They Work

### SQL Injection (Classic)

```python
# VULNERABLE CODE
username = request.args.get('username')
query = f"SELECT * FROM users WHERE username = '{username}'"
result = db.execute(query)
```

Attacker submits: `username = ' OR '1'='1`

Query becomes:
```sql
SELECT * FROM users WHERE username = '' OR '1'='1'
```

Returns all users (because `'1'='1'` is always true).

### Fix: Parameterized Queries

```python
# SAFE CODE
username = request.args.get('username')
query = "SELECT * FROM users WHERE username = ?"
result = db.execute(query, (username,))
```

Database treats `?` as a literal value, not SQL.

Attacker input is now just data, not code.

### XSS (Cross-Site Scripting)

```python
# VULNERABLE
username = request.args.get('username')
html = f"<h1>Welcome {username}</h1>"
return html
```

Attacker submits: `username = <script>steal_cookies()</script>`

Browser renders:
```html
<h1>Welcome <script>steal_cookies()</script></h1>
```

Script runs in user's browser, steals session cookie.

### Fix: HTML Escape

```python
# SAFE
from html import escape
username = request.args.get('username')
html = f"<h1>Welcome {escape(username)}</h1>"
return html
```

Attacker input becomes:
```html
<h1>Welcome &lt;script&gt;steal_cookies()&lt;/script&gt;</h1>
```

Script is rendered as text, doesn't execute.

### Command Injection

```python
# VULNERABLE
filename = request.args.get('file')
os.system(f"convert {filename} thumbnail.jpg")
```

Attacker submits: `filename = image.jpg; rm -rf /`

System executes:
```bash
convert image.jpg; rm -rf / thumbnail.jpg
```

Deletes entire filesystem.

### Fix: Use Proper APIs

```python
# SAFE
import subprocess
filename = request.args.get('file')
subprocess.run(["convert", filename, "thumbnail.jpg"], check=True)
```

Subprocess treats arguments as data, not shell commands.

## Validation vs Sanitization

### Validation: Reject bad input

```python
# Validate email format
import re
email = request.args.get('email')
if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
    return "Invalid email", 400  # Reject
```

**Pros:** Fails fast, clear error message
**Cons:** Need to know valid format for each field

### Sanitization: Clean bad input

```python
# Remove dangerous characters from filename
filename = request.args.get('file')
filename = re.sub(r'[^a-zA-Z0-9_-]', '', filename)  # Keep only safe chars
```

**Pros:** More permissive (allows more input)
**Cons:** Might silently change meaning

**Best practice:** Validate first, sanitize if needed.

## Injection Prevention Checklists

### SQL Injection

- [ ] Always use parameterized queries
- [ ] Never concatenate user input into SQL strings
- [ ] Use ORM (SQLAlchemy, Django ORM) for queries
- [ ] Limit database user permissions (don't use admin account for app)
- [ ] Enable SQL logging to catch attacks

### XSS (Browser Injection)

- [ ] HTML-escape all user input in templates
- [ ] Use template engines with auto-escape (Jinja2, Django templates)
- [ ] Set Content-Security-Policy header (restrict script sources)
- [ ] Validate JSON inputs (don't just eval JSON)
- [ ] Use httponly cookie flag (prevents JavaScript access)

### Command Injection

- [ ] Never use os.system() with user input
- [ ] Use subprocess with list of args (not shell=True)
- [ ] Use proper library for OS operations (pathlib for files, etc.)
- [ ] Run services with least privilege (not root)
- [ ] Disable shell features (no $, backticks, pipes in filenames)

## Interview Pattern: Input Validation

```
Q: "Users upload CSV files. You parse them and insert into database.
   What could go wrong?"

Weak answer:
  "SQL injection, I'll use parameterized queries"
  (❌ Only addresses one vector)

Strong answer:
  "Multiple injection vectors:
  
  1. SQL Injection (CSV → DB):
     - User uploads CSV with malicious SQL in column
     - If we parse naively: CSV[0] = \"'; DROP TABLE users; --\"
     - And insert: INSERT INTO logs VALUES ('\"' + csv[0] + '\"')
     - Fix: Use parameterized queries for inserts
  
  2. CSV Injection (CSV formulas):
     - User uploads CSV where column[0] = \"=cmd|'/c calc'!A1\"
     - Excel interprets = as formula, executes command
     - Fix: Don't auto-execute formulas, or quote formula starts with '
  
  3. Path Traversal (File handling):
     - User submits filename: \"../../etc/passwd\"
     - If we naively open file: open(upload_dir + filename)
     - Exposes system files
     - Fix: Use pathlib, resolve to absolute path, check it's in upload_dir
  
  4. Memory Explosion (ZIP bombs):
     - User uploads 10GB ZIP compressed to 1MB
     - Extraction uncompresses to 10GB
     - Server runs out of RAM
     - Fix: Check extracted size < limit before decompressing
  
  5. Implementation:
     ```python
     import csv
     from pathlib import Path
     
     uploaded = request.files['file']
     filepath = Path(upload_dir) / secure_filename(uploaded.filename)
     
     # Validate file
     if filepath.stat().st_size > 10_000_000:  # 10MB limit
       return \"File too large\", 413
     
     # Parse safely
     with open(filepath) as f:
       reader = csv.DictReader(f)
       for row in reader:
         # Parameterized insert
         db.execute(
           'INSERT INTO logs (name, value) VALUES (?, ?)',
           (row['name'], row['value'])
         )
     ```
  
  6. Monitoring:
     - Log suspicious inputs (SQL keywords, path traversal attempts)
     - Alert on large files, unusual patterns
     - Rate limit uploads (prevent DoS)"

Why this signals good judgment:
  - You identified multiple attack vectors (not just one)
  - You understood file handling risks (path traversal, compression)
  - You used secure functions (secure_filename, pathlib)
  - You parameterized queries
  - You monitored for attacks
```

## OWASP Top 10 (Most Common Vulnerabilities)

1. **SQL Injection** → Use parameterized queries
2. **Broken Authentication** → Use OAuth, bcrypt, 2FA
3. **Sensitive Data Exposure** → Encrypt, HTTPS, no logging
4. **XML External Entities (XXE)** → Disable XML entities
5. **Broken Access Control** → Check permissions before every action
6. **Security Misconfiguration** → Secure defaults
7. **XSS** → HTML escape, CSP header
8. **Insecure Deserialization** → Validate before deserializing
9. **Using Components with Known Vulnerabilities** → Keep deps updated
10. **Insufficient Logging & Monitoring** → Log security events

## Checklist: Input Validation in Production

- [ ] All DB queries parameterized
- [ ] All HTML output escaped
- [ ] All file operations use pathlib
- [ ] All command execution uses subprocess (not os.system)
- [ ] Dependencies scanned for CVEs (safety, snyk)
- [ ] Input size limited (prevent DoS)
- [ ] Security logging enabled
- [ ] Regular penetration testing

## What This Signals

- You understand injection is pervasive (not just SQL)
- You use parameterized queries automatically
- You think about file handling (path traversal, compression bombs)
- You know validation + sanitization approach
