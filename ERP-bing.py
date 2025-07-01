import os
import datetime
import csv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from num2words import num2words

# Constants
CLIENTS = {
    "1": ("A.T Commodities", "Mr Adnan"),
    "2": ("Niazi Bricks", "Mr Talha Niazi Sb")
}

EMPLOYEES = [
    "Inam ur Rehman Ansari",
    "Ebad Ur Rehman",
    "Talha Sidiqqui",
    "Asad Anwar"
]

DATA_DIR = "records"
os.makedirs(DATA_DIR, exist_ok=True)


def get_invoice_input():
    print("Select Client:")
    for key, (company, name) in CLIENTS.items():
        print(f"{key}. {company} ({name})")
    client_key = input("Enter option (1 or 2): ")
    company, customer = CLIENTS.get(client_key, ("Unknown", "Unknown"))

    invoice_no = input("Invoice No.: ")
    delivery_date = input("Delivery Date (DD-MMM-YYYY): ")
    vehicle_no = input("Vehicle No.: ")
    quantity = float(input("Quantity (M/TON): "))
    unit_price = float(input("Unit Price (Rs): "))
    return customer, company, invoice_no, delivery_date, vehicle_no, quantity, unit_price


def generate_invoice_pdf(customer, company, invoice_no, delivery_date, vehicle_no, quantity, unit_price, total):
    amount_in_words = num2words(total, lang='en_IN').title().replace("And", "") + " Rupees Only"
    file_name = os.path.join(DATA_DIR, f"Invoice_{invoice_no}.pdf")
    doc = SimpleDocTemplate(file_name, pagesize=letter)
    elements = []

    elements.append(Spacer(1, 14 * 12))
    styles = getSampleStyleSheet()
    style_center = ParagraphStyle(name='Center', alignment=1, parent=styles['Normal'])

    elements.append(Paragraph("Invoice", styles['Heading2']))
    elements.append(Paragraph(f"Submitted on: {datetime.datetime.now().strftime('%d/%m/%Y')}", style_center))
    elements.append(Spacer(1, 20))

    details_table = Table([
        ['Invoice for', 'Payable to', 'Invoice #'],
        [customer, company, invoice_no]
    ], colWidths=[200, 150, 100])
    details_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('LINEBELOW', (0, 1), (-1, 1), 1, colors.black),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 20))

    items_table = Table([
        ['Description', 'Delivery Date', 'Qty (M/TON)', 'Unit Price', 'Total Price'],
        [f'Coal ({vehicle_no})', delivery_date, f'{quantity:.3f}', f'Rs{unit_price:,.0f}', f'Rs{total:,.0f}']
    ], colWidths=[120, 90, 80, 80, 90])
    items_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
        ('LINEBELOW', (0, 1), (-1, 1), 1, colors.black),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Notes:", styles['Normal']))
    elements.append(Paragraph(f"Rs{total:,.0f}", styles['Normal']))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(amount_in_words, styles['Normal']))

    doc.build(elements)
    print(f"Invoice PDF saved as {file_name}")


def mark_attendance():
    today = datetime.date.today().strftime("%Y-%m-%d")
    filename = os.path.join(DATA_DIR, f"attendance_{today}.csv")
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Employee", "Present (Y/N)"])
        for emp in EMPLOYEES:
            status = input(f"Is {emp} present today? (Y/N): ")
            writer.writerow([emp, status])
    print(f"Attendance for {today} saved in {filename}")


def log_delivery():
    filename = os.path.join(DATA_DIR, "deliveries.csv")
    header = ["Date", "Client", "Vehicle No", "Quantity"]
    if not os.path.exists(filename):
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)

    date = input("Delivery Date (DD-MMM-YYYY): ")
    client = input("Client Name: ")
    vehicle = input("Vehicle No: ")
    qty = input("Quantity: ")

    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([date, client, vehicle, qty])

    print(f"Delivery logged in {filename}")


def main():
    while True:
        print("\nERP CLI Menu:")
        print("1. Generate Invoice")
        print("2. Mark Attendance")
        print("3. Log Delivery")
        print("4. Exit")
        choice = input("Select option: ")

        if choice == "1":
            values = get_invoice_input()
            total = values[5] * values[6]
            generate_invoice_pdf(*values, total)
        elif choice == "2":
            mark_attendance()
        elif choice == "3":
            log_delivery()
        elif choice == "4":
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
