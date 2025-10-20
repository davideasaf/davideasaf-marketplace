# Scripts Reference

Detailed documentation for all available Monarch Money scripts.

## Table of Contents

- [Find Transaction](#find-transaction)
- [Get Categories](#get-categories)
- [Validate Splits](#validate-splits)
- [Split and Annotate](#split-and-annotate)
- [Add Notes](#add-notes)
- [Update Transaction](#update-transaction)

---

## Find Transaction

**Script:** `scripts/find_transaction.ts`

**Purpose:** Search for transactions by date, merchant, amount, or ID.

### Usage

```bash
# By date and merchant
npm run find -- --date YYYY-MM-DD --merchant "Name"

# By date range
npm run find -- --start-date YYYY-MM-DD --end-date YYYY-MM-DD

# By transaction ID
npm run find -- --id "transaction_id"

# By amount (exact or range)
npm run find -- --amount -40.91
npm run find -- --min-amount -50 --max-amount -30
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--date` | YYYY-MM-DD | Search for transactions on specific date |
| `--start-date` | YYYY-MM-DD | Start of date range (requires --end-date) |
| `--end-date` | YYYY-MM-DD | End of date range (requires --start-date) |
| `--merchant` | string | Merchant name (partial match, case-insensitive) |
| `--id` | string | Transaction ID (exact match) |
| `--amount` | number | Transaction amount (exact match) |
| `--min-amount` | number | Minimum amount for range search |
| `--max-amount` | number | Maximum amount for range search |

### Output

Returns transaction details including:
- Transaction ID
- Date
- Merchant name
- Amount
- Category
- Notes
- Account information

### Examples

```bash
# Find recent Walmart transaction
npm run find -- --date 2025-10-16 --merchant "Walmart"

# Find all transactions in October
npm run find -- --start-date 2025-10-01 --end-date 2025-10-31

# Find transaction by ID
npm run find -- --id "224897271489997895"
```

---

## Get Categories

**Script:** `scripts/get_categories.ts`

**Purpose:** List all available budget categories with IDs. Uses local cache by default.

### Usage

```bash
# Human-readable list (uses cache)
npm run categories

# JSON format with all metadata (uses cache)
npm run categories -- --format json

# Force refresh from API
npm run categories -- --refresh
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--format` | text \| json | Output format (default: text) |
| `--refresh` | boolean | Force refresh from API, bypass cache |

### Caching Behavior

- **First run:** Fetches from API and saves to `.cache/categories.json`
- **Subsequent runs:** Uses cache (instant, no API call)
- **Refresh:** Only when `--refresh` flag is provided

Categories rarely change, so caching dramatically speeds up workflows.

### Output

**Text format:**
```
Income
  - Paycheck (ID: 223967675759308360)
  - Investment Income (ID: 223967675759308361)

Spending
  - Groceries (ID: 223967675759308363)
  - Dining Out (ID: 223967675759308364)
  ...
```

**JSON format:**
```json
{
  "categoryGroups": [
    {
      "id": "group_id",
      "name": "Income",
      "categories": [
        {
          "id": "223967675759308360",
          "name": "Paycheck",
          "icon": "💰"
        }
      ]
    }
  ]
}
```

### Examples

```bash
# Quick lookup for receipt splitting
npm run categories

# Get full category metadata
npm run categories -- --format json

# Update cache after adding new categories
npm run categories -- --refresh
```

---

## Validate Splits

**Script:** `scripts/validate_splits.ts`

**Purpose:** Pre-flight validation of splits before executing. Catches errors early.

### Usage

```bash
# Validate splits file
npm run validate -- --splits-file splits.json --amount -40.91

# Validate without amount check
npm run validate -- --splits-file splits.json
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--splits-file` | path | Yes | Path to JSON file with splits |
| `--amount` | number | No | Expected total amount to validate against |

### Validations Performed

1. **Required Fields:** All splits have merchantName, amount, categoryId
2. **Amount Sum:** Splits sum to expected total (within $0.01 tolerance)
3. **Category IDs:** All category IDs exist in Monarch Money
4. **Business Categories:** Warns about Business category usage (often causes errors)
5. **Notes:** Warns if notes field is missing (recommended for all splits)

### Output

**Success:**
```
Split Summary:
  Total splits: 2
  Sum of amounts: -40.91
  Expected amount: -40.91
  Difference: 0.00

✅ All validations passed!
```

**Failure:**
```
❌ Validation failed:
  - Amount mismatch: Expected -40.91, got -40.90 (diff: 0.01)
  - Invalid category ID: 999999999 (not found in cache)
  - Split 2 is missing notes field
```

### Examples

```bash
# Validate before executing split
npm run validate -- --splits-file /tmp/splits.json --amount -40.91

# Check split structure without amount validation
npm run validate -- --splits-file /tmp/splits.json
```

---

## Split and Annotate

**Script:** `scripts/split_and_annotate.ts`

**Purpose:** Split a transaction into multiple category-specific transactions AND add itemized notes. This is the primary tool for receipt splitting.

### Usage

```bash
# Split transaction with notes
npm run split-receipt -- <transaction_id> --splits-file splits.json

# Clear existing splits
npm run split-receipt -- <transaction_id> --clear
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transaction_id` | string | Yes | ID of transaction to split |
| `--splits-file` | path | No* | Path to JSON file with splits (*required unless --clear) |
| `--clear` | boolean | No | Remove all splits, restore original transaction |

### Splits File Format

```json
[
  {
    "merchantName": "Walmart",
    "amount": -20.78,
    "categoryId": "223967675759308363",
    "notes": "Groceries: Crackers $3.88, Cottage cheese $3.24, Milk $4.37, Eggs $5.46"
  },
  {
    "merchantName": "Walmart",
    "amount": -20.13,
    "categoryId": "223967675759308371",
    "notes": "Halloween: Glow items $9.84; Shipping: Boxes $4.08"
  }
]
```

### Requirements

- ✅ Amounts must sum to original transaction amount
- ✅ Each split must have merchantName, amount, categoryId
- ✅ **ALWAYS include notes field** with itemized prices
- ✅ Use negative amounts for expenses
- ✅ Avoid Business categories (causes API errors)

### What Happens

1. Transaction is split into multiple transactions (one per split)
2. Each split gets assigned to its specified category
3. Notes are automatically added to each split transaction
4. Original transaction is preserved as parent
5. Returns array of new split transaction IDs

### Examples

```bash
# Split Walmart receipt by categories
cat > /tmp/splits.json << 'EOF'
[
  {
    "merchantName": "Walmart",
    "amount": -25.50,
    "categoryId": "223967675759308363",
    "notes": "Groceries: Milk $4.50, Eggs $3.20, Bread $2.80, Cheese $5.00, Apples $3.50, Bananas $2.50, Yogurt $4.00"
  },
  {
    "merchantName": "Walmart",
    "amount": -15.41,
    "categoryId": "223967675759308371",
    "notes": "Household: Paper towels $6.50, Dish soap $4.50, Sponges $4.41"
  }
]
EOF

npm run split-receipt -- 224897271489997895 --splits-file /tmp/splits.json

# Remove splits and restore original
npm run split-receipt -- 224897271489997895 --clear
```

---

## Add Notes

**Script:** `scripts/add_notes.ts`

**Purpose:** Add or update notes on a single transaction.

### Usage

```bash
# Add/update notes
npm run notes -- <transaction_id> 'Note text with $prices'

# Clear notes
npm run notes -- <transaction_id> --clear
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `transaction_id` | string | Yes | ID of transaction |
| `note_text` | string | No* | Note content (*required unless --clear) |
| `--clear` | boolean | No | Remove all notes from transaction |

### Important Notes

- **Use single quotes** when notes contain `$` symbols in bash
- Double quotes will cause bash to interpret `$` as variables
- Notes can be multi-line
- Existing notes are completely replaced (not appended)

### Examples

```bash
# Add itemized prices (use single quotes!)
npm run notes -- 224897271489997895 'Groceries: Milk $4.50, Eggs $3.20, Bread $2.80'

# Wrong: Double quotes will break $ symbols
npm run notes -- 224897271489997895 "Milk $4.50"  # ❌ Becomes "Milk 4.50"

# Multi-line notes
npm run notes -- 224897271489997895 'Groceries:
- Milk $4.50
- Eggs $3.20
- Bread $2.80'

# Clear notes
npm run notes -- 224897271489997895 --clear
```

---

## Update Transaction

**Script:** `scripts/update_transaction.ts`

**Purpose:** Update various fields of a transaction (category, merchant, amount, etc.).

### Usage

```bash
# Update category
npm run update -- <transaction_id> --category <category_id>

# Update merchant name
npm run update -- <transaction_id> --merchant "New Name"

# Update amount
npm run update -- <transaction_id> --amount -123.45

# Update multiple fields
npm run update -- <transaction_id> --category <cat_id> --merchant "Store" --notes "Note"
```

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `transaction_id` | string | ID of transaction to update |
| `--category` | string | New category ID |
| `--merchant` | string | New merchant name |
| `--amount` | number | New amount (negative for expenses) |
| `--date` | YYYY-MM-DD | New transaction date |
| `--notes` | string | New notes (use single quotes for $) |
| `--hide-from-reports` | boolean | Hide/show in reports |
| `--needs-review` | boolean | Mark for review |

### Examples

```bash
# Recategorize transaction
npm run update -- 224897271489997895 --category "223967675759308363"

# Fix merchant name typo
npm run update -- 224897271489997895 --merchant "Target"

# Update amount after refund
npm run update -- 224897271489997895 --amount -35.50

# Mark for review with note
npm run update -- 224897271489997895 --needs-review true --notes "Check this expense"

# Hide from reports
npm run update -- 224897271489997895 --hide-from-reports true
```

---

## Common Patterns

### Batch Update Multiple Transactions

```bash
# Update category for multiple transactions
for id in txn_123 txn_456 txn_789; do
  npm run update -- "$id" --category "new_category_id"
done
```

### Monthly Transaction Review

```bash
# Export all transactions for October
npm run find -- --start-date 2025-10-01 --end-date 2025-10-31 > october_transactions.json

# Review and categorize as needed
```

### Receipt Split Workflow

```bash
# 1. Find transaction
npm run find -- --date 2025-10-16 --merchant "Walmart"

# 2. Get categories (uses cache)
npm run categories

# 3. Create splits.json with itemized notes
# (See Split and Annotate section for format)

# 4. Validate before executing
npm run validate -- --splits-file splits.json --amount -40.91

# 5. Execute split with notes
npm run split-receipt -- <transaction_id> --splits-file splits.json
```

---

## Error Handling

All scripts follow consistent error handling:

- **Exit code 0:** Success
- **Exit code 1:** Error
- **stdout:** JSON results or formatted output
- **stderr:** Error messages and warnings

### Common Errors

**Authentication Failure:**
```
Error logging in: Invalid credentials
```
→ Check `MONARCH_EMAIL` and `MONARCH_PASSWORD` environment variables

**Transaction Not Found:**
```
Error: Transaction with ID 123456 not found
```
→ Verify transaction ID is correct (use `find` script to search)

**Category Not Found:**
```
Error: Invalid category ID: 999999
```
→ Use `npm run categories` to get valid category IDs

**Business Category Error:**
```
Error: 400 Bad Request (cryptic message)
```
→ Business categories can't be used for splits. Use General Shopping instead.

**Amount Mismatch:**
```
Error: Split amounts (-40.90) don't match original (-40.91)
```
→ Ensure splits sum exactly to original amount (within $0.01)

---

## Technical Details

### GraphQL Queries

The monarchmoney-ts SDK (v1.1.3) has outdated queries. This skill uses actual working browser queries:

- `ManageGetCategoryGroups` - for categories
- `updateTransactionSplit` - for splits
- `bulkUpdateTransactions` - for notes

See [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md) for implementation details.

### Session Management

- Sessions cached locally by SDK
- `useSavedSession: true` reduces login overhead
- First run requires full authentication
- Sessions persist across script runs

### Category Caching

- Categories stored in `.cache/categories.json`
- Cache used by default (instant lookups)
- Refresh only when categories change (rare)
- Validate script uses cache for category ID verification

---

## Resources

- **TypeScript SDK:** https://github.com/keithah/monarchmoney-ts
- **Monarch Money:** https://www.monarchmoney.com
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Root Cause Analysis:** [ROOT_CAUSE_ANALYSIS.md](ROOT_CAUSE_ANALYSIS.md)
