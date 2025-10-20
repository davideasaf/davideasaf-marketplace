#!/usr/bin/env tsx
/**
 * Update a Monarch Money transaction (category, merchant, amount, date, etc.).
 *
 * Usage:
 *   tsx scripts/update_transaction.ts <transaction_id> --category <category_id>
 *   tsx scripts/update_transaction.ts <transaction_id> --merchant "New Merchant Name"
 *   tsx scripts/update_transaction.ts <transaction_id> --amount -123.45
 *   tsx scripts/update_transaction.ts <transaction_id> --date 2024-03-15
 *   tsx scripts/update_transaction.ts <transaction_id> --hide-from-reports true
 *   tsx scripts/update_transaction.ts <transaction_id> --needs-review false
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface UpdateTransactionArgs {
  category?: string;
  merchant?: string;
  amount?: string;
  date?: string;
  'hide-from-reports'?: string;
  'needs-review'?: string;
  notes?: string;
  email?: string;
  password?: string;
}

async function updateTransaction(
  mm: MonarchClient,
  transactionId: string,
  updates: {
    categoryId?: string;
    merchant?: string;
    amount?: number;
    date?: string;
    hideFromReports?: boolean;
    notes?: string;
  }
) {
  const result = await mm.transactions.updateTransaction(transactionId, updates);
  return result;
}

function parseBoolean(value: string | undefined): boolean | undefined {
  if (value === undefined) return undefined;
  return value.toLowerCase() === 'true';
}

async function main() {
  const { values, positionals } = parseArgs({
    options: {
      category: { type: 'string' },
      merchant: { type: 'string' },
      amount: { type: 'string' },
      date: { type: 'string' },
      'hide-from-reports': { type: 'string' },
      'needs-review': { type: 'string' },
      notes: { type: 'string' },
      email: { type: 'string' },
      password: { type: 'string' },
    },
    allowPositionals: true,
  });

  const args = values as UpdateTransactionArgs;

  // Get transaction ID from positional argument
  if (positionals.length === 0) {
    console.error('Error: Transaction ID required as first argument');
    process.exit(1);
  }

  const transactionId = positionals[0];

  // Build updates object
  const updates: any = {};

  if (args.category) updates.categoryId = args.category;
  if (args.merchant) updates.merchant = args.merchant;
  if (args.amount) updates.amount = parseFloat(args.amount);
  if (args.date) updates.date = args.date;
  if (args['hide-from-reports'] !== undefined) {
    updates.hideFromReports = parseBoolean(args['hide-from-reports']);
  }
  if (args.notes) updates.notes = args.notes;

  // Check if at least one field is being updated
  if (Object.keys(updates).length === 0) {
    console.error('Error: Must provide at least one field to update');
    process.exit(1);
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

  // Update transaction
  try {
    const result = await updateTransaction(mm, transactionId, updates);

    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    console.error('Error updating transaction:', error);
    process.exit(1);
  }
}

main();
