#!/usr/bin/env tsx
/**
 * Benchmark script with detailed telemetry
 *
 * Measures performance of finding and splitting Walmart transactions
 *
 * Usage:
 *   tsx scripts/benchmark.ts                          # Find latest Walmart
 *   tsx scripts/benchmark.ts --merchant "Target"      # Find specific merchant
 *   tsx scripts/benchmark.ts --date 2025-10-16        # Specific date
 */

import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';

// ============================================================================
// TELEMETRY UTILITIES
// ============================================================================

interface TimingEvent {
  name: string;
  start: number;
  end?: number;
  duration?: number;
}

class Telemetry {
  private events: TimingEvent[] = [];
  private startTime: number;

  constructor() {
    this.startTime = performance.now();
  }

  start(name: string): () => void {
    const event: TimingEvent = {
      name,
      start: performance.now(),
    };
    this.events.push(event);

    // Return a function to end timing
    return () => {
      event.end = performance.now();
      event.duration = event.end - event.start;
    };
  }

  report() {
    const totalDuration = performance.now() - this.startTime;

    console.log('\n' + '='.repeat(80));
    console.log('📊 PERFORMANCE TELEMETRY');
    console.log('='.repeat(80));
    console.log();

    // Print each event
    this.events.forEach(event => {
      if (event.duration) {
        const durationMs = event.duration.toFixed(2);
        const percentage = ((event.duration / totalDuration) * 100).toFixed(1);
        const bar = '█'.repeat(Math.floor(event.duration / 100));

        console.log(`${event.name.padEnd(30)} ${durationMs.padStart(8)}ms  [${percentage.padStart(5)}%] ${bar}`);
      }
    });

    console.log();
    console.log('-'.repeat(80));
    console.log(`${'TOTAL'.padEnd(30)} ${totalDuration.toFixed(2).padStart(8)}ms  [100.0%]`);
    console.log('='.repeat(80));
    console.log();

    // Return summary object
    return {
      total: totalDuration,
      events: this.events.map(e => ({
        name: e.name,
        duration: e.duration || 0,
      })),
    };
  }
}

// ============================================================================
// BENCHMARK FUNCTIONS
// ============================================================================

interface BenchmarkArgs {
  merchant?: string;
  date?: string;
  'start-date'?: string;
  'end-date'?: string;
  email?: string;
  password?: string;
}

async function findLatestTransaction(
  mm: MonarchClient,
  telemetry: Telemetry,
  merchant: string = 'Walmart',
  date?: string,
  startDate?: string,
  endDate?: string
) {
  const endTimer = telemetry.start('Find Transaction');

  let filters: any = {
    search: merchant,
  };

  if (date) {
    filters.startDate = date;
    filters.endDate = date;
  } else if (startDate && endDate) {
    filters.startDate = startDate;
    filters.endDate = endDate;
  } else {
    // Default to last 30 days
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 30);
    filters.startDate = start.toISOString().split('T')[0];
    filters.endDate = end.toISOString().split('T')[0];
  }

  const transactions = await mm.transactions.getTransactions({
    limit: 10,
    filters,
  });

  endTimer();

  return transactions;
}

async function getCategories(mm: MonarchClient, telemetry: Telemetry) {
  const endTimer = telemetry.start('Get Categories');

  const categories = await mm.categories.getCategories();

  endTimer();

  return categories;
}

// ============================================================================
// MAIN BENCHMARK
// ============================================================================

async function main() {
  const { values } = parseArgs({
    options: {
      merchant: { type: 'string' },
      date: { type: 'string' },
      'start-date': { type: 'string' },
      'end-date': { type: 'string' },
      email: { type: 'string' },
      password: { type: 'string' },
    },
  });

  const args = values as BenchmarkArgs;
  const telemetry = new Telemetry();

  console.log('\n🚀 Starting performance benchmark...\n');

  // Initialize MonarchClient
  const initTimer = telemetry.start('Initialize MonarchClient');
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });
  initTimer();

  // Login
  const loginTimer = telemetry.start('Login (with saved session)');
  const email = args.email || process.env.MONARCH_EMAIL;
  const password = args.password || process.env.MONARCH_PASSWORD;

  if (!email || !password) {
    console.error('❌ Error: Email and password required (via args or env vars)');
    process.exit(1);
  }

  try {
    await mm.login({ email, password, useSavedSession: true, saveSession: true });
  } catch (error) {
    console.error('❌ Error logging in:', error);
    process.exit(1);
  }
  loginTimer();

  // Find transactions
  const merchant = args.merchant || 'Walmart';
  console.log(`🔍 Searching for: ${merchant}`);

  try {
    const transactions = await findLatestTransaction(
      mm,
      telemetry,
      merchant,
      args.date,
      args['start-date'],
      args['end-date']
    );

    console.log(`✅ Found ${transactions.length} transaction(s)\n`);

    if (transactions.length > 0) {
      console.log('Most recent transaction:');
      console.log('------------------------');
      console.log(`ID:       ${transactions[0].id}`);
      console.log(`Date:     ${transactions[0].date}`);
      console.log(`Merchant: ${transactions[0].merchant?.name || 'N/A'}`);
      console.log(`Amount:   $${Math.abs(transactions[0].amount).toFixed(2)}`);
      console.log(`Category: ${transactions[0].category?.name || 'Uncategorized'}`);
      console.log();
    }

    // Get categories (to test caching)
    const categories = await getCategories(mm, telemetry);
    console.log(`✅ Loaded ${categories.length} categories\n`);

  } catch (error) {
    console.error('❌ Error during benchmark:', error);
    process.exit(1);
  }

  // Report telemetry
  const summary = telemetry.report();

  // Output JSON summary for parsing
  console.log('📋 JSON Summary:');
  console.log(JSON.stringify(summary, null, 2));
}

main();
