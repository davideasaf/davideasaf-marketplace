---
name: monarch-money
description: 'Use this single consolidated skill for Monarch Money transaction management: find transactions, list categories, split receipts, categorize or update transactions, add itemized notes, review needs-review transactions, and process Amazon refunds. Trigger this for any Monarch Money, budgeting transaction, receipt splitting, refund review, or transaction categorization request.'
version: '1.0.3'
---

# Monarch Money

This is the user-facing skill for managing Monarch Money data. Use it for receipt splitting, transaction search, categorization, transaction updates, notes, review cleanup, and Amazon refund workflows.

Do not surface generic dependency skills such as dotenv or dotenvx as separate Monarch capabilities. Environment handling is only implementation detail for this skill.

## Working Directory

Run commands from the directory that contains this `SKILL.md` file:

```bash
cd <path-to-this-skill-directory>
```

## Authentication

The scripts use a saved Monarch session when available and fall back to environment variables when needed:

- `MONARCH_EMAIL`
- `MONARCH_PASSWORD`
- `MONARCH_MFA_SECRET` when MFA is required

Never print secret values. If auth fails, report which variable names are missing or invalid, not their values.

## Default Operating Rules

- Prefer the existing TypeScript scripts over ad hoc API calls.
- Reuse cached categories unless the user asks to refresh or a category is missing.
- For expenses, amounts are negative.
- For receipt splits, every split must include itemized `notes`.
- Validate split files before applying them.
- Search by transaction ID when available; otherwise use date, merchant, and amount.
- Use saved sessions and batch scripts when possible to avoid repeated logins.
- Before mutating data, make sure the target transaction ID, amount, and intended category are clear.
- For ambiguous category decisions, ask the user instead of guessing.

## Primary Commands

| Task | Command |
| --- | --- |
| Find transactions | `npm run find -- --date YYYY-MM-DD --merchant "Merchant"` |
| Find by ID | `npm run find -- --id "<transaction_id>"` |
| List categories | `npm run categories` |
| Refresh categories | `npm run categories -- --refresh` |
| Validate splits | `npm run validate -- --splits-file /tmp/splits.json --amount -40.91` |
| Split receipt and add notes | `npm run split-receipt -- <transaction_id> --splits-file /tmp/splits.json` |
| Add or replace notes | `npm run notes -- <transaction_id> $'Category:\n- Item - $12.34'` |
| Update transaction fields | `npm run update -- <transaction_id> --category <category_id>` |
| Manage tags | `npm run tags -- --list` |
| Bulk update transactions | `npm run bulk-update -- --updates-file /tmp/updates.json` |
| Coordinate Amazon refund review | `npm run batch-refunds -- --days 14` |
| Scrape Amazon refunds | `npm run amazon-scrape -- --headless` |
| Scrape Amazon refunds with items | `npm run amazon-scrape-items -- --headless` |

## Receipt Splitting Workflow

1. Find the matching Monarch transaction.
2. Analyze the receipt and group items by spending category.
3. Run `npm run categories` to get category IDs.
4. Create a split JSON file with one object per category.
5. Run `npm run validate` and fix any mismatches.
6. Run `npm run split-receipt`.

Split JSON shape:

```json
[
  {
    "merchantName": "Walmart",
    "amount": -20.78,
    "categoryId": "223967675759308363",
    "notes": "Groceries:\n- Milk - $4.37\n- Eggs - $5.46\nTotal: $9.83"
  }
]
```

Split amounts must sum to the original transaction within one cent. Include tax, discounts, and delivery fees in the category totals when needed.

## Transaction Review Workflow

Use this when the user wants to clean up uncategorized or needs-review transactions.

1. Pull only the relevant transaction set, honoring user exclusions first.
2. Group results into high-confidence updates, rule candidates, transfer/payment items, and ambiguous items.
3. Apply only changes the user clearly authorized.
4. Present ambiguous items in small batches with merchant, date, amount, current category, suggested category, and reason.
5. After decisions, update the transactions and capture reusable decisions when useful.

If the current workspace includes durable finance memory, household notes, or transaction-review rules, consult those before asking about ambiguous items. Use local context as decision support only; prefer precise raw Plaid patterns over broad cleaned merchant names.

## Amazon Refund Workflow

Start from Monarch Money, not Amazon:

1. Find Amazon refund transactions, usually positive amounts with `needsReview`.
2. Scrape Amazon order details only for the matching refunds.
3. Infer categories from item names.
4. Add itemized notes and update the transaction category.
5. Mark items reviewed only when the update is correct.

Use dry run first for batch refund work unless the user explicitly asks to apply changes immediately.

## Notes Formatting

Use simple newline notes. When passing notes in shell commands, prefer `$'...\n...'` syntax. If notes contain dollar signs, quote carefully so the shell does not expand them.

Good note style:

```text
Groceries:
- Milk - $4.37
- Eggs - $5.46
Total: $9.83
```

## Troubleshooting

- Auth failures: check `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and `MONARCH_MFA_SECRET`.
- Category missing: refresh with `npm run categories -- --refresh`.
- Split mismatch: rerun `npm run validate` and reconcile tax/fees/discounts.
- Notes lost dollar signs: fix shell quoting.
- GraphQL 400/401/403 or missing fields: treat as Monarch web API drift.

When GraphQL drift is likely:

1. Check `.cache/graphql-failures/`.
2. Compare against the current Monarch web GraphQL request.
3. Patch the relevant script to match the browser operation and response shape.
4. Validate read-only commands before running mutations.

## Reference Docs

Use these only when the task requires detail:

- `SCRIPTS_REFERENCE.md`
- `FORMATTING_GUIDE.md`
- `TROUBLESHOOTING.md`
- `scripts/README.md`

Historical investigation notes live in `docs/archive/`.
