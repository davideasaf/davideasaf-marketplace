#!/usr/bin/env tsx
/**
 * Batch Process Amazon Refunds - Coordinator Script
 *
 * This script orchestrates the entire Amazon refund processing workflow:
 * 1. Finds Amazon refunds from Monarch Money
 * 2. Generates instructions for Claude to scrape Amazon via Playwright MCP
 * 3. Processes scraped data to infer categories
 * 4. Generates bulk update commands
 *
 * Usage:
 *   npm run batch-refunds -- --days 14
 *   npm run batch-refunds -- --start-date 2025-10-13 --end-date 2025-10-27
 *   npm run batch-refunds -- --input refunds.json
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as process from 'node:process';
import { parseArgs } from 'node:util';
import { MonarchClient } from 'monarchmoney';
import {
  filterRefunds,
  matchRefunds,
  formatRefundNote,
  EXTRACT_REFUNDS_JS,
  EXTRACT_ITEM_NAME_JS,
  type MonarchRefund,
  type AmazonRefund,
  type RefundMatch
} from './amazon_scraping_helpers.js';

interface Args {
  days?: string;
  'start-date'?: string;
  'end-date'?: string;
  input?: string;
  output?: string;
  email?: string;
  password?: string;
}

const CACHE_DIR = path.join(__dirname, '..', '.cache');

// Ensure cache directory exists
if (!fs.existsSync(CACHE_DIR)) {
  fs.mkdirSync(CACHE_DIR, { recursive: true });
}

async function findMonarchRefunds(
  mm: MonarchClient,
  startDate: string,
  endDate: string
): Promise<MonarchRefund[]> {
  console.log(`\n📊 Finding Amazon transactions from ${startDate} to ${endDate}...`);

  const transactions = await mm.transactions.getTransactions({
    startDate,
    endDate,
    limit: 500,
  });

  const allAmazon = transactions.allTransactions.results.filter(
    t => t.merchant?.name === 'Amazon'
  );

  const refunds = filterRefunds(allAmazon);

  console.log(`   Found ${allAmazon.length} Amazon transactions`);
  console.log(`   Found ${refunds.length} unreviewed refunds (positive amounts + needsReview=true)`);

  return refunds;
}

function printScrapingInstructions(refunds: MonarchRefund[]) {
  console.log('\n' + '='.repeat(70));
  console.log('SCRAPING INSTRUCTIONS FOR CLAUDE');
  console.log('='.repeat(70));

  console.log('\n📋 Step 1: Navigate to Amazon Payments');
  console.log('   Use: mcp__playwright__browser_navigate');
  console.log('   URL: https://www.amazon.com/cpe/yourpayments/transactions');

  console.log('\n📋 Step 2: Extract ALL refund data in one call');
  console.log('   Use: mcp__playwright__browser_evaluate');
  console.log('   Function:');
  console.log('   ```javascript');
  console.log(EXTRACT_REFUNDS_JS);
  console.log('   ```');
  console.log('   Save result to: .cache/amazon_refunds_raw.json');

  console.log('\n📋 Step 3: Match and process refunds');
  console.log('   The script will automatically match by amount + date');
  console.log('   Expected matches:');

  refunds.forEach(r => {
    console.log(`   → $${r.amount.toFixed(2)} on ${r.date} (ID: ${r.id})`);
  });

  console.log('\n📋 Step 4: For each matched refund, extract item details');
  console.log('   a) Click order link');
  console.log('   b) Use browser_evaluate with:');
  console.log('   ```javascript');
  console.log(EXTRACT_ITEM_NAME_JS);
  console.log('   ```');
  console.log('   c) Navigate back to payments page');
  console.log('   d) Repeat for next refund');

  console.log('\n📋 Step 5: After collecting all item names');
  console.log('   Run: npm run batch-refunds -- --process-scraped');
  console.log('   This will:');
  console.log('   - Infer categories from item names');
  console.log('   - Generate bulk update script');
  console.log('   - Execute updates to Monarch Money');

  console.log('\n' + '='.repeat(70));
}

async function processScrapedData(
  monarchRefunds: MonarchRefund[],
  amazonRefundsPath: string
): Promise<RefundMatch[]> {
  console.log('\n🔄 Processing scraped Amazon data...');

  if (!fs.existsSync(amazonRefundsPath)) {
    console.error(`❌ Error: ${amazonRefundsPath} not found`);
    console.error('   Run the scraping steps first!');
    process.exit(1);
  }

  const amazonRefunds: AmazonRefund[] = JSON.parse(
    fs.readFileSync(amazonRefundsPath, 'utf-8')
  );

  console.log(`   Loaded ${amazonRefunds.length} Amazon refunds`);

  const matches = matchRefunds(monarchRefunds, amazonRefunds);

  console.log(`   Matched ${matches.length} of ${monarchRefunds.length} Monarch refunds`);

  if (matches.length < monarchRefunds.length) {
    console.warn('\n⚠️  Some refunds could not be matched:');
    const matchedIds = new Set(matches.map(m => m.monarchTransactionId));
    monarchRefunds
      .filter(r => !matchedIds.has(r.id))
      .forEach(r => {
        console.warn(`   → $${r.amount.toFixed(2)} on ${r.date} (ID: ${r.id})`);
      });
  }

  return matches;
}

async function main() {
  const { values } = parseArgs({
    options: {
      days: { type: 'string' },
      'start-date': { type: 'string' },
      'end-date': { type: 'string' },
      input: { type: 'string' },
      output: { type: 'string' },
      email: { type: 'string' },
      password: { type: 'string' },
    },
  });

  const args = values as Args;

  // Determine date range
  let startDate: string;
  let endDate: string;

  if (args['start-date'] && args['end-date']) {
    startDate = args['start-date'];
    endDate = args['end-date'];
  } else if (args.days) {
    const days = parseInt(args.days, 10);
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - days);
    endDate = end.toISOString().split('T')[0];
    startDate = start.toISOString().split('T')[0];
  } else {
    // Default to last 14 days
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - 14);
    endDate = end.toISOString().split('T')[0];
    startDate = start.toISOString().split('T')[0];
  }

  // Initialize Monarch Money
  const mm = new MonarchClient({ baseURL: 'https://api.monarch.com' });

  const email = args.email || process.env.MONARCH_EMAIL;
  const password = args.password || process.env.MONARCH_PASSWORD;

  if (!email || !password) {
    console.error('❌ Error: Email and password required (via args or env vars)');
    process.exit(1);
  }

  try {
    console.log('🔐 Logging in to Monarch Money...');
    await mm.login({ email, password, useSavedSession: true, saveSession: true });
    console.log('✅ Logged in successfully');
  } catch (error) {
    console.error('❌ Error logging in:', error);
    process.exit(1);
  }

  // Find Monarch refunds
  const monarchRefunds = await findMonarchRefunds(mm, startDate, endDate);

  if (monarchRefunds.length === 0) {
    console.log('\n✅ No refunds found in date range.');
    process.exit(0);
  }

  // Save Monarch refunds to cache
  const monarchRefundsPath = path.join(CACHE_DIR, 'monarch_refunds.json');
  fs.writeFileSync(
    monarchRefundsPath,
    JSON.stringify(monarchRefunds, null, 2)
  );
  console.log(`\n💾 Saved Monarch refunds to: ${monarchRefundsPath}`);

  // Print scraping instructions
  printScrapingInstructions(monarchRefunds);

  console.log('\n💡 TIP: Save the browser_evaluate results to:');
  console.log(`   ${path.join(CACHE_DIR, 'amazon_refunds_raw.json')}`);
  console.log('\n   Then run: npm run batch-refunds -- --process-scraped');
}

main();
