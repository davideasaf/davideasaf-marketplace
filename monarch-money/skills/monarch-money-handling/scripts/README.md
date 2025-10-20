# Monarch Money TypeScript Scripts

These TypeScript scripts provide a command-line interface to the Monarch Money API using the [monarchmoney-ts](https://github.com/keithah/monarchmoney-ts) library.

## Setup

1. **Install dependencies:**
   ```bash
   cd .claude/skills/monarch-money-handling
   npm install
   ```

2. **Set environment variables:**
   ```bash
   export MONARCH_EMAIL="your-email@example.com"
   export MONARCH_PASSWORD="your-password"
   ```

   Or create a `.env` file in this directory:
   ```
   MONARCH_EMAIL=your-email@example.com
   MONARCH_PASSWORD=your-password
   ```

## Available Scripts

### Find Transaction

Find transactions by ID or by search criteria (date, merchant).

```bash
# Find by transaction ID
npm run find -- --id <transaction_id>

# Find by date and merchant
npm run find -- --date 2024-10-18 --merchant "Walmart"

# Find by date range
npm run find -- --start-date 2024-10-01 --end-date 2024-10-18 --merchant "Amazon"

# Limit results
npm run find -- --date 2024-10-18 --limit 50
```

**Direct usage:**
```bash
tsx scripts/find_transaction.ts --id <transaction_id>
tsx scripts/find_transaction.ts --date 2024-10-18 --merchant "Walmart"
```

### Get Categories

Retrieve all transaction categories and category groups.

```bash
# List format (human-readable)
npm run categories

# JSON format
npm run categories -- --format json
```

**Direct usage:**
```bash
tsx scripts/get_categories.ts
tsx scripts/get_categories.ts --format json
```

### Split Transaction

Split a transaction into multiple categories (perfect for itemized receipts).

```bash
# Using JSON string
npm run split -- <transaction_id> --splits-json '[
  {"merchantName": "Walmart Groceries", "amount": -50.00, "categoryId": "123"},
  {"merchantName": "Walmart Household", "amount": -25.50, "categoryId": "456"}
]'

# Using JSON file
npm run split -- <transaction_id> --splits-file splits.json

# Clear all splits (revert to single transaction)
npm run split -- <transaction_id> --clear
```

**Example splits.json:**
```json
[
  {
    "merchantName": "Walmart Groceries",
    "amount": -125.50,
    "categoryId": "cat_groceries_id",
    "notes": "Milk, eggs, bread"
  },
  {
    "merchantName": "Walmart Household",
    "amount": -45.25,
    "categoryId": "cat_household_id",
    "notes": "Paper towels, detergent"
  }
]
```

**Direct usage:**
```bash
tsx scripts/split_transaction.ts <transaction_id> --splits-json '[...]'
tsx scripts/split_transaction.ts <transaction_id> --splits-file splits.json
tsx scripts/split_transaction.ts <transaction_id> --clear
```

### Add Notes

Add or update notes on a transaction.

```bash
# Add notes
npm run notes -- <transaction_id> "Receipt items: milk, eggs, bread"

# Clear notes
npm run notes -- <transaction_id> --clear
```

**Direct usage:**
```bash
tsx scripts/add_notes.ts <transaction_id> "Your note text here"
tsx scripts/add_notes.ts <transaction_id> --clear
```

### Update Transaction

Update various transaction fields.

```bash
# Update category
npm run update -- <transaction_id> --category <category_id>

# Update merchant name
npm run update -- <transaction_id> --merchant "New Merchant Name"

# Update amount
npm run update -- <transaction_id> --amount -123.45

# Update date
npm run update -- <transaction_id> --date 2024-10-18

# Update flags
npm run update -- <transaction_id> --hide-from-reports true
npm run update -- <transaction_id> --needs-review false

# Multiple fields at once
npm run update -- <transaction_id> --category <id> --merchant "Walmart" --notes "Receipt breakdown"
```

**Direct usage:**
```bash
tsx scripts/update_transaction.ts <transaction_id> --category <category_id>
tsx scripts/update_transaction.ts <transaction_id> --merchant "New Name"
```

## Authentication

All scripts support authentication via:

1. **Environment variables** (recommended):
   - `MONARCH_EMAIL`
   - `MONARCH_PASSWORD`

2. **Command-line arguments**:
   ```bash
   tsx scripts/find_transaction.ts --email "user@example.com" --password "pass" --id <id>
   ```

## Common Workflows

### Receipt Categorization Workflow

When you have an itemized receipt (e.g., from Walmart) and want to split it into categories:

1. **Find the transaction:**
   ```bash
   npm run find -- --date 2024-10-18 --merchant "Walmart"
   ```

2. **Get available categories:**
   ```bash
   npm run categories
   ```

3. **Create splits JSON file:**
   Create `walmart_splits.json`:
   ```json
   [
     {"merchantName": "Walmart Groceries", "amount": -125.50, "categoryId": "cat_123"},
     {"merchantName": "Walmart Household", "amount": -45.25, "categoryId": "cat_456"},
     {"merchantName": "Walmart Health", "amount": -35.00, "categoryId": "cat_789"}
   ]
   ```

4. **Split the transaction:**
   ```bash
   npm run split -- <transaction_id> --splits-file walmart_splits.json
   ```

5. **Add notes (optional):**
   ```bash
   npm run notes -- <transaction_id> "Receipt breakdown: groceries (milk, eggs), household (towels, soap), health (vitamins)"
   ```

## Error Handling

All scripts:
- Exit with code 0 on success
- Exit with code 1 on errors
- Print errors to stderr
- Print results to stdout (JSON format)

**Example error checking in bash:**
```bash
if npm run find -- --id "12345"; then
  echo "Success!"
else
  echo "Failed to find transaction"
fi
```

## TypeScript Development

**Build scripts:**
```bash
npm run build
```

This compiles TypeScript to JavaScript in the `dist/` directory.

**Run directly with tsx (no build needed):**
```bash
tsx scripts/find_transaction.ts --help
```

## Debugging

Enable debug output:
```bash
DEBUG=monarchmoney:* npm run find -- --id <transaction_id>
```

## Notes

- Split amounts must sum exactly to the original transaction amount (within 0.01 tolerance)
- Transaction IDs can be found using the `find_transaction.ts` script
- Category IDs can be found using the `get_categories.ts` script
- Dates should be in `YYYY-MM-DD` format
- Amounts should be negative for expenses, positive for income

## Migration from Python Scripts

If you were using the deprecated Python scripts:

| Old Python Script | New TypeScript Script | npm Command |
|------------------|----------------------|-------------|
| `find_transaction.py` | `find_transaction.ts` | `npm run find` |
| `get_categories.py` | `get_categories.ts` | `npm run categories` |
| `split_transaction.py` | `split_transaction.ts` | `npm run split` |
| `add_notes.py` | `add_notes.ts` | `npm run notes` |
| `update_transaction.py` | `update_transaction.ts` | `npm run update` |

All functionality is preserved with improved reliability using the TypeScript SDK.
