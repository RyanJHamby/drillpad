# System Design: Distributed File Storage (Dropbox/Google Drive)

## Firm Archetype: Dropbox, Google Drive, Microsoft OneDrive, AWS S3

**Problem:** Store user files, sync across devices, handle large files (1TB+), deduplicate identical content, versioning. 1B users, 100 billion files, 10 EB total storage.

**Why hard:** Consistency (file sync), large file handling (chunking), deduplication, bandwidth optimization, conflict resolution.

---

## Architecture

```
Client (Upload):
  1. User selects file: document.pdf (50 MB)
  
  2. Client chunks file:
     ├─ Split into 4 MB chunks (12 chunks)
     ├─ Compute hash per chunk: sha256
     └─ Chunk hashes: [hash1, hash2, ..., hash12]
  
  3. Check dedup (optional):
     ├─ Query: chunk1_hash exists?
     ├─ If yes (already stored): skip
     ├─ If no: upload
  
  4. Parallel upload:
     ├─ Upload chunks 1-4 in parallel (4 threads)
     ├─ Each: PUT /chunks/{chunk_hash}
     ├─ Backoff on 503 (server busy)
     └─ Retry on transient error
  
  5. Commit metadata:
     ├─ POST /files
     ├─ Body: {filename, chunk_hashes: [hash1, ..., hash12], size}
     └─ Server returns: file_id, created_at

Client (Download):
  1. GET /files/{file_id}
     ├─ Server returns: {chunk_hashes, size, created_at}
  
  2. Fetch chunks in parallel:
     ├─ GET /chunks/{chunk1_hash}, /chunks/{chunk2_hash}, ...
     ├─ Parallel: 4 concurrent requests
     └─ Download to local cache
  
  3. Reassemble:
     ├─ Concatenate chunks in order
     ├─ Verify: hash(reassembled) == file hash
     └─ Write to local file

Sync (iCloud-style):
  1. File created locally
  2. Chunked + uploaded (from above)
  3. Server updates: file_id, metadata
  4. Sync daemon on other devices:
     ├─ Polls: /sync/changes?since=timestamp
     ├─ Server returns: {deleted, created, modified} since timestamp
     └─ Device: download new, delete removed, update modified
  
  5. Conflict resolution (both devices modify):
     ├─ Device A: modified at 10:00
     ├─ Device B: modified at 10:05
     ├─ Conflict: both versions exist
     ├─ Resolution: rename B → "filename (device B's copy).pdf"
     ├─ User: manually merge if needed
```

---

## Chunking Strategy

### Fixed-size chunks (4 MB)

```
File: video.mp4 (1 GB)
Chunks: 1GB / 4MB = 256 chunks

Advantages:
  - Simple
  - Easy parallelism (chunk 1, 2, 3, ... in parallel)
  - Fixed memory (buffer size = 4 MB)

Disadvantages:
  - Inefficient for small files (overhead)
  - Redundant on small edits (1 byte change = 1 chunk re-upload)
```

### Content-defined chunks (Rabin fingerprinting)

```
Algorithm: rolling hash to find chunk boundaries
  - Use: rolling polynomial hash (Rabin fingerprinting)
  - Chunk boundary: when hash % N == 0
  - Variable chunk size: 1-16 MB
  
Example:
  File: "abcdefghijklmnop"
  Hash at position 5: "abcde" % 256 == 0 → boundary
  Chunk 1: "abcde"
  Chunk 2: "fghijklmnop"

Advantages:
  - 1 byte edit = only modified chunk re-uploaded
  - Example: 1 byte edit in 1GB file = 1 KB re-upload (instead of 4 MB)
  - Deduplication: identical sections = identical chunks

Disadvantages:
  - Complex computation (rolling hash)
  - CPU cost: 10-20% of upload time
  - Trade-off: bandwidth saved > CPU cost

Typical:
  Dropbox: fixed 4 MB
  AWS S3: fixed 5 MB
  IPFS/content-addressable: content-defined
```

---

## Deduplication

### Chunk-level deduplication

```
User A uploads: document.pdf with chunks [chunk1, chunk2, chunk3]
User B uploads: same document (different name)

Storage:
  1. User A: chunk1 uploaded (hash: abc123)
  2. User B: check chunk1 hash (abc123) → exists!
  3. Link: User B's copy → existing chunk1 (no re-upload)
  4. Saved: 4 MB per duplicate

Dedup ratio:
  ├─ Office files (docx, xlsx): high (similar structure)
  ├─ Videos (mp4, mkv): low (different encoding = different bytes)
  ├─ Backups: very high (daily incremental = 95% identical)
  └─ Average: 1.5-2x dedup (store 1 copy, serve 2)
```

### File-level vs block-level

```
File-level (naive):
  file_hash = sha256(entire_file)
  If file_hash matches existing → link
  
  Problem: any 1 byte change = new hash
  1 byte edit in 1 GB file = not detected

Block-level (better):
  file = [block1, block2, block3]
  block_hash = sha256(block)
  If block1 and block2 unchanged, block3 changed:
    → Reuse block1, block2 (no re-upload)
    → Upload only block3
  
  Used by: Dropbox, rsync, ZFS
```

### Cross-user vs single-user

```
Cross-user dedup:
  ├─ User A uploads: file.pdf
  ├─ User B uploads: same file.pdf
  ├─ Storage: 1 copy (shared)
  └─ Risk: privacy (infer similar files across users)

Single-user dedup:
  ├─ User A: upload, deduplicate across their own files
  ├─ Safe: no privacy leak
  ├─ Savings: 30-50% (lots of duplicate content)
  └─ Used by: most cloud storage

Hybrid:
  ├─ Single-user dedup always
  ├─ Cross-user dedup opt-in
  └─ Example: Google Drive (cross-user dedup available)
```

---

## Versioning & Sync

### Version History

```
File: document.txt

V1: 10:00 "Hello world"
V2: 10:05 "Hello from Alice"
V3: 10:10 "Hello from Bob"

Storage:
  ├─ Current: points to V3
  ├─ History: keep last 30 versions or 30 days
  ├─ Cleanup: delete old versions (save space)
  └─ Dedup: if V2 == V1 (no change), don't store

Rollback:
  User clicks: restore V1
  Server: current = V1
  Client: download V1 (replaces V3)
```

### Conflict Resolution

```
Scenario:
  Device A (offline, no sync):
    10:00: download file (version 1)
    10:05: edit → version 2 local
    10:30: back online, upload version 2
  
  Device B (online):
    10:10: edit file → version 2 uploaded
    10:20: edit file → version 3 uploaded
    10:30: Device A syncs version 2 (conflicts with version 3)

Conflict detection:
  ├─ Server: version 3 is current
  ├─ Device A: uploading version 2 (parent = version 1)
  ├─ Problem: parent mismatch (version 3 ≠ version 1)
  └─ Result: conflict

Resolution strategies:

1. Last-write-wins (bad):
   - Device A (10:30): version 2 wins → overwrites version 3
   - Device B's changes lost (bad for user)

2. Merge (complex):
   - If text file: merge line by line (git-style)
   - If binary: can't merge
   - Dependent on file type

3. Create both versions (Dropbox approach):
   - Keep version 3 (current)
   - Create version 3.1 (Device A's copy)
   - Rename: "document (Device A's copy).txt"
   - User: manually choose which version
   - No data loss

4. Lamport clocks (ordering):
   - Assign logical timestamp to each edit
   - Version 3 (timestamp 5) > version 2 (timestamp 4)
   - Version 3 wins automatically
   - More reliable than wall-clock time
```

---

## Scale Calculation

```
1B users
Avg files: 100 files/user = 100B total files
Avg file size: 100 KB
Total storage: 100B files * 100 KB = 10 EB

Chunk size: 4 MB
Chunks: 10 EB / 4 MB = 2.5B chunks
Chunk metadata: 2.5B * 200 bytes = 500 GB

Bandwidth:
  Daily uploads: 100M users * 1 file * 100 KB = 10 PB/day
  Peak: 5x = 50 PB/day

  Upload workers: 10 PB / 86400 sec / 1 Mbps worker = 
    10^15 bytes / 86400 / (10^6 bits / 8) ≈ 926K workers
  
  Cost: 926K workers * $0.10/hour = $92.6K/hour (expensive!)
  
  Optimization: delta-sync (only upload changes, not full file)
    → reduces 50 PB to 5 PB peak
    → 92.6K workers → 9.3K workers
```

---

## Consistency Models

### Eventual Consistency (Dropbox-style)

```
Device A uploads: file.pdf version 2
  → Server: file.pdf = version 2

Device B: polls /sync/changes
  → Missing: version 2 for 5 seconds (lag)
  → Eventually: receives update

Trade-off:
  ✓ Fast writes (no wait for all devices)
  ✗ Temporary inconsistency (different devices see different versions)
  
Used by: Dropbox, Google Drive, iCloud
```

### Strong Consistency (Expensive)

```
Device A uploads: file.pdf version 2
  → Server: replicate to 3 datacenters
  → Wait for 2/3 ACK (quorum)
  → Return 200 OK to device A

Device B: reads file.pdf
  → Guaranteed: version 2 (not stale)

Trade-off:
  ✓ No conflicts, always consistent
  ✗ Slow writes (wait for quorum)
  ✗ Unavailable on partition

Used by: databases, strong guarantees
```

---

## Code Example (Python)

```python
import hashlib
import boto3
from datetime import datetime

class FileStorageService:
    CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB
    
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.files_table = self.dynamodb.Table('files')
        self.chunks_table = self.dynamodb.Table('chunks')
    
    def upload_file(self, user_id, filename, file_path):
        """Upload file with chunking and deduplication."""
        file_size = os.path.getsize(file_path)
        chunks = []
        chunk_hashes = []
        
        # Chunk the file
        with open(file_path, 'rb') as f:
            while True:
                chunk_data = f.read(self.CHUNK_SIZE)
                if not chunk_data:
                    break
                
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                chunks.append((chunk_hash, chunk_data))
                chunk_hashes.append(chunk_hash)
        
        # Upload chunks (parallel in practice)
        for chunk_hash, chunk_data in chunks:
            # Check if chunk exists
            existing = self.chunks_table.get_item(
                Key={'chunk_hash': chunk_hash}
            )
            
            if not existing.get('Item'):
                # Upload to S3
                self.s3.put_object(
                    Bucket='chunks',
                    Key=chunk_hash,
                    Body=chunk_data
                )
                
                # Record metadata
                self.chunks_table.put_item(
                    Item={
                        'chunk_hash': chunk_hash,
                        'size': len(chunk_data),
                        'uploaded_at': datetime.now().isoformat(),
                        'users': [user_id]
                    }
                )
            else:
                # Chunk exists, just add user to list
                self.chunks_table.update_item(
                    Key={'chunk_hash': chunk_hash},
                    UpdateExpression='ADD #users :uid',
                    ExpressionAttributeNames={'#users': 'users'},
                    ExpressionAttributeValues={':uid': {user_id}}
                )
        
        # Record file metadata
        file_id = hashlib.sha256(f"{user_id}:{filename}:{datetime.now().isoformat()}".encode()).hexdigest()
        self.files_table.put_item(
            Item={
                'file_id': file_id,
                'user_id': user_id,
                'filename': filename,
                'size': file_size,
                'chunk_hashes': chunk_hashes,
                'created_at': datetime.now().isoformat(),
                'version': 1
            }
        )
        
        return file_id
    
    def download_file(self, user_id, file_id, output_path):
        """Download file (reconstruct from chunks)."""
        # Fetch file metadata
        response = self.files_table.get_item(Key={'file_id': file_id})
        file_data = response['Item']
        chunk_hashes = file_data['chunk_hashes']
        
        # Fetch and reconstruct
        with open(output_path, 'wb') as f:
            for chunk_hash in chunk_hashes:
                # Fetch chunk from S3
                obj = self.s3.get_object(Bucket='chunks', Key=chunk_hash)
                chunk_data = obj['Body'].read()
                f.write(chunk_data)
        
        return output_path
    
    def get_file_versions(self, user_id, file_id):
        """Get version history."""
        # Query GSI: user_id, file_id → all versions
        response = self.files_table.query(
            IndexName='user_file_versions',
            KeyConditionExpression='user_id = :uid AND file_id = :fid',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':fid': file_id
            },
            ScanIndexForward=False  # DESC by version
        )
        
        return response['Items']
    
    def sync_changes(self, user_id, since_timestamp):
        """Get changes since timestamp for sync."""
        # Query files modified after timestamp
        response = self.files_table.query(
            IndexName='user_created_at',
            KeyConditionExpression='user_id = :uid AND created_at > :ts',
            ExpressionAttributeValues={
                ':uid': user_id,
                ':ts': since_timestamp
            }
        )
        
        return response['Items']
```

---

## Interview Checklist

- [ ] Explain chunking (fixed vs content-defined)
- [ ] Deduplication: block-level vs file-level, cross-user risks
- [ ] Parallel upload/download with retry
- [ ] Versioning and rollback mechanism
- [ ] Conflict resolution: last-write-wins vs create both copies
- [ ] Eventual vs strong consistency tradeoffs
- [ ] Scale: chunking reduces bandwidth by 5-10x
- [ ] Metadata storage (DynamoDB) vs blob storage (S3)

## Common Wrong Answers

- ❌ "Upload entire file at once" — 1 GB file = single point of failure, slow
- ❌ "No deduplication" — 2x storage cost (same files duplicated)
- ❌ "Delete old versions immediately" — users lose edit history
- ❌ "Last-write-wins always" — loses edits in conflict scenarios
- ❌ "No sync conflict handling" — data loss when devices sync
- ❌ "Single S3 upload" — no parallelism, slow, no dedup
