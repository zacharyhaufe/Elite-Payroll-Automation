#!/usr/bin/env python3
"""Commission calculator for payroll automation."""

import csv
import json
from pathlib import Path
from typing import Dict, List

EMPLOYEE_FILE = Path("employees.json")
JOBS_FILE = Path("jobs.csv")

SOLO_COMMISSION_RATE = 0.25

# Per-employee solo rate overrides (name lowercase -> rate)
SOLO_COMMISSION_RATE_OVERRIDES = {
    "kaiden": 0.30,
}


def load_employees(path: Path) -> Dict[str, Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Employee data not found at: {path}")

    with path.open("r", encoding="utf-8") as f:
        records = json.load(f)

    employees = {}
    for record in records:
        emp_id = str(record.get("id", "")).strip()
        if not emp_id:
            continue
        commission_rate = float(record.get("commission_rate", 0))
        employees[emp_id] = {
            "id": emp_id,
            "name": record.get("name", emp_id),
            "commission_rate": commission_rate,
        }

    return employees


def parse_employee_ids(raw: str) -> List[str]:
    # Job row may provide multiple IDs separated by comma or semicolon
    parts = [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    return parts


def process_jobs(employees: Dict[str, Dict], path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"Jobs file not found at: {path}")

    output_rows = []
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            job_id = row.get("job_id", "").strip()
            if not job_id:
                continue

            subtotal_str = row.get("subtotal", "0").strip()
            try:
                subtotal = float(subtotal_str)
            except ValueError:
                print(f"Skipping invalid subtotal for job {job_id}: {subtotal_str}")
                continue

            raw_emps = str(row.get("employee_ids", "") or "").strip()

            # If employee IDs are in multiple columns (csv library), combine them
            extra_ids = []
            for key, value in row.items():
                if key in ("job_id", "subtotal", "employee_ids"):
                    continue
                if key is None:
                    # DictReader stores extra values under None key as a list
                    if isinstance(value, list):
                        extra_ids += [str(x).strip() for x in value if str(x).strip()]
                    elif str(value).strip():
                        extra_ids.append(str(value).strip())
                else:
                    if str(value).strip():
                        extra_ids.append(str(value).strip())

            if extra_ids:
                if raw_emps:
                    raw_emps = ",".join([raw_emps] + extra_ids)
                else:
                    raw_emps = ",".join(extra_ids)

            employees_for_job = parse_employee_ids(raw_emps)
            if not employees_for_job:
                print(f"Skipping job {job_id}: no employees listed")
                continue

            solo = len(employees_for_job) == 1
            for emp_token in employees_for_job:
                emp = employees.get(emp_token)

                # fallback to name match (case-insensitive) when input uses names
                if emp is None:
                    candidate = next(
                        (e for e in employees.values() if e["name"].lower() == emp_token.lower()),
                        None,
                    )
                    if candidate:
                        emp = candidate

                if emp is None:
                    print(f"Warning: employee '{emp_token}' not found for job {job_id}, skipping")
                    continue

                if solo:
                    rate = SOLO_COMMISSION_RATE_OVERRIDES.get(emp["name"].lower(), SOLO_COMMISSION_RATE)
                else:
                    rate = emp["commission_rate"]
                earned = subtotal * rate

                output_rows.append({
                    "job_id": job_id,
                    "employee_id": emp["id"],
                    "employee_name": emp["name"],
                    "subtotal": subtotal,
                    "commission_rate": rate,
                    "earned": round(earned, 2),
                    "split_type": "solo" if solo else "shared",
                })

    return output_rows


def print_report(rows: List[Dict]):
    if not rows:
        print("No commission rows to report.")
        return

    # Group rows by employee
    by_emp = {}
    for r in rows:
        emp_name = r['employee_name']
        by_emp.setdefault(emp_name, []).append(r)

    lines = []
    for emp_name in sorted(by_emp.keys()):
        emp_rows = by_emp[emp_name]
        total = sum(r['earned'] for r in emp_rows)
        emp_id = emp_rows[0]['employee_id']
        lines.append(f"{emp_name} ({emp_id})")
        for r in emp_rows:
            rate_pct = r['commission_rate'] * 100
            lines.append(
                f"  {r['job_id']}: ${r['earned']:.2f} ({rate_pct:.0f}% commission on ${r['subtotal']:.2f})"
            )
        lines.append(f"  Total: ${total:.2f}")
        lines.append("")

    print("\n".join(lines))


def save_report(rows: List[Dict], out_path: Path):
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["job_id", "employee_id", "employee_name", "subtotal", "commission_rate", "earned", "split_type"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute employee commissions from jobs data.")
    parser.add_argument("--employees", default=EMPLOYEE_FILE, help="employees JSON path")
    parser.add_argument("--jobs", default=JOBS_FILE, help="jobs CSV path")
    parser.add_argument("--output", default=None, help="optional output CSV report path (if not provided, prints only)")

    args = parser.parse_args()

    employees = load_employees(Path(args.employees))
    rows = process_jobs(employees, Path(args.jobs))

    print_report(rows)

    if args.output:
        save_report(rows, Path(args.output))
        print(f"\nSaved commission report to {args.output}")

