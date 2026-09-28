# Data Quality Finding: Referential Integrity Issues

## Problem

During analysis of the Transaction Disputes workflow, we discovered that ~26% of complaints (2,107 out of 8,143 cases) have a `customer_id` that does not match the `customer_id` of the associated transaction.

## Investigation

- The `affected_product_id` in the complaint correctly links to the product.
- The `customer_id` in `raw_transactions` matches the product owner.
- The `customer_id` in `complaints` does not always match the product owner.

## Root Cause Hypotheses

1. **Additional cards**: The primary cardholder files a complaint for a supplementary card.
2. **Corporate cards**: An employee reports a charge on a company card.
3. **Data quality issue**: Intentional synthetic data inconsistency (~2% duplicates, ~5% nulls suggest deliberate quality challenges).

## Solution

The agent queries transactions by `product_id` instead of `customer_id`, as the product is the reliable link between complaint and transaction.

## Business Impact

This pattern affects authorization logic. The agent must:

- Verify the authenticated user has permission to view the product's transactions.
- Explain to the customer why they're seeing transactions from a different customer_id (e.g., "This is your supplementary card").
- Escalate if the relationship is unclear.
