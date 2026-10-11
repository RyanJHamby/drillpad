# Encryption: In Transit vs At Rest, Key Management

## Encryption Basics

**Symmetric encryption (AES):**
- Same key for encrypt and decrypt
- Fast (CPU optimized)
- Problem: How do you share the key?

**Asymmetric encryption (RSA, EC):**
- Public key (share with world)
- Private key (keep secret)
- Public key encrypts, private key decrypts
- Slow (CPU intensive)
- Problem: Still need to share public key securely

## In-Transit Encryption (Over Network)

Goal: Protect data while traveling over the internet.

### TLS/SSL (Standard)

```
Client connects to server:
  1. Client: "Hi, I want to connect securely"
  2. Server: "Sure, here's my certificate" [includes public key]
  3. Client: Verifies certificate (is server legit?)
  4. Client-Server: Use asymmetric encryption to agree on a shared key
  5. All future communication: Encrypted with shared key (symmetric)
```

**Why this works:**
- Asymmetric protects the key exchange
- Symmetric encrypts the actual data (fast)
- Server's certificate is signed by trusted CA (prevents impersonation)

**Implementation:**
```python
import ssl
import socket

# Server
context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain("cert.pem", "key.pem")  # Server's cert + key

with socket.socket() as sock:
    sock.bind(("localhost", 443))
    with context.wrap_socket(sock, server_side=True) as ssock:
        client, addr = ssock.accept()
        # All data now encrypted

# Client
context = ssl.create_default_context()
with socket.socket() as sock:
    with context.wrap_socket(sock, server_hostname="example.com") as ssock:
        ssock.connect(("example.com", 443))
        # All data now encrypted
```

**Real-world:**
- HTTP → HTTPS (adds TLS)
- AMQP → AMQPS (adds TLS)
- Any protocol can be wrapped in TLS

### Pitfalls

**Pitfall 1: Self-signed certificates**
```
Server generates its own certificate (not signed by CA)
Client connects: Browser shows "Certificate not trusted"
```
Fine for internal systems, bad for public APIs.

**Pitfall 2: Certificate expiration**
```
Your certificate expires on 2025-01-31
2025-02-01: All clients get SSL_ERROR_CERT_EXPIRED
All connections fail
```
Monitor certificate expiration, renew before expiry.

**Pitfall 3: Private key leak**
```
Attacker steals your private key
Can now decrypt all past sessions (if not using perfect forward secrecy)
```
Use PFS (Perfect Forward Secrecy) so old sessions stay private even if key leaks.

## At-Rest Encryption (On Disk)

Goal: Protect data stored in database.

### Transparent Data Encryption (TDE)

```
Application:
  INSERT INTO users VALUES (name='Alice', password='secret123');

Database (with TDE):
  - Encrypts 'Alice' and 'secret123' before writing to disk
  - Decrypts when reading from disk
  - Application doesn't know, happens transparently

Disk (encrypted):
  [random bytes that look like noise]
```

**Implementation in practice:**
- PostgreSQL: Use pgcrypto extension
- MySQL: Data-at-rest encryption (built-in)
- AWS: Enable encryption on RDS (one checkbox)

**Cost:** ~5% performance overhead (encryption/decryption).

### Field-Level Encryption (More Granular)

```
Application handles encryption:
  password_hash = bcrypt.hash(password)  # Salted hash
  encrypted_ssn = encrypt_aes(ssn, key)  # AES encryption

Database stores encrypted_ssn as blob
Decryption happens in application (not database)
```

**Why separate from TDE:**
- Database admins can't read SSN (security layer)
- Key is separate from database (database breach ≠ key compromise)
- Flexibility (different fields, different keys)

### Pitfall: Encryption Without Key Management

```
# BAD: Hardcoded key
KEY = "my-secret-key-12345"
encrypted = AES.encrypt(data, KEY)

# Anyone with code access has the key
# Key appears in git history
# Impossible to rotate
```

**Good: External key management**
```
# Use AWS KMS, HashiCorp Vault, etc.
key = kms.get_key(key_id="arn:aws:kms:...")
encrypted = AES.encrypt(data, key)
```

## Key Management

### Lifecycle

```
1. Generate: Create key (random, cryptographically secure)
2. Store: Keep key separate from encrypted data
3. Use: Encrypt/decrypt without exposing key
4. Rotate: Periodically replace with new key
5. Retire: Decommission old key, keep for old decryption
6. Destroy: Securely delete when no longer needed
```

### Key Rotation Strategy

```
Problem: Attacker steals one key, can decrypt everything

Solution: Rotate keys regularly
  2025-01-01: Key1 is active
  2025-02-01: Generate Key2, make it active
              Re-encrypt all data encrypted with Key1 using Key2
  2025-03-01: Delete Key1 (or keep for decryption only)

Result: Attacker with old Key1 can only decrypt Jan data
```

**Cost:** Re-encryption is expensive (scan all data, decrypt + encrypt).

### Where to Store Keys

| Location | Security | Availability |
|---|---|---|
| **Hardcoded** | ❌ None | ✓ Always |
| **Config file** | ❌ Low | ✓ Always |
| **Environment var** | ⚠️ Medium | ✓ Always |
| **AWS KMS** | ✓ High | ✓ Available |
| **HashiCorp Vault** | ✓ High | ✓ Depends |
| **Hardware HSM** | ✓ Highest | ⚠️ Limited |

**Best practice:** External KMS (AWS KMS, Vault, etc.)

## Interview Pattern: Encryption Strategy

```
Q: "Design a password reset system.
   Users email a link: 'click here to reset'."

Weak answer:
  "Encrypt the email in transit with TLS"
  (❌ Missing at-rest encryption)

Strong answer:
  "Encryption at multiple layers:
  
  1. In-transit (TLS):
     - Email server to user's email provider: TLS
     - Password reset link sent over HTTPS: TLS
     - Cost: Standard, just enable HTTPS
  
  2. At-rest (Database):
     - Reset token stored in database (hashed, not encrypted)
     - Why hash not encrypt? Reset token is one-time use, expire quickly
     - Hash prevents DB admins from reading tokens
  
  3. Key material:
     - Use bcrypt/scrypt for hashing (password-based)
     - Use random tokens for reset links
     - Don't hardcode keys
  
  4. Token lifecycle:
     - Generate random token: 256 bits
     - Hash token: sha256(token)
     - Store hash in database: reset_token_hash
     - User gets: 'https://example.com/reset?token=<raw_token>'
     - User clicks: Server computes sha256(token), looks up in DB
     - Match? Token is valid
  
  5. Expiration:
     - Token expires in 1 hour (reset link invalid after)
     - Cost: Forces user to request new link if they wait (good for security)
  
  6. Monitoring:
     - Log all reset requests (who, when)
     - Alert if reset requested for same user 10x/day (attack?)
     - Track success rate (did user complete reset?)"

Why this signals good judgment:
  - You understood multiple encryption layers
  - You knew hashing ≠ encryption (appropriate for tokens)
  - You thought about key management (not hardcoding)
  - You considered expiration and monitoring
```

## Checklist: Encryption in Production

- [ ] HTTPS for all external APIs (TLS 1.2+)
- [ ] Database encryption (TDE or field-level)
- [ ] Keys stored in KMS (not code, not config files)
- [ ] Key rotation policy (annual minimum)
- [ ] Passwords hashed with bcrypt/scrypt (not encrypted)
- [ ] Secrets rotated after leak (if it happens)
- [ ] Monitor cert expiration (automated renewal)
- [ ] PFS enabled (DHE, ECDHE cipher suites)

## What This Signals

- You understand in-transit vs at-rest encryption
- You know TLS protects network, not database
- You understand key management (KMS, rotation)
- You distinguish encryption (reversible) from hashing (one-way)
