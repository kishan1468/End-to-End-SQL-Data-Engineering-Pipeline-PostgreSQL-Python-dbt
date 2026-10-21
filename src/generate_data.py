"""Generate a reproducible synthetic e-commerce dataset.

Produces five CSV files in ./data:
    customers, products, orders, order_items, payments

A small share of deliberately bad rows is injected (malformed emails,
duplicate keys, non-positive quantities, orphan foreign keys, invalid
statuses, future dates, null amounts) so the validation step in
`ingest.py` has real work to do.

Usage:
    python src/generate_data.py --customers 2000 --orders 8000 --seed 42
"""
from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

FIRST = ["Aarav", "Anna", "Ben", "Clara", "David", "Elena", "Felix", "Greta", "Hans",
         "Isha", "Jonas", "Kavya", "Lukas", "Mia", "Noah", "Olivia", "Priya", "Rahul",
         "Sofia", "Tim", "Uma", "Viktor", "Wei", "Yara", "Zoe"]
LAST = ["Schmidt", "Mueller", "Weber", "Fischer", "Sharma", "Patel", "Singh", "Meyer",
        "Wagner", "Becker", "Hoffmann", "Koch", "Richter", "Klein", "Wolf", "Neumann"]
COUNTRIES = ["Germany", "India", "France", "Netherlands", "Spain", "Italy", "Poland", "Austria"]
COUNTRY_WEIGHTS = [40, 15, 10, 8, 8, 7, 7, 5]
CATEGORIES = {
    "Electronics": (25, 900),
    "Books": (8, 60),
    "Home & Kitchen": (10, 250),
    "Sports": (12, 300),
    "Beauty": (5, 120),
    "Toys": (6, 90),
}
PAYMENT_METHODS = ["credit_card", "paypal", "sepa_debit", "klarna", "bank_transfer"]
# status -> probability
STATUSES = {"completed": 0.72, "shipped": 0.10, "cancelled": 0.08, "refunded": 0.05, "pending": 0.05}

START = date(2024, 1, 1)
END = date(2026, 9, 30)


def rand_date(rng: random.Random) -> date:
    return START + timedelta(days=rng.randint(0, (END - START).days))


def build(n_customers: int, n_orders: int, seed: int) -> dict[str, pd.DataFrame]:
    rng = random.Random(seed)

    # ---- customers -------------------------------------------------------
    customers = []
    for cid in range(1, n_customers + 1):
        fn, ln = rng.choice(FIRST), rng.choice(LAST)
        customers.append({
            "customer_id": cid,
            "first_name": fn,
            "last_name": ln,
            "email": f"{fn}.{ln}.{cid}@example.com".lower(),
            "country": rng.choices(COUNTRIES, COUNTRY_WEIGHTS)[0],
            "signup_date": rand_date(rng).isoformat(),
        })

    # ---- products --------------------------------------------------------
    products = []
    pid = 1
    for cat, (lo, hi) in CATEGORIES.items():
        for i in range(1, 21):
            products.append({
                "product_id": pid,
                "product_name": f"{cat.split()[0]} Item {i:02d}",
                "category": cat,
                "unit_price": round(rng.uniform(lo, hi), 2),
            })
            pid += 1
    n_products = len(products)
    price_of = {p["product_id"]: p["unit_price"] for p in products}

    # ---- orders / items / payments --------------------------------------
    orders, items, payments = [], [], []
    item_id = pay_id = 1
    signup = {c["customer_id"]: date.fromisoformat(c["signup_date"]) for c in customers}
    statuses, weights = zip(*STATUSES.items())

    for oid in range(1, n_orders + 1):
        cid = rng.randint(1, n_customers)
        order_date = max(rand_date(rng), signup[cid])  # no order before signup
        status = rng.choices(statuses, weights)[0]
        orders.append({"order_id": oid, "customer_id": cid,
                       "order_date": order_date.isoformat(), "status": status})

        total = 0.0
        for _ in range(rng.randint(1, 5)):
            prod = rng.randint(1, n_products)
            qty = rng.choices([1, 2, 3, 4], [60, 25, 10, 5])[0]
            price = price_of[prod]
            items.append({"order_item_id": item_id, "order_id": oid, "product_id": prod,
                          "quantity": qty, "unit_price": price})
            total += round(qty * price, 2)
            item_id += 1

        if status != "cancelled" and status != "pending":
            paid_at = datetime.combine(order_date, datetime.min.time()) + timedelta(
                hours=rng.randint(0, 48), minutes=rng.randint(0, 59))
            payments.append({"payment_id": pay_id, "order_id": oid,
                             "payment_method": rng.choice(PAYMENT_METHODS),
                             "amount": round(total, 2),
                             "paid_at": paid_at.isoformat(sep=" ")})
            pay_id += 1

    # ---- inject bad rows -------------------------------------------------
    # 1. malformed emails (~1% of customers) -> rejected, orders cascade
    for c in rng.sample(customers, k=max(1, n_customers // 100)):
        c["email"] = c["email"].replace("@", "_at_")
    # 2. duplicate customer primary keys
    customers += [dict(c) for c in rng.sample(customers, k=5)]
    # 3. extra order_items with non-positive quantity
    for _ in range(20):
        items.append({"order_item_id": item_id, "order_id": rng.randint(1, n_orders),
                      "product_id": rng.randint(1, n_products),
                      "quantity": rng.choice([0, -1, -3]), "unit_price": 10.0})
        item_id += 1
    # 4. orders: orphan customer, invalid status, future date
    next_oid = n_orders + 1
    for kind in ["orphan"] * 10 + ["status"] * 10 + ["future"] * 5:
        orders.append({
            "order_id": next_oid,
            "customer_id": 999_999 if kind == "orphan" else rng.randint(1, n_customers),
            "order_date": "2099-01-01" if kind == "future" else rand_date(rng).isoformat(),
            "status": "teleported" if kind == "status" else "completed",
        })
        next_oid += 1
    # 5. payments with null amount
    for _ in range(8):
        payments.append({"payment_id": pay_id, "order_id": rng.randint(1, n_orders),
                         "payment_method": rng.choice(PAYMENT_METHODS),
                         "amount": None, "paid_at": "2025-01-01 10:00:00"})
        pay_id += 1

    return {
        "customers": pd.DataFrame(customers),
        "products": pd.DataFrame(products),
        "orders": pd.DataFrame(orders),
        "order_items": pd.DataFrame(items),
        "payments": pd.DataFrame(payments),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--customers", type=int, default=2000)
    ap.add_argument("--orders", type=int, default=8000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for name, df in build(args.customers, args.orders, args.seed).items():
        df.to_csv(args.out / f"{name}.csv", index=False)
        print(f"wrote {name}.csv  ({len(df):,} rows)")


if __name__ == "__main__":
    main()
