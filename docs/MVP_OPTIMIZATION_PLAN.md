# VEGZ Admin — MVP Optimization Plan

## In-scope before GPS and payment gateway
- Make Admin the authoritative approval/control plane for shops, agents, product moderation and order status.
- Replace duplicate, manually managed order/shop records with authenticated service synchronization and reconciliation.
- Add a bulk-order request queue with business type, item lines, quantities/units, requested date, quote, status and assigned owner.
- Add role-based permissions for support, operations and super-admin actions.
- Require audit events for approvals, price overrides, adjustments and status changes.
- Add filters/pagination for orders, shops, agents and audit logs.
- Add health/dependency status for Shop and Agent services and surface integration failures.
- Keep secrets outside source control and enforce strong production bootstrap credentials.

## B2B quotation lifecycle
pending_review -> quoted -> accepted -> confirmed -> fulfilling -> delivered.
Also support rejected and cancelled with a reason. Preserve a quote snapshot so later catalog price changes do not silently change an accepted quote. A quotation is not an order, and an order is not paid until verified by a payment service.

## Acceptance checks
- Admin actions are authenticated and role-checked.
- Partner approvals propagate to the corresponding service.
- Failed downstream sync is visible and retryable.
- Bulk quote and order transitions are validated and audited.
