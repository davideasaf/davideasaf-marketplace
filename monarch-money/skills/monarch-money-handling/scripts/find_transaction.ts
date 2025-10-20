#!/usr/bin/env tsx
/**
 * Find a Monarch Money transaction by various criteria.
 *
 * Usage:
 *   tsx scripts/find_transaction.ts --id <transaction_id>
 *   tsx scripts/find_transaction.ts --date <date> --merchant <merchant_name>
 *   tsx scripts/find_transaction.ts --start-date <start> --end-date <end> --merchant <merchant>
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

interface FindTransactionArgs {
  id?: string;
  date?: string;
  'start-date'?: string;
  'end-date'?: string;
  merchant?: string;
  limit?: string;
  email?: string;
  password?: string;
}

async function findTransactionById(mm: MonarchClient, transactionId: string) {
  const result = await mm.transactions.getTransactionDetails(transactionId);
  return result;
}

async function findTransactionsByCriteria(
  mm: MonarchClient,
  options: {
    startDate?: string;
    endDate?: string;
    merchant?: string;
    limit?: number;
  }
) {
  const result = await mm.transactions.getTransactions({
    startDate: options.startDate,
    endDate: options.endDate,
    search: options.merchant || '',
    limit: options.limit || 100,
  });

  return result.transactions;
}

async function main() {
  const { values } = parseArgs({
    options: {
      id: { type: 'string' },
      date: { type: 'string' },
      'start-date': { type: 'string' },
      'end-date': { type: 'string' },
      merchant: { type: 'string' },
      limit: { type: 'string', default: '100' },
      email: { type: 'string' },
      password: { type: 'string' },
    },
  });

  const args = values as FindTransactionArgs;

  // Initialize Monarch Money with correct API endpoint
  const mm = new MonarchClient({
    baseURL: 'https://api.monarch.com',
  });

  // Login
  const email = args.email || process.env.MONARCH_EMAIL;
  const password = args.password || process.env.MONARCH_PASSWORD;
  const mfaSecretKey = process.env.MONARCH_MFA_SECRET;

  if (!email || !password) {
    console.error('Error: Email and password required (via args or env vars)');
    process.exit(1);
  }

  try {
    await mm.login({ email, password, mfaSecretKey, useSavedSession: true, saveSession: true });
  } catch (error) {
    console.error('Error logging in:', error);
    process.exit(1);
  }

  // Find transaction
  try {
    if (args.id) {
      // Find by ID
      const transaction = await findTransactionById(mm, args.id);
      console.log(JSON.stringify(transaction, null, 2));
    } else {
      // Find by criteria
      const startDate = args['start-date'] || args.date;
      const endDate = args['end-date'] || args.date;

      if (!startDate) {
        console.error('Error: Must provide either --id or --date/--start-date');
        process.exit(1);
      }

      const transactions = await findTransactionsByCriteria(mm, {
        startDate,
        endDate,
        merchant: args.merchant,
        limit: args.limit ? parseInt(args.limit, 10) : 100,
      });

      console.log(
        JSON.stringify(
          {
            count: transactions.length,
            transactions,
          },
          null,
          2
        )
      );
    }
  } catch (error) {
    console.error('Error finding transaction:', error);
    process.exit(1);
  }
}

main();
