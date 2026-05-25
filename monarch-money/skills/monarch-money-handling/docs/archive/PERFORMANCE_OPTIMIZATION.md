# Performance Optimization Guide

This document outlines strategies to improve the speed and efficiency of the Monarch Money skill.

## Current Performance Profile

### Baseline Timings (October 2025)

Based on recent usage:

| Operation | Time | Notes |
|-----------|------|-------|
| `npm run find` | ~2-3s | Uses saved session |
| `npm run categories` (cached) | ~0.5s | Local cache hit |
| `npm run categories` (fresh) | ~2-3s | API fetch required |
| `npm run notes` | ~2-3s | Single API mutation |
| `npm run split-receipt` | ~5-8s | Multiple API calls (split + notes) |
| `npm run validate` | ~0.1s | Local validation only |

### Bottlenecks Identified

1. **Session initialization** - 1-2s even with saved sessions
2. **Sequential API calls** - Split + notes executed separately
3. **Category fetching** - 2-3s when cache miss
4. **Transaction search** - 2-3s for date/merchant lookups

## Optimization Strategies

### 1. Category Caching (Already Implemented ✅)

**Status:** Active and working well

**Impact:** 90% reduction in category fetch time

**How it works:**
- First call fetches from API and caches to `.cache/categories.json`
- Subsequent calls read from cache (~0.5s vs ~2-3s)
- Cache persists across sessions

**Usage:**
```bash
# Uses cache (fast)
npm run categories

# Force refresh
npm run categories -- --refresh
```

**Further improvements:**
- Add cache expiration (e.g., 24 hours)
- Cache invalidation on category updates
- Validate cache on startup

### 2. Parallel API Calls

**Status:** Not implemented yet

**Impact:** 50% reduction in multi-operation workflows

**Current:**
```typescript
// Sequential (slow)
const txn = await findTransaction(...);
const categories = await getCategories(...);
const result = await splitTransaction(...);
```

**Proposed:**
```typescript
// Parallel (fast)
const [txn, categories] = await Promise.all([
  findTransaction(...),
  getCategories(...)
]);
const result = await splitTransaction(...);
```

**Implementation:**
Create a new script `scripts/batch_operations.ts` that:
- Accepts multiple operations as input
- Executes independent operations in parallel
- Returns combined results

### 3. Bulk Transaction Updates

**Status:** API supports it, but not fully utilized

**Impact:** 70% reduction for multi-transaction updates

**Current:**
```bash
# Update 5 transactions (sequential)
for id in txn1 txn2 txn3 txn4 txn5; do
  npm run update -- "$id" --category <cat_id>
done
# Total time: ~10-15s
```

**Proposed:**
```bash
# Batch update (parallel)
npm run bulk-update -- --ids txn1,txn2,txn3,txn4,txn5 --category <cat_id>
# Total time: ~2-3s
```

**Implementation:**
Leverage `bulkUpdateTransactions` mutation (already used in `add_notes.ts`):

```typescript
const result = await mm.graphql.mutation(bulkUpdateMutation, {
  selectedTransactionIds: [id1, id2, id3, ...],
  updates: { categoryId: catId },
  allSelected: false,
  expectedAffectedTransactionCount: ids.length,
  // ...
});
```

### 4. Session Keep-Alive

**Status:** Not implemented

**Impact:** Eliminates 1-2s session initialization overhead

**Problem:**
- Sessions expire after inactivity
- Each script run re-authenticates (even with saved session)

**Solution:**
Create a persistent daemon process:

```bash
# Start daemon
npm run daemon:start

# Daemon keeps session alive and handles requests
npm run find -- --date 2025-10-16 --merchant Amazon
# Uses daemon (no session init) - saves 1-2s
```

**Architecture:**
```
[CLI Command] → [Unix Socket] → [Daemon Process]
                                 ├─ Session Manager
                                 ├─ Request Queue
                                 └─ Cache Manager
```

**Benefits:**
- Zero session overhead per request
- Shared cache across operations
- Request batching/coalescing

### 5. GraphQL Query Optimization

**Status:** Partially implemented

**Impact:** 20-30% reduction in API response time

**Current issue:**
Some queries fetch unnecessary fields (e.g., full transaction details when only ID is needed).

**Optimization:**
Create minimal query variants:

```typescript
// Current: Fetches everything
const fullTransaction = await getTransaction(id);

// Optimized: Fetch only what's needed
const transactionId = await getTransactionId(merchant, date);
```

**Example:**
```graphql
# Minimal query (fast)
query FindTransactionId($filters: TransactionFilterInput!) {
  transactions(filters: $filters, limit: 1) {
    id
  }
}

# Full query (slower)
query FindTransaction($filters: TransactionFilterInput!) {
  transactions(filters: $filters, limit: 1) {
    id
    amount
    merchant { ... }
    category { ... }
    tags { ... }
    # ... many fields
  }
}
```

### 6. Request Deduplication

**Status:** Not implemented

**Impact:** Eliminates redundant API calls

**Scenario:**
Claude might call multiple scripts that fetch the same data:

```bash
npm run find -- --date 2025-10-16  # Fetches transactions
npm run categories                  # Already cached
npm run validate -- ...             # Local only
npm run split-receipt -- ...        # Needs transaction again
```

**Solution:**
- Cache transaction lookups (short TTL, e.g., 30s)
- Deduplicate in-flight requests
- Return cached results when available

### 7. Compression & Minification

**Status:** Not implemented (low priority)

**Impact:** 10-15% reduction in network time

**Technique:**
- Request gzip compression for API responses
- Minify GraphQL queries (remove whitespace)

**Before:**
```graphql
query FindTransaction {
  transactions(filters: $filters) {
    id
    amount
  }
}
```

**After:**
```graphql
query FindTransaction{transactions(filters:$filters){id amount}}
```

## Recommended Implementation Order

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Category caching (already done)
2. Add cache expiration/validation
3. Minimize GraphQL queries

**Expected improvement:** 30-40% faster

### Phase 2: Parallel Execution (3-4 hours)
1. Batch operations script
2. Parallel API calls where possible
3. Bulk update support

**Expected improvement:** 50-60% faster

### Phase 3: Session Management (6-8 hours)
1. Daemon process architecture
2. Unix socket communication
3. Shared cache and session

**Expected improvement:** 70-80% faster

### Phase 4: Advanced (Future)
1. Request deduplication
2. Compression/minification
3. Predictive prefetching

**Expected improvement:** 80-90% faster

## Benchmarking

### Test Scenario: Split Receipt with 3 Categories

**Current workflow:**
```bash
npm run find -- --date 2025-10-16 --merchant Walmart  # 2-3s
npm run categories                                     # 0.5s (cached)
npm run validate -- --splits-file splits.json ...      # 0.1s
npm run split-receipt -- <id> --splits-file splits.json # 5-8s
# Total: ~8-12s
```

**Optimized workflow (Phase 2):**
```bash
npm run receipt-split -- \
  --date 2025-10-16 \
  --merchant Walmart \
  --splits-file splits.json
# Total: ~3-5s (60% faster)
```

**Optimized workflow (Phase 3 - with daemon):**
```bash
npm run receipt-split -- \
  --date 2025-10-16 \
  --merchant Walmart \
  --splits-file splits.json
# Total: ~1-2s (85% faster)
```

## Monitoring & Metrics

### Recommended Metrics to Track

1. **API Call Latency**
   - p50, p95, p99 response times
   - Broken down by operation type

2. **Cache Hit Rate**
   - Category cache hits vs misses
   - Transaction cache (if implemented)

3. **Session Duration**
   - Time between login and expiration
   - Session reuse frequency

4. **Error Rates**
   - API failures
   - Timeout errors
   - Validation failures

### Implementation

Add optional timing/logging:

```bash
# Enable performance logging
export MONARCH_PERF_LOG=true

npm run find -- ...
# Output:
# [PERF] Session init: 1.2s
# [PERF] GraphQL query: 0.8s
# [PERF] Total: 2.0s
```

## Future Ideas

1. **Local Transaction Cache**
   - Cache recent transactions (last 30 days)
   - Refresh incrementally
   - Enables instant search

2. **Predictive Prefetching**
   - Fetch categories on startup
   - Preload recent transactions
   - Background cache warming

3. **GraphQL Subscriptions**
   - Real-time updates for transaction changes
   - Eliminates polling/refetching

4. **Optimistic Updates**
   - Update local cache immediately
   - Sync with API in background
   - Rollback on failure

## Cost/Benefit Analysis

| Optimization | Dev Time | Perf Gain | Complexity | Priority |
|--------------|----------|-----------|------------|----------|
| Category caching | 1h | 90% | Low | ✅ Done |
| Parallel calls | 3h | 50% | Medium | High |
| Bulk updates | 2h | 70% | Low | High |
| Session daemon | 8h | 80% | High | Medium |
| Query optimization | 2h | 30% | Low | Medium |
| Request dedup | 4h | 40% | Medium | Low |
| Compression | 1h | 15% | Low | Low |

## Conclusion

The most impactful optimizations are:

1. **Category caching** (✅ done) - 90% improvement
2. **Parallel API calls** - 50% improvement
3. **Bulk updates** - 70% improvement

Combined, these could reduce typical workflows from 8-12s to 2-3s (75% faster) with minimal complexity.

The session daemon (Phase 3) offers the ultimate performance but requires significant architectural changes.

---

**Last Updated:** 2025-10-23
**Status:** Category caching implemented, other optimizations pending
