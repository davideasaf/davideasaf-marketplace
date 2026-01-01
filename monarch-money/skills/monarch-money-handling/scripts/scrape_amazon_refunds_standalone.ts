#!/usr/bin/env tsx
/**
 * Standalone Amazon Refund Scraper
 *
 * Uses Playwright DIRECTLY (not MCP) to scrape Amazon refunds efficiently.
 * Outputs only JSON to stdout - no page state bloat.
 *
 * Usage:
 *   npx tsx scripts/scrape_amazon_refunds_standalone.ts
 *   npx tsx scripts/scrape_amazon_refunds_standalone.ts --headless
 *   npx tsx scripts/scrape_amazon_refunds_standalone.ts --include-items
 *
 * Output format:
 *   {
 *     "refunds": [
 *       { "amount": 42.80, "date": "2025-12-21", "orderNumber": "111-...", "items": [...] }
 *     ]
 *   }
 */

import { chromium, type BrowserContext, type Page } from 'playwright';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { parseArgs } from 'node:util';

interface RefundData {
  amount: number;
  date: string;
  orderNumber: string;
  orderUrl: string;
  items?: ItemData[];
}

interface ItemData {
  name: string;
  price?: number;
  quantity?: number;
}

const TRANSACTIONS_URL = 'https://www.amazon.com/cpe/yourpayments/transactions';

// Chrome profile for persistent session
const DEFAULT_PROFILE_DIR = path.join(os.homedir(), '.amazon-session');

async function extractRefundsFromPage(page: Page): Promise<RefundData[]> {
  return await page.evaluate(() => {
    const refunds: any[] = [];
    const seen = new Set<string>();

    // Get current date context by finding date headers
    let currentDate = '';
    const dateHeaders = document.querySelectorAll('[class*="date"], h2, h3');
    const datePattern = /^(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}$/;

    // Find all transaction containers
    const containers = document.querySelectorAll('.apx-transactions-line-item-component-container');

    containers.forEach((container) => {
      // Check previous siblings for date
      let sibling = container.previousElementSibling;
      while (sibling) {
        const text = sibling.textContent?.trim() || '';
        if (datePattern.test(text)) {
          currentDate = text;
          break;
        }
        sibling = sibling.previousElementSibling;
      }

      // Get amount
      const amountEl = container.querySelector('span.a-text-bold');
      const amountText = amountEl?.textContent?.trim() || '';

      // Only process positive amounts (refunds)
      if (!amountText.startsWith('+') && !amountText.startsWith('$')) return;
      if (amountText.startsWith('-')) return;

      const amount = parseFloat(amountText.replace(/[+$,]/g, ''));
      if (isNaN(amount) || amount <= 0) return;

      // Get order link
      const orderLink = container.querySelector('a[href*="orderID="]') as HTMLAnchorElement;
      if (!orderLink) return;

      const urlMatch = orderLink.href.match(/orderID=([^&]+)/);
      const orderNumber = urlMatch ? urlMatch[1] : '';
      if (!orderNumber) return;

      // Dedup by order + amount
      const key = `${orderNumber}_${amount}`;
      if (seen.has(key)) return;
      seen.add(key);

      refunds.push({
        amount,
        date: currentDate,
        orderNumber,
        orderUrl: orderLink.href,
      });
    });

    return refunds;
  });
}

async function extractItemsFromOrderPage(page: Page): Promise<ItemData[]> {
  return await page.evaluate(() => {
    const items: any[] = [];

    // Try to find product rows in order details
    const productSelectors = [
      '.shipment-item', // Order details page
      '[class*="item-row"]',
      '[class*="product-item"]',
      'a[href*="/dp/"]', // Product links
    ];

    for (const selector of productSelectors) {
      const elements = document.querySelectorAll(selector);
      if (elements.length === 0) continue;

      elements.forEach((el) => {
        let name = '';
        let price: number | undefined;

        // Try to get product name
        const nameEl =
          el.querySelector('a[href*="/dp/"]') ||
          el.querySelector('[class*="title"]') ||
          el.querySelector('[class*="name"]');

        if (nameEl) {
          name = nameEl.textContent?.trim() || '';
        } else if (el.tagName === 'A' && el.getAttribute('href')?.includes('/dp/')) {
          name = el.textContent?.trim() || '';
        }

        // Try to get price
        const priceEl = el.querySelector('[class*="price"]');
        if (priceEl) {
          const priceText = priceEl.textContent?.trim() || '';
          price = parseFloat(priceText.replace(/[$,]/g, ''));
        }

        if (name && name.length > 5) {
          items.push({ name, price: isNaN(price!) ? undefined : price });
        }
      });

      if (items.length > 0) break;
    }

    // Fallback: look for any product image alt text
    if (items.length === 0) {
      const imgs = document.querySelectorAll('img[alt]');
      imgs.forEach((img) => {
        const alt = img.getAttribute('alt') || '';
        if (
          alt.length > 10 &&
          !alt.includes('Amazon') &&
          !alt.includes('logo') &&
          !alt.includes('icon')
        ) {
          items.push({ name: alt });
        }
      });
    }

    return items;
  });
}

async function isLoginPage(page: Page): Promise<boolean> {
  const url = page.url();
  return (
    url.includes('/ap/signin') ||
    url.includes('/signin') ||
    url.includes('/ap/cvf') ||
    url.includes('/ap/mfa')
  );
}

async function scrapeAmazonRefunds(options: {
  headless: boolean;
  includeItems: boolean;
  profileDir: string;
}): Promise<RefundData[]> {
  const { headless, includeItems, profileDir } = options;

  // Ensure profile directory exists
  if (!fs.existsSync(profileDir)) {
    fs.mkdirSync(profileDir, { recursive: true });
  }

  const context = await chromium.launchPersistentContext(profileDir, {
    headless,
    channel: 'chrome',
    args: ['--disable-blink-features=AutomationControlled', '--no-sandbox'],
  });

  const page = context.pages()[0] || (await context.newPage());
  let allRefunds: RefundData[] = [];

  try {
    console.error('Navigating to Amazon transactions...');
    await page.goto(TRANSACTIONS_URL, { waitUntil: 'domcontentloaded' });

    // Check if login required
    if (await isLoginPage(page)) {
      if (headless) {
        throw new Error(
          'Login required. Run without --headless first to authenticate.'
        );
      }
      console.error('Login required. Please log in via the browser...');
      await page.waitForURL('**/yourpayments/transactions**', { timeout: 300000 });
      console.error('Login successful!');
    }

    // Wait for transactions to load
    await page.waitForSelector('a[href*="orderID="]', { timeout: 10000 }).catch(() => {
      console.error('No transactions found on page');
    });

    // Extract refunds from all pages
    let pageNum = 1;
    while (true) {
      console.error(`Extracting from page ${pageNum}...`);

      const pageRefunds = await extractRefundsFromPage(page);
      console.error(`  Found ${pageRefunds.length} refunds`);
      allRefunds = allRefunds.concat(pageRefunds);

      // Check for next page
      const nextBtn = page.locator('span.a-button:has-text("Next Page")');
      const isVisible = await nextBtn.isVisible().catch(() => false);

      if (!isVisible) {
        console.error('No more pages');
        break;
      }

      await nextBtn.click({ force: true });
      await page.waitForTimeout(3000);
      pageNum++;
    }

    // Optionally fetch item details for each refund
    if (includeItems && allRefunds.length > 0) {
      console.error(`\nFetching item details for ${allRefunds.length} refunds...`);

      for (let i = 0; i < allRefunds.length; i++) {
        const refund = allRefunds[i];
        console.error(`  [${i + 1}/${allRefunds.length}] Order ${refund.orderNumber}...`);

        try {
          await page.goto(refund.orderUrl, { waitUntil: 'domcontentloaded' });
          await page.waitForTimeout(2000);

          const items = await extractItemsFromOrderPage(page);
          refund.items = items;

          console.error(`    Found ${items.length} item(s)`);
        } catch (err) {
          console.error(`    Error: ${err}`);
          refund.items = [];
        }
      }
    }
  } finally {
    await context.close();
  }

  return allRefunds;
}

async function main() {
  const { values } = parseArgs({
    options: {
      headless: { type: 'boolean', default: false },
      'include-items': { type: 'boolean', default: false },
      'profile-dir': { type: 'string', default: DEFAULT_PROFILE_DIR },
      help: { type: 'boolean', short: 'h' },
    },
  });

  if (values.help) {
    console.log(`
Amazon Refund Scraper (Standalone Playwright)

Usage:
  npx tsx scripts/scrape_amazon_refunds_standalone.ts [options]

Options:
  --headless        Run in headless mode (requires existing auth session)
  --include-items   Also fetch item names from each order page
  --profile-dir     Chrome profile directory (default: ~/.amazon-session)
  -h, --help        Show this help

Output:
  JSON to stdout with structure: { "refunds": [...] }
  Progress messages go to stderr

Examples:
  # First run (interactive login)
  npx tsx scripts/scrape_amazon_refunds_standalone.ts

  # Subsequent runs (headless with saved session)
  npx tsx scripts/scrape_amazon_refunds_standalone.ts --headless

  # With item details
  npx tsx scripts/scrape_amazon_refunds_standalone.ts --headless --include-items
`);
    process.exit(0);
  }

  try {
    const refunds = await scrapeAmazonRefunds({
      headless: values.headless ?? false,
      includeItems: values['include-items'] ?? false,
      profileDir: values['profile-dir'] ?? DEFAULT_PROFILE_DIR,
    });

    // Output only JSON to stdout
    console.log(JSON.stringify({ refunds }, null, 2));
  } catch (err) {
    console.error('Error:', err);
    process.exit(1);
  }
}

main();
