/**
 * Utility functions for formatting transaction notes with proper readability.
 * Monarch Money supports newlines, so we can create well-structured notes.
 */

export interface ReceiptItem {
  name: string;
  price: number;
}

export interface FormattedNotesOptions {
  category?: string;
  items: ReceiptItem[];
  deliveryDate?: string;
  orderNumber?: string;
  additionalInfo?: string;
}

/**
 * Format receipt items into a readable multi-line note with bullet points.
 *
 * Example output:
 * ```
 * Children's Clothing:
 * • Item 1 - $14.99
 * • Item 2 - $8.99
 *
 * Delivered: Oct 17
 * Order: AMAZON MKTPL*NM2237YZ0
 * ```
 */
export function formatReceiptNotes(options: FormattedNotesOptions): string {
  const lines: string[] = [];

  // Category header (if provided)
  if (options.category) {
    lines.push(`${options.category}:`);
  }

  // Itemized list with bullet points
  for (const item of options.items) {
    const formattedPrice = item.price.toFixed(2);
    lines.push(`• ${item.name} - $${formattedPrice}`);
  }

  // Add spacing before metadata
  if (options.deliveryDate || options.orderNumber || options.additionalInfo) {
    lines.push('');
  }

  // Delivery date
  if (options.deliveryDate) {
    lines.push(`Delivered: ${options.deliveryDate}`);
  }

  // Order number
  if (options.orderNumber) {
    lines.push(`Order: ${options.orderNumber}`);
  }

  // Additional info
  if (options.additionalInfo) {
    lines.push(options.additionalInfo);
  }

  return lines.join('\n');
}

/**
 * Format split transaction notes for a single category.
 * Similar to formatReceiptNotes but optimized for split transactions.
 *
 * Example output:
 * ```
 * Groceries:
 * • Crackers - $3.88
 * • Cottage cheese - $3.24
 * • Milk - $4.37
 * • Eggs - $5.46
 * Total: $17.95
 * ```
 */
export function formatSplitNotes(
  category: string,
  items: ReceiptItem[],
  includeTotal = true
): string {
  const lines: string[] = [];

  // Category header
  lines.push(`${category}:`);

  // Itemized list
  let total = 0;
  for (const item of items) {
    total += item.price;
    const formattedPrice = item.price.toFixed(2);
    lines.push(`• ${item.name} - $${formattedPrice}`);
  }

  // Total (optional)
  if (includeTotal && items.length > 1) {
    lines.push(`Total: $${total.toFixed(2)}`);
  }

  return lines.join('\n');
}

/**
 * Format a simple itemized list without category grouping.
 * Useful for single-category transactions.
 *
 * Example output:
 * ```
 * • Item 1 - $14.99
 * • Item 2 - $8.99
 * • Item 3 - $5.50
 * ```
 */
export function formatSimpleItemList(items: ReceiptItem[]): string {
  return items
    .map(item => `• ${item.name} - $${item.price.toFixed(2)}`)
    .join('\n');
}
