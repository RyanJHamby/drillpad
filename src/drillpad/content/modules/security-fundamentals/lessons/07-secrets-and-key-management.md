# Secrets & Key Management

## Secret Storage

```
Bad (don't do):
  ├─ Hardcoded in code: password = "secret123"
  ├─ Committed to git: git log shows secrets
  ├─ Environment variables unencrypted: anyone with shell access
  └─ Cost: one compromised developer = entire infrastructure

Good:
  ├─ Secrets manager: AWS Secrets Manager, HashiCorp Vault
  ├─ Encrypted at rest: KMS envelope encryption
  ├─ Audit log: who accessed the secret?
  ├─ Rotation: automatic key rollover
  └─ Access control: RBAC, only services that need it

Workflow:
  1. Create secret in AWS Secrets Manager
  2. Secret encrypted with KMS key
  3. App requests secret at runtime
  4. Secrets Manager verifies IAM identity
  5. Returns secret (encrypted in transit with TLS)
```

## Key Rotation

```
Problem: old key compromised (or routine rotation)

Naive rotation:
  1. Create new key: key_v2
  2. Update all configs: KEY = key_v2
  3. Deploy everywhere
  4. Destroy old key
  └─ Risk: during deploy, some instances still using key_v1

Better (gradual):
  1. Create new key: key_v2
  2. Add to allowed keys: [key_v1, key_v2]
  3. Deploy everywhere (both keys valid)
  4. Monitor: all using key_v2?
  5. If yes: remove key_v1
  └─ Safe: old key still valid during transition

Automatic:
  ├─ Secrets Manager: enable automatic rotation
  ├─ Period: every 30 days
  ├─ Lambda function: updates key
  ├─ All instances pick up new key
  └─ Transparent: no manual work
```

## Envelope Encryption (KMS)

```
Problem: encrypt 1 GB file
  ├─ Key stored in database
  ├─ Attacker reads database → gets key → decrypts file
  └─ Single point of failure

Solution: envelope encryption

  Master key (in AWS KMS):
    ├─ Stored in HSM (hardware security module)
    ├─ Never leaves AWS
    └─ Accessed only via API

  Data encryption key (DEK):
    ├─ Generated per file/object
    ├─ Used to encrypt file: ciphertext = encrypt(file, DEK)
    └─ Encrypted DEK stored with file

  Workflow:
    1. Generate DEK (in memory, random)
    2. Encrypt file: ciphertext = AES-256(file, DEK)
    3. Encrypt DEK with KMS master key: encrypted_dek = KMS.encrypt(DEK)
    4. Store: {ciphertext, encrypted_dek}
    
  Decryption:
    1. Retrieve: {ciphertext, encrypted_dek}
    2. Decrypt DEK: DEK = KMS.decrypt(encrypted_dek) [only KMS can do this]
    3. Decrypt file: file = AES-256(ciphertext, DEK)

  Benefit:
    ├─ Attacker with database access: gets encrypted_dek (useless without KMS)
    ├─ Attacker needs KMS API access: requires IAM credentials
    └─ Defense in depth: two layers
```

---

## Interview Checklist

- [ ] Never hardcode secrets
- [ ] Secrets manager: encrypted at rest + in transit
- [ ] Key rotation: automatic or manual with gradual rollout
- [ ] Envelope encryption: master key + data key pattern
- [ ] Audit: who accessed what secret, when?

## Common Wrong Answers

- ❌ "Encrypt with static key" — compromise = all data exposed
- ❌ "No rotation" — old keys compromise the system
- ❌ "Store keys with data" — defeats encryption
- ❌ "Hardcode in code" — dev environment leaks to prod
