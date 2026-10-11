# System Design: Geospatial & Ride-Hailing (Uber/Lyft)

## Firm Archetype: Uber, Lyft, Google Maps, DoorDash

**Problem:** Find nearest drivers in O(1) time. 1M drivers in 50 cities, 100K ride requests/sec, P99 < 100ms. Handle surge pricing, hot spots, driver distribution.

**Why hard:** 2D spatial indexing at scale, real-time updates (drivers moving), nearest-neighbor queries, handling skewed distribution (downtown vs suburbs).

---

## Spatial Indexing: Geohash vs Quadtree vs S2

### Geohash (Simple, Limited)

```
Latitude: 40.7128 (Manhattan)
Longitude: -74.0060

Geohash algorithm:
  1. Interleave lat/long bits
  2. Encode as base32
  
  Geohash: "dr5reg" (6 chars = ~1 km)
  Geohash: "dr5re" (5 chars = ~5 km)
  Geohash: "dr5r" (4 chars = ~20 km)

Grid:
  [u]  [v]  [w]
  [x]  [y]  [z]  (e.g., "dr5r" covers 16 cells)
  [a]  [b]  [c]

Query: find drivers in geohash "dr5re"
  ├─ Prefix match: geohash LIKE "dr5re%"
  ├─ DynamoDB query: fast, indexed
  ├─ Return: all drivers in cell

Problem:
  Boundary: driver at (40.71, -74.01) in "dr5reg"
            rider at (40.712, -74.01) in "dr5reh"
            Different cells! (nearest neighbor not guaranteed)
  
  Solution: query geohash ± neighbors (9 cells total)
```

### Quadtree (Balanced, Better)

```
Recursive spatial partitioning:

       World
      /  |  \  \
    NW  NE  SW  SE

Each quadrant further divided:
  
  NYC quadrant:
    /  |  \ \
   NW NE SW SE
   
   If NW has >1000 drivers, divide again

Depth: ~20 levels (precision = 1 meter)

Query: find drivers within 1 km of (40.7128, -74.0060)
  1. Traverse tree to leaf covering location
  2. Check: NW, NE, SW, SE quadrants
  3. Recursively: if >1000 drivers in quadrant, divide further
  4. Return: drivers within radius

Complexity:
  Build: O(n log n) where n = number of drivers
  Query: O(log n + k) where k = results returned
  
Pros:
  ✓ Balanced tree (fast queries)
  ✓ Handles skew (hot spots subdivided more)
  ✓ Cache-friendly
  
Cons:
  ✗ Complex updates (rebalancing)
  ✗ Memory overhead
```

### S2 Geometry (Google, Best)

```
Spherical geometry (treats Earth as sphere):
  - Covers Earth with hierarchical cells
  - Cell level 0-30 (level 30 = 1 cm²)
  
S2 Cell ID: 64-bit integer (like Geohash)
  - Ordered: nearby locations → nearby IDs
  - Hierarchical: contains parent/child cells
  
Query: find drivers within 1 km
  1. Convert radius to S2 cells (level 30)
  2. Union nearby cells → covering
  3. Query DynamoDB: S2_CELL_ID IN (cells)
  4. Return: drivers in covering

Pros:
  ✓ Spherical (accurate Earth measurements)
  ✓ Hierarchical queries (skip to level 20 if <1000 drivers)
  ✓ Industry standard (Google, Uber, Lyft)
  
Used by: Google Maps, Uber, Lyft, H3 (Uber's open source version)
```

---

## Architecture

```
Driver Update:
  1. Driver location update (every 5 sec)
     ├─ Mobile app: POST /location {lat, long, driver_id}
     ├─ Compute S2 cell: level 30 (1 cm precision)
     └─ Compute S2 cell: level 20 (100 m precision, coarser)

  2. Write to Redis:
     ├─ Key: drivers_in_cell:{s2_level_20_cell_id}
     ├─ Value: set of {driver_id}
     ├─ TTL: 30 seconds (location stale)
     └─ Complexity: ~500K cells in NYC, 1M drivers
     
     Memory: 500K cells * 1000 drivers avg * 8 bytes = 4 GB

  3. Write to DynamoDB (eventual consistency):
     ├─ PK: driver_id
     ├─ Attributes: lat, long, s2_cell_20, status (available, busy, offline)
     ├─ TTL: 1 minute (remove offline drivers)
     └─ GSI: s2_cell_20 → driver_ids (for queries)

Rider Matching:
  1. Rider: "Request a ride" at (40.7580, -73.9855)
  
  2. Compute S2 cells (expanding radius):
     ├─ Level 30: 1 cm (probably 0 drivers)
     ├─ Level 25: 1 meter (maybe 1-2 drivers)
     ├─ Level 20: 100 meters (maybe 10-20 drivers)
     └─ Stop: when >5 drivers found (don't search too far)

  3. Query Redis:
     ├─ Get drivers_in_cell for cells in radius
     ├─ Complexity: O(1) per cell
     ├─ Return: {driver1, driver2, ...}
     └─ Filter by: status = "available"

  4. Score drivers:
     ├─ Distance: manhattan or haversine
     ├─ ETA: based on routing engine
     ├─ Rating: driver rating (5.0 = best)
     └─ Score: distance * 0.5 + eta * 0.3 + (5 - rating) * 0.2
     
     Example:
       driver1: 2km away, 8 min ETA, 4.8 rating → score 3.2
       driver2: 5km away, 12 min ETA, 4.2 rating → score 7.8
       Winner: driver1

  5. Send match request:
     ├─ Driver notification: "Ride from A to B, accept?"
     ├─ Timeout: 30 seconds
     ├─ If no response: try next driver

  6. On acceptance:
     ├─ Lock driver: unavailable for other matches
     ├─ Update: rider ↔ driver assigned
     └─ Create: trip_id
```

---

## Surge Pricing & Hot Spots

### Dynamic Pricing

```
Demand/Supply ratio:
  ├─ Requests: 1000/min in downtown
  ├─ Available drivers: 100
  ├─ Ratio: 10:1 (high demand)
  └─ Surge: 3x (multiply fare by 3)

Update frequency:
  ├─ Calculate: every 1 minute
  ├─ Grid-based: 500m × 500m cells
  ├─ Store: Redis (fast lookup)
  ├─ Propagate: push to clients
  
Query:
  GET /surge?lat=40.7&long=-74&cell_size=500m
  Response: {surge_multiplier: 3.2}
```

### Hot Spot Handling

```
Problem: Downtown Manhattan (10K requests/day)
         vs Suburbs (1K requests/day)
         → Skewed distribution

Solution 1: Incentivize supply
  ├─ Surge pricing: high rates attract drivers to hot spots
  ├─ Bonus: $5 extra for drivers picking up downtown
  └─ Effect: more drivers move to hot spot

Solution 2: Predict & preposition
  ├─ ML model: predict demand 30 min ahead
  ├─ Target: drivers not currently matched
  ├─ Offer: "Go to downtown, earn bonuses"
  └─ Reduce: wait time for riders

Solution 3: Geofencing & batching
  ├─ Zone: downtown = single "super zone"
  ├─ Batch requests: 10 requests → 2 drivers each (5 rides/driver)
  ├─ Efficiency: reuse trips (shared rides)
  └─ Result: 2x capacity without 2x drivers
```

---

## Scale Calculation

```
1M active drivers
50 cities

Spatial resolution: S2 level 20 (100m cells)
  NYC: 30 km × 20 km = 600 km²
  At level 20 (~100m): 600 cells × 200 cells = 120K cells
  
  Across 50 cities: 120K * 50 = 6M cells

Drivers per cell:
  Average: 1M drivers / 6M cells = 0.16 drivers/cell
  Hot spot (downtown): 10 drivers/cell
  Suburbs: 0.05 drivers/cell

Redis memory:
  6M cells * 100 bytes (metadata) = 600 MB (small!)
  Plus: driver set per cell (8 bytes/driver)
  Hot spots: 120K cells * 5 drivers avg = 600K entries * 8 bytes = 5 MB
  Total: ~600 MB (one Redis node sufficient)

QPS:
  100K ride requests/sec
  Each request: 1 query (which drivers are near?)
  Each query: 3 cell lookups (expanding radius)
  Total: 100K * 3 = 300K Redis lookups/sec
  
  Redis: ~1M QPS per node (single-threaded)
  Nodes needed: 300K / 1M = 0.3 → 1 node (over-provisioned)
```

---

## Failure Modes

### Driver Goes Offline

```
Scenario: Driver's app crashes, phone dies

Detection:
  ├─ Heartbeat: driver sends ping every 30 sec
  ├─ Timeout: no ping for 60 sec → mark offline
  ├─ Redis: TTL 60 sec on location, auto-expire
  ├─ DynamoDB: TTL 1 min on driver record
  
Effect:
  └─ Driver no longer appears in matching

Recovery:
  ├─ Driver restarts app
  ├─ Send location update
  ├─ Back in matching within 1 sec
```

### Surge Calculation Fails

```
Scenario: Surge pricing service crashes

Effect:
  ├─ Riders see: "Price unavailable"
  ├─ Fallback: base fare (no surge multiplier)
  ├─ Loss: surge revenue during outage
  
Mitigation:
  ├─ Caching: surge multipliers cached for 1 min
  ├─ Replay: use last known surge on failure
  └─ Replication: 3 surge services (failover)
```

### Geographic Boundary Issues

```
Scenario: Rider at (40.7129, -74.0060) (boundary)
          Drivers at (40.7130, -74.0060) (adjacent cell)

Problem:
  ├─ Different S2 cells (boundary between cells)
  ├─ Query misses adjacent drivers
  
Solution:
  ├─ Always query neighboring cells
  ├─ S2 provides: cell.neighbors()
  ├─ Cost: slight increase in query cells
  └─ Benefit: no boundary misses
```

---

## Code Example (Python with S2)

```python
import s2geometry as s2
from redis import Redis
import boto3

class RideMatchingService:
    def __init__(self):
        self.redis = Redis()
        self.dynamodb = boto3.resource('dynamodb')
        self.drivers_table = self.dynamodb.Table('drivers')
    
    def update_driver_location(self, driver_id, lat, long):
        """Update driver location."""
        # Compute S2 cells
        point = s2.LatLng.FromDegrees(lat, long)
        cell_l20 = s2.CellId.FromLatLng(point).parent(20)
        cell_l30 = s2.CellId.FromLatLng(point).parent(30)
        
        # Update Redis (fast, real-time)
        self.redis.sadd(f"drivers_in_cell:{cell_l20}", driver_id)
        self.redis.expire(f"drivers_in_cell:{cell_l20}", 30)
        
        # Update DynamoDB (eventual consistency)
        self.drivers_table.update_item(
            Key={'driver_id': driver_id},
            UpdateExpression='SET lat = :lat, long = :long, s2_cell_20 = :cell20, updated_at = :now',
            ExpressionAttributeValues={
                ':lat': lat,
                ':long': long,
                ':cell20': str(cell_l20),
                ':now': int(time.time())
            }
        )
    
    def find_nearby_drivers(self, rider_lat, rider_long, max_distance_km=5):
        """Find available drivers near rider."""
        point = s2.LatLng.FromDegrees(rider_lat, rider_long)
        
        # Expand search radius: start with smaller cells
        drivers = set()
        max_level = 30
        min_level = 15
        
        for level in range(max_level, min_level - 1, -1):
            cell = s2.CellId.FromLatLng(point).parent(level)
            
            # Get neighbors
            neighbors = [cell] + list(cell.GetEdgeNeighbors())
            
            for neighbor in neighbors:
                cell_str = str(neighbor)
                drivers_in_cell = self.redis.smembers(f"drivers_in_cell:{cell_str}")
                drivers.update(drivers_in_cell)
            
            if len(drivers) >= 5:
                break
        
        return list(drivers)
    
    def match_rider_to_driver(self, rider_id, rider_lat, rider_long, destination):
        """Match rider to nearest driver."""
        candidates = self.find_nearby_drivers(rider_lat, rider_long)
        
        if not candidates:
            return {"status": "no_drivers"}
        
        # Score drivers
        scored = []
        for driver_id in candidates:
            driver = self.drivers_table.get_item(Key={'driver_id': driver_id})['Item']
            
            if driver.get('status') != 'available':
                continue
            
            # Distance
            distance = self._haversine(
                rider_lat, rider_long,
                driver['lat'], driver['long']
            )
            
            # ETA (simplified: distance / 30 km/h)
            eta = distance / 0.5  # minutes
            
            # Rating
            rating = driver.get('rating', 4.5)
            
            # Score
            score = distance * 0.5 + eta * 0.3 + (5 - rating) * 0.2
            scored.append((score, driver_id))
        
        scored.sort()
        
        if not scored:
            return {"status": "all_busy"}
        
        best_driver_id = scored[0][1]
        
        # Send match request
        return {
            "status": "matched",
            "driver_id": best_driver_id,
            "distance_km": distance,
            "eta_minutes": eta
        }
    
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Distance between two coordinates in km."""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371  # Earth radius km
        
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
```

---

## Interview Checklist

- [ ] Explain S2 geometry (hierarchical cells, levels 15-30)
- [ ] Nearest neighbor query: expanding radius approach
- [ ] Redis for hot data (drivers_in_cell), DynamoDB for cold
- [ ] Surge pricing: demand/supply ratio, dynamic multiplier
- [ ] Hot spot handling: incentives, prediction, batching
- [ ] Failure modes: driver offline, surge calculation down
- [ ] Scale: 1M drivers, 100K QPS, 300K Redis lookups/sec
- [ ] Boundary handling: always query neighbor cells

## Common Wrong Answers

- ❌ "Query database for every match request" — 100K QPS, DB can't handle
- ❌ "Use Geohash with exact cell" — boundary misses nearby drivers
- ❌ "Fixed price (no surge)" — loses revenue on demand spikes
- ❌ "No driver availability tracking" — match drivers who are offline
- ❌ "Calculate surge every request" — too expensive, stale multipliers OK
- ❌ "Single S2 cell level" — hot spots need finer granularity
