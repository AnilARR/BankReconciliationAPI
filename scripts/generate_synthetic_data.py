"""Generate SYNTHETIC ledger and daily-file data with known discrepancies.

No real customers, accounts or banking credentials are used: names are "Synthetic Customer NNN" and
account numbers use a fake "SYNT" bank code.

    python scripts/generate_synthetic_data.py --count 200 --date 2026-10-21 --out sample_data

Produces:
    ledger_transactions.csv   load via POST /api/v1/transactions/import
    bank_daily_file.csv       upload via POST /api/v1/imports
    bank_daily_file.xlsx      same content as Excel
"""

import argparse
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd

STATUSES = ["COMPLETED"] * 8 + ["PENDING", "FAILED"]
DESCRIPTIONS = ["Card payment", "Standing order", "Direct debit", "Salary credit", "Transfer", "ATM withdrawal"]


def synthetic_transaction(rng: random.Random, n: int, day: date) -> dict:
    customer = rng.randint(1, 500)
    return {
        "reference": f"TXN-{day:%Y%m%d}-{n:06d}",
        "account_number": f"GB00SYNT{customer:014d}",
        "customer_name": f"Synthetic Customer {customer:03d}",
        "amount": str(Decimal(rng.randint(100, 500_000)) / 100),
        "currency": "USD",
        "transaction_date": day.isoformat(),
        "status": rng.choice(STATUSES),
        "description": rng.choice(DESCRIPTIONS),
    }


def generate(count: int, day: date, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = random.Random(seed)
    ledger = [synthetic_transaction(rng, i, day) for i in range(1, count + 1)]
    bank = [dict(t) for t in ledger]

    # Inject discrepancies (each index used once so outcomes are predictable).
    picks = rng.sample(range(len(bank)), k=max(10, count // 10))
    q = max(1, len(picks) // 5)
    amount_diff, date_diff, status_diff, missing_from_file, duplicated = (
        picks[0:q],
        picks[q : 2 * q],
        picks[2 * q : 3 * q],
        picks[3 * q : 4 * q],
        picks[4 * q : 5 * q],
    )
    for i in amount_diff:
        bank[i]["amount"] = str(Decimal(bank[i]["amount"]) + Decimal("10.00"))
    for i in date_diff:
        bank[i]["transaction_date"] = (day - timedelta(days=1)).isoformat()
    for i in status_diff:
        bank[i]["status"] = "PENDING" if bank[i]["status"] != "PENDING" else "COMPLETED"
    duplicates = [dict(bank[i]) for i in duplicated]
    bank = [row for i, row in enumerate(bank) if i not in set(missing_from_file)] + duplicates

    # Payments the bank processed that are not in our ledger.
    bank += [synthetic_transaction(rng, count + i, day) for i in range(1, q + 1)]
    rng.shuffle(bank)
    return pd.DataFrame(ledger), pd.DataFrame(bank)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--date", type=date.fromisoformat, default=date(2026, 10, 21))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("sample_data"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    ledger, bank = generate(args.count, args.date, args.seed)
    ledger.to_csv(args.out / "ledger_transactions.csv", index=False)
    bank.to_csv(args.out / "bank_daily_file.csv", index=False)
    bank.to_excel(args.out / "bank_daily_file.xlsx", index=False)
    print(f"Wrote {len(ledger)} ledger rows and {len(bank)} bank-file rows to {args.out}/")


if __name__ == "__main__":
    main()
