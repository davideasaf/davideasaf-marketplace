# Root Cause Analysis: Categories API 400 Error

**Date:** October 19, 2025
**Issue:** `get_categories.ts` script returning 400 Bad Request
**Status:** ✅ RESOLVED

## Problem Summary

The `npm run categories` command was failing with a 400 Bad Request error when attempting to fetch transaction categories and category groups from Monarch Money's GraphQL API.

## Investigation Process

### 1. Error Reproduction
- ✅ Confirmed error occurs consistently
- ❌ `getTransactionCategories()` returns 400 Bad Request
- ❌ `getTransactionCategoryGroups()` returns 400 Bad Request

### 2. SDK Analysis
Examined the monarchmoney TypeScript SDK implementation and found it was using these queries:

**Failed Query #1:**
```graphql
query GetCategories {
  categories {
    id
    name
    icon
    color
    group {
      id
      name
      type
    }
    systemCategory
    isHidden
  }
}
```

**Failed Query #2:**
```graphql
query GetCategoryGroups {
  categoryGroups {
    id
    name
    type
    categories {
      id
      name
      icon
      color
    }
  }
}
```

### 3. Browser Network Inspection
Captured actual working GraphQL request from Monarch Money web app:

**Working Query:**
```graphql
query ManageGetCategoryGroups {
  categoryGroups {
    id
    name
    order
    type
    __typename
  }
  categories(includeDisabledSystemCategories: true) {
    id
    name
    order
    icon
    isSystemCategory
    systemCategory
    isDisabled
    group {
      id
      type
      name
      __typename
    }
    __typename
  }
}
```

## Root Cause

**The Monarch Money GraphQL API schema changed**, requiring:

1. **Query parameter on `categories`**: Must include `includeDisabledSystemCategories: true`
2. **Additional fields**: `order`, `isSystemCategory`, `isDisabled`, `__typename`
3. **Operation name**: Uses `ManageGetCategoryGroups` instead of separate queries

The monarchmoney-ts SDK (v1.1.3) uses an **outdated schema** that doesn't match the current API requirements.

## Solution

Updated `scripts/get_categories.ts` to use the working browser query directly:

```typescript
async function getCategories(mm: MonarchClient) {
  // Use the actual browser query that works
  const browserQuery = `
    query ManageGetCategoryGroups {
      categoryGroups {
        id
        name
        order
        type
        __typename
      }
      categories(includeDisabledSystemCategories: true) {
        id
        name
        order
        icon
        isSystemCategory
        systemCategory
        isDisabled
        group {
          id
          type
          name
          __typename
        }
        __typename
      }
    }
  `;

  const result = await mm['graphql'].query(browserQuery);

  return {
    categories: result.categories,
    categoryGroups: result.categoryGroups,
  };
}
```

## Test Results

After implementing the fix:

```bash
$ npm run categories
✅ Successfully returns 80 categories
✅ Successfully returns 16 category groups
✅ Human-readable format works
✅ JSON format works
```

## Key Learnings

1. **Browser DevTools are essential**: When SDK methods fail, inspect actual browser requests
2. **API schemas evolve**: GraphQL APIs can change field requirements without versioning
3. **Direct GraphQL access**: The SDK's GraphQL client can be accessed directly via `mm['graphql'].query()`
4. **Parameter requirements**: The `includeDisabledSystemCategories: true` parameter was critical

## Prevention

For future API issues:
1. Always check browser network requests first
2. Compare SDK queries with actual working browser queries
3. Maintain our own working queries independently of SDK updates
4. Consider contributing fixes back to the monarchmoney-ts repository

## Related Files

- Fixed: `scripts/get_categories.ts`
- Debug scripts:
  - `scripts/debug_categories.ts`
  - `scripts/debug_categories_v2.ts`
  - `scripts/test_browser_query.ts`

## Next Steps

- [x] Fix implemented and tested
- [ ] Consider submitting PR to monarchmoney-ts repository
- [ ] Monitor for other SDK methods that might have similar issues
- [ ] Document this pattern for future troubleshooting
