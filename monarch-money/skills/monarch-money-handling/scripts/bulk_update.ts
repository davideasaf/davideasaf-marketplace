#!/usr/bin/env tsx
/**
 * Bulk update multiple transactions at once
 *
 * Supports updating category, notes, and hideFromReports fields
 * for multiple transactions in a single operation.
 *
 * Usage:
 *   tsx scripts/bulk_update.ts --ids id1,id2,id3 --category <category_id>
 *   tsx scripts/bulk_update.ts --ids id1,id2,id3 --notes "Shared note"
 *   tsx scripts/bulk_update.ts --ids id1,id2,id3 --hide
 *   tsx scripts/bulk_update.ts --ids id1,id2,id3 --category <cat_id> --notes "Note"
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface BulkUpdateArgs {
  ids?: string;
  category?: string;
  notes?: string;
  hide?: boolean;
  unhide?: boolean;
  email?: string;
  password?: string;
}

async function main() {
  const { values } = parseArgs({
    options: {
      ids: { type: 'string' },
      category: { type: 'string' },
      notes: { type: 'string' },
      hide: { type: 'boolean', default: false },
      unhide: { type: 'boolean', default: false },
      email: { type: 'string' },
      password: { type: 'string' },
    },
  });

  const args = values as BulkUpdateArgs;

  // Validate inputs
  if (!args.ids) {
    console.error('Error: --ids required (comma-separated transaction IDs)');
    process.exit(1);
  }

  const transactionIds = args.ids.split(',').map(id => id.trim());

  if (transactionIds.length === 0) {
    console.error('Error: At least one transaction ID required');
    process.exit(1);
  }

  // Build updates object
  const updates: Record<string, any> = {};

  if (args.category) {
    updates.categoryId = args.category;
  }

  if (args.notes !== undefined) {
    updates.notes = args.notes;
  }

  if (args.hide) {
    updates.hideFromReports = true;
  } else if (args.unhide) {
    updates.hideFromReports = false;
  }

  if (Object.keys(updates).length === 0) {
    console.error('Error: At least one update field required (--category, --notes, --hide, --unhide)');
    process.exit(1);
  }

  // Initialize Monarch Money client
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });

  const email = args.email || process.env.MONARCH_EMAIL;
  const password = args.password || process.env.MONARCH_PASSWORD;

  if (!email || !password) {
    console.error('Error: Email and password required (via args or env vars)');
    process.exit(1);
  }

  try {
    await mm.login({ email, password, useSavedSession: true, saveSession: true });
  } catch (error) {
    console.error('Error logging in:', error);
    process.exit(1);
  }

  // Perform bulk update
  try {
    console.log(`Updating ${transactionIds.length} transactions...`);
    console.log('Updates:', JSON.stringify(updates, null, 2));

    const startTime = performance.now();

    const result = await mm.transactions.bulkUpdateTransactions({
      transactionIds,
      updates,
      allSelected: false,
    });

    const duration = performance.now() - startTime;

    console.log(`\n[PERF] Completed in ${duration.toFixed(2)}ms`);
    console.log(`\nSuccess: ${result.successful} transactions updated`);

    if (result.errors && result.errors.length > 0) {
      console.error(`\nErrors: ${result.errors.length} transactions failed`);
      result.errors.forEach((error: any) => {
        console.error(`  - ${error.field}: ${error.messages?.join(', ')}`);
      });
    }
  } catch (error) {
    console.error('Error performing bulk update:', error);
    process.exit(1);
  }
}

main();
