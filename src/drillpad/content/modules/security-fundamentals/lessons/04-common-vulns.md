# Common Vulnerabilities: OWASP Top 10 in Context

## Broken Authentication

### Vulnerability: Weak Session Management

```python
# VULNERABLE: Session stored in cookie, not validated
@app.route('/login', methods=['POST'])
def login():
    user = db.find_user(request.form['username'])
    if verify_password(user.password, request.form['password']):
        response = make_response("Logged in")
        response.set_cookie('user_id', user.id)  # Plain ID!
        return response

# Attacker changes cookie: user_id=2 (another user)
# Server trusts cookie: you're now logged in as user 2
```

### Fix: Cryptographically Signed Sessions

```python
# SAFE: Flask with secure session
from flask import session

@app.route('/login', methods=['POST'])
def login():
    user = db.find_user(request.form['username'])
    if verify_password(user.password, request.form['password']):
        session['user_id'] = user.id  # Flask signs it
        return "Logged in"

# Session is now signed + encrypted
# Attacker can't forge or modify without key
```

### Vulnerability: Password Storage

```python
# VULNERABLE: Plaintext or weak hash
password_hash = sha1(password)  # SHA1 is too fast (can brute-force)
```

### Fix: Slow Hash

```python
# SAFE
import bcrypt
password_hash = bcrypt.hashpw(password, bcrypt.gensalt(rounds=12))
# bcrypt: intentionally slow (100ms per hash), stops brute-force
```

## Sensitive Data Exposure

### Vulnerability: Logging Passwords

```python
# VULNERABLE
import logging
logging.info(f"User {username} password {password}")  # Password in logs!
```

### Fix: Never Log Sensitive Data

```python
# SAFE
logging.info(f"User {username} authenticated")  # No password in logs
```

### Vulnerability: Unencrypted Transport

```python
# VULNERABLE
GET http://example.com/api/balance  (no HTTPS!)
# Attacker sniffs network: sees all data
```

### Fix: Always HTTPS

```python
# SAFE
GET https://example.com/api/balance  (TLS 1.2+)
# Data encrypted in transit
```

## Broken Access Control

### Vulnerability: No Permission Checks

```python
# VULNERABLE
@app.route('/user/<user_id>/profile')
def get_profile(user_id):
    user = db.get_user(user_id)
    return user.profile  # No check if current user owns profile!
```

Attacker: GET /user/2/profile → sees user 2's data (unauthorized)

### Fix: Verify Ownership

```python
# SAFE
@app.route('/user/<user_id>/profile')
def get_profile(user_id):
    if current_user.id != int(user_id):
        return "Forbidden", 403  # Check first
    user = db.get_user(user_id)
    return user.profile
```

### Pattern: Permission Checks

```python
# For every operation, ask: "Does current user own this resource?"

def delete_post(post_id):
    post = db.get_post(post_id)
    if post.author_id != current_user.id:
        return "You can't delete someone else's post", 403
    post.delete()
```

## XML External Entities (XXE)

### Vulnerability: XML Parsing

```python
# VULNERABLE
import xml.etree.ElementTree as ET
xml_string = request.data
root = ET.fromstring(xml_string)  # Parses XML features
```

Attacker submits:
```xml
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<data>&xxe;</data>
```

Server parses, reads `/etc/passwd` from disk.

### Fix: Disable XML Features

```python
# SAFE
import defusedxml.ElementTree as ET
root = ET.fromstring(xml_string)  # XXE disabled
```

Or use defusedxml library which disables dangerous features.

## Insecure Deserialization

### Vulnerability: Pickle (Python)

```python
# VULNERABLE
import pickle
data = request.data
obj = pickle.loads(data)  # Deserialize from network!
```

Attacker can craft pickle that executes arbitrary code.

### Fix: Use JSON Instead

```python
# SAFE
import json
data = json.loads(request.data)  # JSON can't execute code
```

If you must serialize objects:
- Use JSON with schema validation
- Never pickle untrusted data
- Use validation libraries (marshmallow, pydantic)

## Using Components with Known Vulnerabilities

### Vulnerability: Outdated Dependencies

```
Your requirements.txt:
  flask==1.0.0  (released 2018)
  
CVE-2019-1234 in Flask 1.0.0: Remote code execution!
Attacker: Exploit CVE, executes code on your server
```

### Fix: Regular Updates

```bash
# Check for vulnerable dependencies
pip-audit

# Update
pip install --upgrade flask
```

## Security Misconfiguration

### Vulnerability: Default Credentials

```
Database admin: admin / password
S3 bucket: public read access (should be private)
Debug mode enabled in production
```

### Fix: Security Hardening

```python
# Checklist
- [ ] Change all default credentials
- [ ] Disable debug mode in production
- [ ] Set secure headers (X-Content-Type-Options, CSP, etc.)
- [ ] Run with minimal permissions (not root)
- [ ] Close unnecessary ports
- [ ] Enable logging + monitoring
```

## Insufficient Logging & Monitoring

### Vulnerability: Silent Attacks

```
Attacker logs in 100 times with wrong passwords
No alerts
Attacker finally guesses right password
No alerts
Attacker deletes all user data
No alerts

You find out weeks later in a support ticket.
```

### Fix: Security Logging

```python
# Log all security events
logging.warning(f"Failed login: {username} (attempt 5)")
logging.error(f"Unauthorized access: user {user_id} tried to delete post {post_id}")
logging.critical(f"Mass deletion detected: 10000 records deleted by user {user_id}")

# Alert immediately on suspicious activity
if failed_logins > 5:
    alert_security_team()
```

## Interview Pattern: Vulnerability Assessment

```
Q: "You're hiring developers to code your payment system.
   What would you audit for security?"

Weak answer:
  "I'd use a security scanner"
  (❌ Tools find only obvious issues)

Strong answer:
  "Multi-layered code review:
  
  1. Authentication:
     - Are passwords hashed with bcrypt/scrypt? (not SHA1)
     - Are sessions signed/encrypted? (not just user_id in cookie)
     - Is 2FA available for sensitive operations?
  
  2. Authorization:
     - Every route: Does code check if user owns resource?
     - Database queries: Use parameterized queries (no SQL injection)
     - File uploads: Use pathlib, check size, validate format
  
  3. Data Protection:
     - Sensitive data (passwords, SSN): Never logged
     - Transmission: HTTPS everywhere
     - Storage: Field-level encryption for PII
  
  4. Input Validation:
     - All user input validated (size, type, format)
     - HTML output escaped
     - Command execution: use subprocess, not os.system
  
  5. Dependencies:
     - Run pip-audit (check for CVEs)
     - Vendor lock-in: review cryptography libraries
     - Audit major dependencies (Flask, SQLAlchemy)
  
  6. Logging & Monitoring:
     - Security events logged (login, auth failures, deletions)
     - Alerts for suspicious activity
     - Audit trail for sensitive operations
  
  7. Process:
     - Code review by security-trained dev
     - Automated scans (SAST) for common issues
     - Penetration testing by external firm
     - Bug bounty program (let researchers find issues)
  
  Cost: Security is expensive but losing user data is more expensive."

Why this signals good judgment:
  - You have a structured review process
  - You knew specific vulnerabilities to check
  - You understood the cost/benefit (security takes time)
  - You included monitoring (not just prevention)
```

## Security Checklist for Every Application

- [ ] Authentication: bcrypt, signed sessions, 2FA
- [ ] Authorization: Permission checks on every operation
- [ ] Encryption: TLS for transport, encryption at rest for sensitive data
- [ ] Input validation: All user input validated
- [ ] No SQL injection: Parameterized queries
- [ ] No XSS: HTML escape, CSP header
- [ ] No command injection: subprocess with list args
- [ ] Dependency scanning: pip-audit, snyk, dependabot
- [ ] Logging: Security events logged
- [ ] Monitoring: Alerts for suspicious activity
- [ ] Secrets: External KMS (not hardcoded)
- [ ] Headers: X-Content-Type-Options, Strict-Transport-Security, CSP

## What This Signals

- You understand the OWASP Top 10 (not just theory)
- You know specific fixes for each vulnerability
- You have a security review process
- You think about logging and monitoring
