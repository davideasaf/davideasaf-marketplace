#!/usr/bin/env tsx
/**
 * Amazon Refund Scraping Helper Functions
 *
 * Provides utilities for extracting refund data from Amazon payments page
 * via Playwright MCP browser interactions.
 */

export interface MonarchRefund {
  id: string;
  amount: number;
  date: string;
}

export interface AmazonRefund {
  amount: number;
  date: string;
  orderNumber: string;
  orderUrl: string;
}

export interface RefundMatch {
  monarchTransactionId: string;
  amount: number;
  date: string;
  orderNumber: string;
  orderUrl: string;
  itemName?: string;
  categoryId?: string;
}

/**
 * JavaScript to inject via browser_evaluate to extract ALL refund data
 * from the Amazon payments page in one shot.
 *
 * Returns array of: { amount, date, orderNumber, orderUrl }
 */
export const EXTRACT_REFUNDS_JS = `
(() => {
  const refunds = [];

  // Find all transaction groups on the page
  const dateGroups = document.querySelectorAll('[class*="date"]');

  dateGroups.forEach(dateGroup => {
    const dateText = dateGroup.textContent?.trim();
    if (!dateText) return;

    // Find transactions within this date group
    const transactionGroup = dateGroup.closest('[class*="transaction"]')?.nextElementSibling;
    if (!transactionGroup) return;

    // Find all refund entries (links containing "Refund:")
    const refundLinks = transactionGroup.querySelectorAll('a[href*="orderID"]');

    refundLinks.forEach(link => {
      const linkText = link.textContent?.trim() || '';

      // Only process refunds
      if (!linkText.includes('Refund:')) return;

      // Find the amount in the parent container
      const container = link.closest('div');
      let amountText = '';

      // Search for amount element (usually has + prefix for refunds)
      const amountElements = container?.querySelectorAll('[class*="amount"], [class*="price"]');
      amountElements?.forEach(el => {
        const text = el.textContent?.trim() || '';
        if (text.startsWith('+') || text.startsWith('$')) {
          amountText = text;
        }
      });

      if (!amountText) return;

      // Extract order number from URL
      const urlMatch = link.href.match(/orderID=([^&]+)/);
      const orderNumber = urlMatch ? urlMatch[1] : null;

      if (!orderNumber) return;

      // Parse amount (remove +, $, commas)
      const amount = parseFloat(amountText.replace(/[+$,]/g, ''));
      if (isNaN(amount)) return;

      refunds.push({
        amount: amount,
        date: dateText,
        orderNumber: orderNumber,
        orderUrl: link.href
      });
    });
  });

  return refunds;
})();
`;

/**
 * JavaScript to extract item name from order details page.
 * Should be called after clicking into an order.
 *
 * Returns: { itemName: string, orderNumber: string }
 */
export const EXTRACT_ITEM_NAME_JS = `
(() => {
  // Try multiple selectors to find item name
  const selectors = [
    'a[href*="/dp/"] img[alt]',  // Product image alt text
    'a[href*="/dp/"]',            // Product link text
    '[class*="item"] [class*="title"]',
    '[class*="product"] [class*="name"]',
    'h1, h2, h3'                  // Fallback to headings
  ];

  for (const selector of selectors) {
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
      let text = '';

      if (el.tagName === 'IMG') {
        text = el.getAttribute('alt') || '';
      } else {
        text = el.textContent?.trim() || '';
      }

      // Filter out generic text
      if (text &&
          text.length > 10 &&
          !text.includes('Order Details') &&
          !text.includes('View invoice') &&
          !text.includes('Ship to')) {
        return {
          itemName: text,
          orderNumber: window.location.href.match(/orderID=([^&]+)/)?.[1] || ''
        };
      }
    }
  }

  return { itemName: 'Unknown Item', orderNumber: '' };
})();
`;

/**
 * Filter Monarch transactions to only unreviewed refunds (positive amounts + needsReview=true)
 */
export function filterRefunds(transactions: any[]): MonarchRefund[] {
  return transactions
    .filter(t =>
      t.amount > 0 &&
      t.merchant?.name === 'Amazon' &&
      t.needsReview === true
    )
    .map(t => ({
      id: t.id,
      amount: t.amount,
      date: t.date
    }));
}

/**
 * Match Monarch refunds to Amazon refunds by amount and date
 */
export function matchRefunds(
  monarchRefunds: MonarchRefund[],
  amazonRefunds: AmazonRefund[]
): RefundMatch[] {
  const matches: RefundMatch[] = [];

  for (const monarch of monarchRefunds) {
    // Try exact date match first
    let match = amazonRefunds.find(
      amazon =>
        Math.abs(amazon.amount - monarch.amount) < 0.01 &&
        amazon.date === monarch.date
    );

    // Try ±1 day if no exact match
    if (!match) {
      const monarchDate = new Date(monarch.date);
      const prevDay = new Date(monarchDate);
      prevDay.setDate(prevDay.getDate() - 1);
      const nextDay = new Date(monarchDate);
      nextDay.setDate(nextDay.getDate() + 1);

      match = amazonRefunds.find(
        amazon => {
          const amazonDate = new Date(amazon.date);
          return Math.abs(amazon.amount - monarch.amount) < 0.01 &&
            (amazonDate.toDateString() === prevDay.toDateString() ||
             amazonDate.toDateString() === nextDay.toDateString());
        }
      );
    }

    if (match) {
      matches.push({
        monarchTransactionId: monarch.id,
        amount: monarch.amount,
        date: monarch.date,
        orderNumber: match.orderNumber,
        orderUrl: match.orderUrl
      });
    }
  }

  return matches;
}

/**
 * Format refund data for Monarch update
 */
export function formatRefundNote(itemName: string, orderNumber: string): string {
  return `Refund: ${itemName}\nOrder: https://www.amazon.com/gp/your-account/order-details?orderID=${orderNumber}`;
}

/**
 * Parse date from various Amazon date formats
 */
export function parseAmazonDate(dateStr: string): string {
  // Handle formats like "October 23, 2025"
  const date = new Date(dateStr);
  if (!isNaN(date.getTime())) {
    return date.toISOString().split('T')[0];
  }
  return dateStr;
}
