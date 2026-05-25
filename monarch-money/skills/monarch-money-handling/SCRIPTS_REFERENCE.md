# Scripts Reference

This is the current command reference for the Monarch Money skill.

## Authentication

Scripts use a saved Monarch session when possible. If no valid session exists, set:

- `MONARCH_EMAIL`
- `MONARCH_PASSWORD`
- `MONARCH_MFA_SECRET` when MFA is required

Never print or commit secret values.

## Transaction Lookup

```bash
npm run find -- --id <transaction_id>
npm run find -- --date YYYY-MM-DD --merchant "Merchant"
npm run find -- --start-date YYYY-MM-DD --end-date YYYY-MM-DD --merchant "Merchant"
npm run find -- --date YYYY-MM-DD --limit 50
```

Use ID lookup when available. It is faster and avoids merchant normalization ambiguity.

## Categories

```bash
npm run categories
npm run categories -- --format json
npm run categories -- --refresh
```

Categories are cached in `.cache/categories.json`. Use `--refresh` after category changes.

## Updates

```bash
npm run update -- <transaction_id> --category <category_id>
npm run update -- <transaction_id> --merchant "Merchant"
npm run update -- <transaction_id> --notes $'Line 1\nLine 2'
npm run update -- <transaction_id> --needs-review false
npm run notes -- <transaction_id> $'Line 1\nLine 2'
```

For broad cleanup work, update only rows where the target ID and intended fields are clear.

## Tags

```bash
npm run tags -- --list
npm run tags -- --create "Tag Name" --color "#00A2C7"
npm run tags -- --add <transaction_id> --tags <tag_id>
npm run tags -- --set <transaction_id> --tags <tag_id_1,tag_id_2>
```

Use `--add` to preserve existing tags. Use `--set` only when replacing the full tag list is intentional.

## Splits

```bash
npm run validate -- --splits-file /tmp/splits.json --amount -40.91
npm run split-receipt -- <transaction_id> --splits-file /tmp/splits.json
npm run split-receipt -- <transaction_id> --clear
```

Split file shape:

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

Validation checks required fields, category IDs, and whether the split total matches the source transaction.

## Bulk Updates

```bash
npm run bulk-update -- --updates-file /tmp/updates.json
```

Prefer the single-transaction `update` command unless the update set is already reviewed and deterministic.

## Amazon Refund Workflows

```bash
npm run batch-refunds -- --days 14
npm run batch-refunds -- --start-date YYYY-MM-DD --end-date YYYY-MM-DD
npm run amazon-scrape -- --headless
npm run amazon-scrape-items -- --headless
```

Amazon workflows are reconciliation helpers. Do not mark refunds reviewed unless the item/order mapping is clear.

## GraphQL Drift

The current implementation uses `scripts/utils/monarch_graphql.ts` for web-compatible GraphQL calls in key scripts. On schema failures:

1. Inspect `.cache/graphql-failures/`.
2. Reproduce the action in Monarch web.
3. Compare the browser GraphQL request with the script query or mutation.
4. Patch the script and validate read-only commands before retrying mutations.
