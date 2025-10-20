# Troubleshooting

Common issues and solutions for Monarch Money skills.

## Table of Contents

- [Authentication Issues](#authentication-issues)
- [Split Amount Errors](#split-amount-errors)
- [Dollar Signs in Notes](#dollar-signs-in-notes)
- [Business Category Errors](#business-category-errors)
- [Transaction Not Found](#transaction-not-found)
- [Category Cache Issues](#category-cache-issues)

---

## Authentication Issues

### Problem: "Error logging in" or "Invalid credentials"

**Symptoms:**
```
Error logging in: Authentication failed
Error: Invalid email or password
```

**Solutions:**

1. **Verify environment variables are set:**
   ```bash
   echo $MONARCH_EMAIL
   echo $MONARCH_PASSWORD
   ```

2. **Test login at monarchmoney.com manually**
   - Ensure credentials work in browser
   - Check for special characters that might need escaping

3. **Check .env file (if using):**
   ```bash
   cat .env
   ```
   Should contain:
   ```
   MONARCH_EMAIL=your-email@example.com
   MONARCH_PASSWORD=your-password
   ```

4. **Ensure environment variables are exported:**
   ```bash
   export MONARCH_EMAIL="your-email@example.com"
   export MONARCH_PASSWORD="your-password"
   ```

5. **Special characters in password:**
   - Use quotes around password in .env file
   - Escape special characters if needed
   - Consider changing password to avoid special characters

### Problem: Session expired

**Symptoms:**
```
Error: Session expired or invalid
Error: Unauthorized (401)
```

**Solution:**

The SDK caches sessions. If sessions expire frequently:
1. Re-run the script (will re-authenticate automatically)
2. Check if password changed recently
3. Verify 2FA is not enabled (not currently supported)

---

## Split Amount Errors

### Problem: "Split amounts must sum to original transaction amount"

**Symptoms:**
```
Error: Split amounts (-40.90) don't match original transaction (-40.91)
Difference: 0.01
```

**Root Causes:**

1. **Rounding errors:** Splitting by percentages can cause penny differences
2. **Missing items:** Not all receipt items included in splits
3. **Tax distribution:** Tax not proportionally distributed across categories
4. **Calculation errors:** Manual math mistakes

**Solutions:**

1. **Use validation before executing:**
   ```bash
   npm run validate -- --splits-file splits.json --amount -40.91
   ```

2. **Check receipt total matches transaction:**
   - Receipt total: $40.91
   - Transaction amount: -$40.91 (negative for expenses)
   - Ensure they match exactly

3. **Account for all items:**
   - List all receipt items with prices
   - Group by category
   - Calculate subtotals
   - Verify subtotals sum to total

4. **Distribute tax proportionally:**
   ```
   Item A: $10.00 (pre-tax)
   Item B: $20.00 (pre-tax)
   Tax: $1.50

   Item A portion: (10/30) * 1.50 = $0.50 → Total: $10.50
   Item B portion: (20/30) * 1.50 = $1.00 → Total: $21.00
   ```

5. **Allow $0.01 tolerance:**
   - Validation allows ±$0.01 difference
   - If off by one penny, adjust largest split by $0.01

---

## Dollar Signs in Notes

### Problem: Dollar signs disappearing from notes

**Symptoms:**
```bash
# Input:  "Milk $4.50, Eggs $3.20"
# Output: "Milk 4.50, Eggs 3.20"
```

**Root Cause:**

Bash interprets `$` as variable expansion when using double quotes.

**Solution:**

**✅ Use single quotes:**
```bash
npm run notes -- <id> 'Milk $4.50, Eggs $3.20'
```

**❌ Don't use double quotes:**
```bash
npm run notes -- <id> "Milk $4.50, Eggs $3.20"  # Wrong!
```

**Why it happens:**
```bash
# With double quotes, bash expands $4 and $3 as variables
echo "Milk $4.50"  # Outputs: Milk .50 (if $4 is empty)

# With single quotes, bash treats everything literally
echo 'Milk $4.50'  # Outputs: Milk $4.50 ✅
```

**Alternative for JSON files:**

When creating splits JSON files, use cat with heredoc:
```bash
cat > /tmp/splits.json << 'EOF'
[
  {
    "notes": "Milk $4.50, Eggs $3.20"
  }
]
EOF
```

Note the **single quotes** around `'EOF'` - this prevents variable expansion.

---

## Business Category Errors

### Problem: Cryptic 400 error when splitting with certain categories

**Symptoms:**
```
Error: 400 Bad Request
Error: GraphQL error (no detailed message)
Split fails but validation passes
```

**Root Cause:**

Business categories cannot be used for transaction splits. These include:
- Postage & Shipping
- Office Supplies
- Business Expenses
- Advertising & Marketing

**Solution:**

1. **Use General Shopping instead:**
   ```bash
   # Get categories to find General Shopping ID
   npm run categories

   # Look for: General Shopping (ID: 223967675759308371)
   ```

2. **Check category type before using:**
   ```bash
   npm run categories -- --format json
   ```

   Look for `"type": "Business"` in the output. Avoid these categories for splits.

3. **Validation warning:**

   The validate script warns about Business categories:
   ```
   ⚠️  Warning: Split 2 uses a Business category which may cause errors
   ```

**Why this happens:**

Monarch Money's API restricts Business categories from being used in split transactions. The restriction is enforced at the API level, not documented in the SDK.

---

## Transaction Not Found

### Problem: Cannot find transaction by ID

**Symptoms:**
```
Error: Transaction with ID 123456789 not found
Transaction returned null
```

**Solutions:**

1. **Verify transaction ID is correct:**
   - IDs are long numeric strings (e.g., "224897271489997895")
   - Check for typos or truncation

2. **Search by date and merchant instead:**
   ```bash
   npm run find -- --date 2025-10-16 --merchant "Walmart"
   ```

3. **Check date range:**

   By default, searches look at recent transactions. If transaction is old:
   ```bash
   npm run find -- --start-date 2025-01-01 --end-date 2025-12-31
   ```

4. **Verify transaction exists in Monarch Money:**
   - Log into monarchmoney.com
   - Check if transaction is visible
   - Ensure account sync completed

5. **Check account access:**
   - Transaction might be in account you don't have access to
   - Verify multi-user permissions

---

## Category Cache Issues

### Problem: Category not found but it exists in Monarch Money

**Symptoms:**
```
Error: Invalid category ID: 223967675759308999
Category validation failed
```

**Cause:**

Category cache is outdated. New categories added since last cache refresh.

**Solution:**

1. **Refresh category cache:**
   ```bash
   npm run categories -- --refresh
   ```

2. **Verify category exists:**
   ```bash
   npm run categories
   ```

   Look for the category name and ID in output.

3. **Check for typos in category ID:**
   - IDs are 18-digit numbers
   - Easy to transpose digits
   - Copy-paste from `npm run categories` output

### Problem: Cache file corrupted

**Symptoms:**
```
Error: Cannot parse categories cache
Error: Unexpected token in JSON
```

**Solution:**

1. **Delete cache and refresh:**
   ```bash
   rm .cache/categories.json
   npm run categories -- --refresh
   ```

2. **Check cache file:**
   ```bash
   cat .cache/categories.json
   ```

   Should be valid JSON. If corrupted, delete and refresh.

---

## Performance Issues

### Problem: Scripts are slow

**Symptoms:**
- Commands take >5 seconds to complete
- Multiple API calls for same data

**Solutions:**

1. **Use category cache (default):**
   ```bash
   # Fast (uses cache)
   npm run categories

   # Slow (hits API)
   npm run categories -- --refresh
   ```

2. **Batch operations instead of loops:**

   **❌ Slow (multiple logins):**
   ```bash
   for id in txn_1 txn_2 txn_3; do
     npm run update -- "$id" --category "cat_id"
   done
   ```

   **✅ Fast (single login, bulk update):**
   Create a script for bulk updates or use split functionality for related transactions.

3. **Check network connection:**
   - Slow API responses may indicate network issues
   - VPN can slow down requests
   - Monarch Money API outages (rare)

---

## GraphQL Errors

### Problem: Generic GraphQL errors

**Symptoms:**
```
Error: GraphQL request failed
Error: Unexpected error from API
```

**Solutions:**

1. **Check ROOT_CAUSE_ANALYSIS.md:**

   The skill uses custom GraphQL queries that differ from the SDK defaults. See [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md) for details.

2. **Verify you're using correct query:**
   - Category queries: `ManageGetCategoryGroups`
   - Split queries: `updateTransactionSplit`
   - Note queries: `bulkUpdateTransactions`

3. **Check Monarch Money API status:**
   - Try logging into monarchmoney.com
   - Verify web interface is working
   - Check for maintenance notifications

---

## Validation Warnings

### Warning: Missing notes field

**Message:**
```
⚠️  Warning: Split 2 is missing notes field (recommended for all splits)
```

**Why it matters:**

Notes provide itemized details for each split, making it easier to:
- Understand what items are in each category
- Review spending later
- Track specific purchases

**Solution:**

Always include `notes` field in splits:
```json
{
  "merchantName": "Walmart",
  "amount": -20.78,
  "categoryId": "223967675759308363",
  "notes": "Groceries: Milk $4.50, Eggs $3.20, Bread $2.80"
}
```

---

## Getting More Help

If you encounter an error not covered here:

1. **Check script comments:**
   - Each script in `scripts/` has detailed usage in header
   - Look for examples and edge cases

2. **Review ROOT_CAUSE_ANALYSIS.md:**
   - Technical details about API implementation
   - Known SDK limitations
   - Working GraphQL queries

3. **Enable debug output:**
   ```bash
   # Run script with debug logging
   DEBUG=* npm run find -- --date 2025-10-16
   ```

4. **Check Monarch Money SDK issues:**
   - https://github.com/keithah/monarchmoney-ts/issues
   - May be known SDK bugs or API changes

5. **Test with minimal example:**
   - Isolate the problem
   - Try simplest possible operation
   - Rule out environmental issues

---

## Common Workflow Issues

### Issue: Receipt split fails validation but amounts are correct

**Check:**
1. Negative amounts for expenses (e.g., `-40.91` not `40.91`)
2. All category IDs exist (run `npm run categories`)
3. No Business categories used
4. JSON file is valid (use `cat splits.json` to verify)

### Issue: Split succeeds but notes missing

**Cause:**

Using legacy `split_transaction.ts` instead of `split_and_annotate.ts`.

**Solution:**

Use the primary split tool:
```bash
npm run split-receipt -- <id> --splits-file splits.json
```

Not:
```bash
npm run split -- <id> --splits-file splits.json  # Legacy, no notes
```

---

## Quick Diagnostic Checklist

When something goes wrong, check these in order:

- [ ] Environment variables set (`MONARCH_EMAIL`, `MONARCH_PASSWORD`)
- [ ] Can log into monarchmoney.com with same credentials
- [ ] Category cache up to date (`npm run categories -- --refresh`)
- [ ] Transaction ID is correct (use `npm run find` to search)
- [ ] Using single quotes for notes with `$` symbols
- [ ] Split amounts sum to original transaction
- [ ] Not using Business categories for splits
- [ ] JSON files are valid (no syntax errors)
- [ ] Using latest version of skill scripts

If all checks pass and issue persists, see [Getting More Help](#getting-more-help) section.
