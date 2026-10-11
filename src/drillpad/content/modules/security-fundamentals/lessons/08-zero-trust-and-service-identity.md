# Zero Trust & Service Identity

## Zero Trust Principle

```
Old (perimeter-based):
  ├─ Firewall: block external traffic
  ├─ Inside firewall: trust everything
  └─ Problem: insider attack, compromised box = full access

Zero trust:
  ├─ Never trust by default (even inside network)
  ├─ Verify every request (who are you? what do you want?)
  ├─ Encrypt everything (in-flight + at-rest)
  └─ Principle: assume breach, design defense
```

## Service Identity (mTLS)

```
Problem: microservice A calls microservice B
  ├─ Service B: how do I know A is legitimate?
  ├─ A could be attacker with forged request
  └─ Solution: mutual TLS (mTLS)

mTLS (mutual TLS):
  ├─ Both A and B have X.509 certificates
  ├─ A connects to B with TLS
  ├─ B verifies A's certificate (proves A is legitimate)
  ├─ A verifies B's certificate (proves B is legitimate)
  └─ Result: both authenticated

Certificate management:
  ├─ Issue certs to services
  ├─ Store securely (no hardcoding)
  ├─ Rotate before expiry
  ├─ Revoke if compromised
  └─ Tool: cert managers (cert-manager, Vault)

Example (Istio service mesh):
  ├─ Service A → envoy proxy (sidecar)
  ├─ Envoy proxy → mTLS → Service B proxy
  ├─ Certificates: managed by Istio CA
  ├─ Rotation: automatic
  └─ Encryption: transparent to application
```

## Workload Identity

```
Problem: service needs to access AWS resources
  ├─ Traditional: hardcode AWS access key in code
  ├─ Risk: commit key, developer leaks key
  └─ Compromise: all AWS resources accessible

Workload Identity (AWS IAM Roles for Pods):
  
  Kubernetes pod:
    ├─ No hardcoded keys
    ├─ Assume IAM role via IRSA (IAM Roles for Service Accounts)
    ├─ OIDC trust relationship: K8s → AWS
    └─ Token exchange: Kubernetes token → AWS STS token
  
  Flow:
    1. Pod needs to access S3
    2. App requests token from Kubernetes (in-memory)
    3. Kubernetes returns OIDC token (cryptographically signed)
    4. App exchanges token with AWS STS
    5. STS: verifies signature, returns temporary credentials
    6. App uses credentials to access S3
  
  Benefits:
    ├─ No hardcoded keys
    ├─ Automatic rotation (STS renews every hour)
    ├─ Pod-level isolation: only this pod has access
    └─ Audit: CloudTrail logs which pod accessed what

IAM policy:
  {
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::123456789:oidc-provider/oidc.eks.amazonaws.com"
    },
    "Condition": {
      "StringEquals": {
        "oidc.eks.amazonaws.com:sub": "system:serviceaccount:default:my-app"
      }
    },
    "Action": "sts:AssumeRole"
  }
  └─ Only my-app service account in default namespace can assume role
```

---

## Interview Checklist

- [ ] Zero trust: verify every request
- [ ] mTLS: mutual certificate verification
- [ ] Service identity: no hardcoded keys
- [ ] IRSA: workload identity in Kubernetes
- [ ] Certificate rotation: automatic or manual

## Common Wrong Answers

- ❌ "Trust inside network" — insider attacks still possible
- ❌ "Hardcode AWS keys" — compromise = full access
- ❌ "No encryption between services" — eavesdropping risk
- ❌ "Manual certificate rotation" — easy to miss, security gap
