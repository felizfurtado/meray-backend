from datetime import datetime
import uuid


def generate_sif(company, payroll_records, month, year):

    lines = []

    total_salary = sum([p.net_salary for p in payroll_records])

    today = datetime.today().strftime("%Y%m%d")

    header = [
        "100",
        company.employer_eid,
        company.employer_name,
        company.bank_swift_code,
        company.payroll_iban,
        f"{year}{str(month).zfill(2)}",
        today,
        str(uuid.uuid4())[:10],
        len(payroll_records),
        total_salary
    ]

    lines.append(",".join(map(str, header)))

    for record in payroll_records:

        employee = record.employee

        row = [
            "200",
            employee.labour_card_number,
            employee.name,
            employee.bank_swift_code,
            employee.bank_account,
            "M",
            record.days_worked,
            record.basic_salary,
            record.allowances,
            record.deductions,
            record.net_salary,
            today
        ]

        lines.append(",".join(map(str, row)))

    trailer = [
        "300",
        len(payroll_records),
        total_salary,
        today
    ]

    lines.append(",".join(map(str, trailer)))

    return "\n".join(lines)