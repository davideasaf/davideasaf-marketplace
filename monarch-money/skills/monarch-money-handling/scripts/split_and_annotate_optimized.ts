#!/usr/bin/env tsx
/**
 * Split a transaction and add notes using parallel API calls
 *
 * Uses the SDK methods with parallel note updates.
 *
 * Usage:
 *   tsx scripts/split_and_annotate_optimized.ts <transaction_id> --splits-file splits.json
 *   tsx scripts/split_and_annotate_optimized.ts <transaction_id> --splits-json '[...]'
 *   tsx scripts/split_and_annotate_optimized.ts <transaction_id> --clear  # Remove splits
 */

import * as fs from 'node:fs';
import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';
import type { TransactionSplit } from 'monarchmoney';

interface SplitAndAnnotateArgs {
  'splits-json'?: string;
  'splits-file'?: string;
  clear?: boolean;
  email?: string;
  password?: string;
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      'splits-json': { type: 'string' },
      'splits-file': { type: 'string' },
      clear: { type: 'boolean', default: false },
      email: { type: 'string' },
      password: { type: 'string' },
    },
    allowPositionals: true,
  });

  const args = values as SplitAndAnnotateArgs;

  // Get transaction ID from positional argument
  if (positionals.length === 0) {
    console.error('Error: Transaction ID required as first argument');
    process.exit(1);
  }

  const transactionId = positionals[0];

  // Parse splits
  let splits: TransactionSplit[] = [];

  if (args.clear) {
    splits = [];
  } else if (args['splits-json']) {
    try {
      splits = JSON.parse(args['splits-json']);
    } catch (error) {
      console.error('Error parsing splits JSON:', error);
      process.exit(1);
    }
  } else if (args['splits-file']) {
    try {
      const fileContent = fs.readFileSync(args['splits-file'], 'utf-8');
      splits = JSON.parse(fileContent);
    } catch (error) {
      console.error('Error reading splits file:', error);
      process.exit(1);
    }
  } else {
    console.error('Error: Must provide --splits-json, --splits-file, or --clear');
    process.exit(1);
  }

  // Validate split structure
  if (splits.length > 0) {
    const requiredKeys = new Set(['merchantName', 'amount', 'categoryId']);
    for (let i = 0; i < splits.length; i++) {
      const split = splits[i] as any;
      const splitKeys = new Set(Object.keys(split));
      const missing = [...requiredKeys].filter((k) => !splitKeys.has(k));

      if (missing.length > 0) {
        console.error(`Error: Split ${i} missing required keys: ${missing.join(', ')}`);
        process.exit(1);
      }

      // Check for notes
      if (!split.notes) {
        console.warn(`Warning: Split ${i + 1} has no notes. Consider adding itemized details.`);
      }
    }
  }

  // Initialize Monarch Money
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });

  // Login
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

  // Split and annotate transaction using SDK method
  try {
    console.log('Splitting transaction...');
    const startTime = performance.now();

    const transaction = await mm.transactions.updateTransactionSplits(transactionId, splits);

    const duration = performance.now() - startTime;
    console.log(`[PERF] Completed in ${duration.toFixed(2)}ms`);

    console.log(JSON.stringify(transaction, null, 2));
  } catch (error) {
    console.error('Error splitting transaction:', error);
    process.exit(1);
  }
}

main();
