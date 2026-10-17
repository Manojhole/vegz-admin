# Vegz release-readiness and cross-service verification

Use this checklist before calling a build production-ready. A green health check alone does not prove the customer, shop, agent and admin workflows are integrated.

## Start and smoke-test the development services

Start the APIs using each repository's documented instructions. From the `vegz-user` repository run:

```bash
bash scripts/vegz-smoke-test.sh
```

The script checks health endpoints for customer (8003), shop (8002), agent (8001), admin (8000), and the public customer product catalog. Override `VEGZ_USER_API`, `VEGZ_SHOP_API`, `VEGZ_AGENT_API`, and `VEGZ_ADMIN_API` when using different URLs.

## Required end-to-end release checks

- [ ] A newly registered shop is pending approval and cannot publish purchasable inventory or accept orders.
- [ ] Admin approval updates the owning shop service; rejection/suspension blocks selling and order acceptance.
- [ ] A new shop product enters moderation; approve/reject changes the shop service and customer catalog consistently.
- [ ] Customer catalog shows only approved products from approved, open shops with positive stock; each image matches the product.
- [ ] Product price and stock updates are reflected without stale or duplicate listings.
- [ ] Customer can add/remove items, save an eligible delivery address, place a COD order, and see order status/history.
- [ ] Multi-shop orders create the correct shop suborders and dispatch; failed downstream calls do not silently report success.
- [ ] Only approved agents can go online; assigned agents see only their deliveries and valid status transitions are enforced.
- [ ] Delivery status reaches customer, shop and admin views; failed delivery requires a reason.
- [ ] Unauthenticated requests and cross-account access are rejected; service callbacks require shared secrets.
- [ ] Database migrations, restart persistence, empty/error/loading UI, Android builds and responsive web layouts are checked.
- [ ] Payment is not shown as paid unless the payment gateway confirms it; OTP is not production-ready while demo codes are enabled.

## Known release caveats

Development/demo login codes are not production authentication. Customer OTP delivery requires a configured SMS provider. Online payments, live GPS tracking, and tamper-resistant delivery proof need real provider/device integration. Validate cross-service callback URLs and shared secrets in the target environment. Use separately owned service schemas and reviewed migrations; do not let the apps write directly into each other's tables.

## Release decision

Do not mark a release as production-ready until the workflow checks above are executed against a shared development environment with evidence, including negative cases (pending/rejected shop, out-of-stock item, unauthorized user, failed callback, and invalid order-state transition).
