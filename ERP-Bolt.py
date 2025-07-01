#!/usr/bin/env python3
"""
A.T Commodities ERP System
A complete ERP solution for attendance, invoicing, and delivery management
"""

import os
import json
import sqlite3
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template_string, send_file, redirect, url_for
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import csv
import io
import base64

app = Flask(__name__)
app.secret_key = 'at_commodities_secret_key_2025'

class DatabaseManager:
    def __init__(self, db_name='at_commodities.db'):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialize database with all required tables"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Employees table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                email TEXT NOT NULL
            )
        ''')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                employee_name TEXT NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT,
                work_location TEXT NOT NULL,
                date TEXT NOT NULL,
                total_hours REAL,
                FOREIGN KEY (employee_id) REFERENCES employees (id)
            )
        ''')
        
        # Clients table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                address TEXT NOT NULL
            )
        ''')
        
        # Invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT NOT NULL UNIQUE,
                client_id INTEGER,
                client_name TEXT NOT NULL,
                date TEXT NOT NULL,
                items TEXT NOT NULL,
                subtotal REAL NOT NULL,
                tax REAL NOT NULL,
                discount REAL NOT NULL,
                total REAL NOT NULL,
                status TEXT DEFAULT 'draft',
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
        ''')
        
        # Deliveries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deliveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicle_number TEXT NOT NULL,
                driver_name TEXT NOT NULL,
                delivery_date TEXT NOT NULL,
                delivery_time TEXT NOT NULL,
                destination TEXT NOT NULL,
                load_details TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Insert default employees if table is empty
        cursor.execute('SELECT COUNT(*) FROM employees')
        if cursor.fetchone()[0] == 0:
            employees = [
                ('Ahmad Ali', 'Operations', 'ahmad@atcommodities.com'),
                ('Fatima Khan', 'Sales', 'fatima@atcommodities.com'),
                ('Muhammad Hassan', 'Logistics', 'hassan@atcommodities.com'),
                ('Aisha Malik', 'Accounts', 'aisha@atcommodities.com'),
                ('Usman Sheikh', 'Warehouse', 'usman@atcommodities.com')
            ]
            cursor.executemany('INSERT INTO employees (name, department, email) VALUES (?, ?, ?)', employees)
        
        # Insert default clients if table is empty
        cursor.execute('SELECT COUNT(*) FROM clients')
        if cursor.fetchone()[0] == 0:
            clients = [
                ('A.L.U International', 'Mr. Adnan Sb', 'Industrial Area, Karachi'),
                ('Niazi Bricks', 'Mr. Talha Niazi Sb', 'Brick Kiln Area, Lahore')
            ]
            cursor.executemany('INSERT INTO clients (name, contact, address) VALUES (?, ?, ?)', clients)
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query, params=None, fetch=False):
        """Execute database query"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        if fetch:
            result = cursor.fetchall()
        else:
            result = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return result

class InvoiceGenerator:
    def __init__(self):
        pass
    
    def number_to_words(self, num):
        """Convert number to words in Pakistani format"""
        if num == 0:
            return "Zero"
        
        ones = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine']
        teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
        tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']
        
        def convert_hundreds(n):
            result = ''
            if n >= 100:
                result += ones[n // 100] + ' Hundred '
                n %= 100
            if n >= 20:
                result += tens[n // 10] + ' '
                n %= 10
            elif n >= 10:
                result += teens[n - 10] + ' '
                return result.strip()
            if n > 0:
                result += ones[n] + ' '
            return result.strip()
        
        if num < 1000:
            return convert_hundreds(num) + ' Rupees Only'
        elif num < 100000:
            thousands = num // 1000
            remainder = num % 1000
            result = convert_hundreds(thousands) + ' Thousand'
            if remainder > 0:
                result += ', ' + convert_hundreds(remainder)
            return result + ' Rupees Only'
        elif num < 10000000:
            lakhs = num // 100000
            remainder = num % 100000
            result = convert_hundreds(lakhs) + ' Lakh'
            if remainder >= 1000:
                thousands = remainder // 1000
                remainder = remainder % 1000
                result += ', ' + convert_hundreds(thousands) + ' Thousand'
            if remainder > 0:
                result += ', ' + convert_hundreds(remainder)
            return result + ' Rupees Only'
        else:
            crores = num // 10000000
            remainder = num % 10000000
            result = convert_hundreds(crores) + ' Crore'
            if remainder >= 100000:
                lakhs = remainder // 100000
                remainder = remainder % 100000
                result += ', ' + convert_hundreds(lakhs) + ' Lakh'
            if remainder >= 1000:
                thousands = remainder // 1000
                remainder = remainder % 1000
                result += ', ' + convert_hundreds(thousands) + ' Thousand'
            if remainder > 0:
                result += ', ' + convert_hundreds(remainder)
            return result + ' Rupees Only'
    
    def generate_pdf(self, invoice_data, filename=None):
        """Generate PDF invoice"""
        if not filename:
            filename = f"Invoice_{invoice_data['invoice_number']}.pdf"
        
        doc = SimpleDocTemplate(filename, pagesize=A4, topMargin=0.5*inch, bottomMargin=1*inch, leftMargin=1*inch, rightMargin=1*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Add space at top
        story.append(Spacer(1, 14 * 14))
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=20, alignment=TA_CENTER, fontName='Helvetica-Bold')
        story.append(Paragraph("Invoice", title_style))
        
        # Invoice details
        items = json.loads(invoice_data['items'])
        total_amount = float(invoice_data['total'])
        
        # Create invoice table
        table_data = [['Description', 'Quantity', 'Unit Price', 'Total']]
        for item in items:
            table_data.append([
                item['description'],
                str(item['quantity']),
                f"Rs{item['unit_price']:,.2f}",
                f"Rs{item['total']:,.2f}"
            ])
        
        table = Table(table_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 20))
        
        # Total
        story.append(Paragraph(f"<b>Total: Rs{total_amount:,.2f}</b>", styles['Normal']))
        story.append(Paragraph(f"Amount in words: {self.number_to_words(int(total_amount))}", styles['Normal']))
        
        doc.build(story)
        return filename

# Initialize components
db = DatabaseManager()
invoice_gen = InvoiceGenerator()

# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A.T Commodities ERP System</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; }
        .sidebar { width: 250px; height: 100vh; background: #1e293b; color: white; position: fixed; left: 0; top: 0; }
        .sidebar-header { padding: 20px; border-bottom: 1px solid #334155; }
        .sidebar-header h1 { font-size: 20px; margin-bottom: 5px; }
        .sidebar-header p { font-size: 12px; color: #94a3b8; }
        .sidebar-nav { padding: 20px 0; }
        .nav-item { display: block; padding: 12px 20px; color: #cbd5e1; text-decoration: none; transition: all 0.3s; }
        .nav-item:hover, .nav-item.active { background: #3b82f6; color: white; }
        .main-content { margin-left: 250px; padding: 30px; }
        .header { background: white; padding: 20px 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px; }
        .header h1 { font-size: 28px; color: #1e293b; margin-bottom: 5px; }
        .header p { color: #64748b; }
        .card { background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 25px; margin-bottom: 20px; }
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-weight: 600; color: #374151; }
        .form-control { width: 100%; padding: 12px; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 14px; }
        .form-control:focus { border-color: #3b82f6; outline: none; }
        .btn { padding: 12px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.3s; }
        .btn-primary { background: #3b82f6; color: white; }
        .btn-primary:hover { background: #2563eb; }
        .btn-success { background: #10b981; color: white; }
        .btn-success:hover { background: #059669; }
        .btn-danger { background: #ef4444; color: white; }
        .btn-danger:hover { background: #dc2626; }
        .table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .table th, .table td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        .table th { background: #f8fafc; font-weight: 600; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 25px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .stat-number { font-size: 32px; font-weight: bold; margin-bottom: 5px; }
        .stat-label { color: #64748b; font-size: 14px; }
        .form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .alert { padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .alert-success { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
        .alert-error { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; }
        .modal-content { background: white; margin: 5% auto; padding: 30px; border-radius: 10px; max-width: 600px; max-height: 80vh; overflow-y: auto; }
        .close { float: right; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close:hover { color: #ef4444; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h1>🏢 A.T Commodities</h1>
            <p>ERP System</p>
        </div>
        <nav class="sidebar-nav">
            <a href="/" class="nav-item {{ 'active' if active_page == 'dashboard' else '' }}">📊 Dashboard</a>
            <a href="/attendance" class="nav-item {{ 'active' if active_page == 'attendance' else '' }}">🕒 Attendance</a>
            <a href="/invoices" class="nav-item {{ 'active' if active_page == 'invoices' else '' }}">📄 Invoices</a>
            <a href="/deliveries" class="nav-item {{ 'active' if active_page == 'deliveries' else '' }}">🚚 Deliveries</a>
            <a href="/downloads" class="nav-item {{ 'active' if active_page == 'downloads' else '' }}">📥 Downloads</a>
        </nav>
    </div>
    <div class="main-content">
        {% block content %}{% endblock %}
    </div>
    <script>
        function showModal(modalId) {
            document.getElementById(modalId).style.display = 'block';
        }
        function hideModal(modalId) {
            document.getElementById(modalId).style.display = 'none';
        }
        function confirmDelete(message) {
            return confirm(message || 'Are you sure you want to delete this item?');
        }
    </script>
</body>
</html>
"""

DASHBOARD_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="header">
    <h1>📊 Dashboard</h1>
    <p>Welcome to A.T Commodities ERP System</p>
</div>

<div class="stats-grid">
    <div class="stat-card">
        <div class="stat-number" style="color: #3b82f6;">{{ stats.total_employees }}</div>
        <div class="stat-label">👥 Total Employees</div>
    </div>
    <div class="stat-card">
        <div class="stat-number" style="color: #10b981;">{{ stats.today_attendance }}</div>
        <div class="stat-label">🕒 Today's Attendance</div>
    </div>
    <div class="stat-card">
        <div class="stat-number" style="color: #8b5cf6;">{{ stats.total_invoices }}</div>
        <div class="stat-label">📄 Total Invoices</div>
    </div>
    <div class="stat-card">
        <div class="stat-number" style="color: #f59e0b;">{{ stats.active_deliveries }}</div>
        <div class="stat-label">🚚 Active Deliveries</div>
    </div>
</div>

<div class="form-row">
    <div class="card">
        <h3>🚀 Quick Actions</h3>
        <div style="margin-top: 20px;">
            <a href="/attendance" class="btn btn-primary" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">🕒 Mark Attendance</a>
            <a href="/invoices" class="btn btn-success" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">📄 Create Invoice</a>
            <a href="/deliveries" class="btn" style="background: #f59e0b; color: white; display: block; text-decoration: none; text-align: center;">🚚 Add Delivery</a>
        </div>
    </div>
    <div class="card">
        <h3>📊 System Status</h3>
        <div style="margin-top: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <span>Database Status</span>
                <span style="background: #10b981; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;">Active</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                <span>Last Backup</span>
                <span>Today, 6:00 AM</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>Storage Used</span>
                <span>{{ stats.storage_used }} KB</span>
            </div>
        </div>
    </div>
</div>
""")

ATTENDANCE_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
<div class="header">
    <h1>🕒 Daily Attendance</h1>
    <p>Track employee attendance and work locations</p>
</div>

{% if message %}
<div class="alert alert-{{ message_type }}">{{ message }}</div>
{% endif %}

<div class="form-row">
    <div class="card">
        <h3>✅ Check In</h3>
        <form method="POST" action="/attendance/checkin">
            <div class="form-group">
                <label>Select Employee</label>
                <select name="employee_id" class="form-control" required>
                    <option value="">Choose an employee</option>
                    {% for emp in employees %}
                    <option value="{{ emp[0] }}">{{ emp[1] }} - {{ emp[2] }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>Work Location</label>
                <select name="work_location" class="form-control" required>
                    <option value="office">🏢 Office</option>
                    <option value="warehouse">🏭 Warehouse</option>
                    <option value="field">🌾 Field</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Check In</button>
        </form>
    </div>
    
    <div class="card">
        <h3>📊 Today's Summary</h3>
        <div style="margin-top: 20px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                <span>Total Check-ins</span>
                <span style="font-size: 24px; font-weight: bold; color: #10b981;">{{ today_stats.total }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 15px;">
                <span>Checked Out</span>
                <span style="font-size: 24px; font-weight: bold; color: #3b82f6;">{{ today_stats.checked_out }}</span>
            </div>
            <hr style="margin: 15px 0;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span>🏢 Office</span>
                <span>{{ today_stats.office }}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span>🏭 Warehouse</span>
                <span>{{ today_stats.warehouse }}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
                <span>🌾 Field</span>
                <span>{{ today_stats.field }}</span>
            </div>
        </div>
    </div>
</div>

<div class="card">
    <h3>📋 Today's Attendance Records</h3>
    <table class="table">
        <thead>
            <tr>
                <th>Employee</th>
                <th>Check In</th>
                <th>Check Out</th>
                <th>Location</th>
                <th>Total Hours</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
            {% for record in today_records %}
            <tr>
                <td>{{ record[2] }}</td>
                <td>{{ record[3] }}</td>
                <td>{{ record[4] or '-' }}</td>
                <td>
                    <span style="background: {% if record[5] == 'office' %}#dbeafe{% elif record[5] == 'warehouse' %}#d1fae5{% else %}#fed7aa{% endif %}; 
                                 color: {% if record[5] == 'office' %}#1e40af{% elif record[5] == 'warehouse' %}#065f46{% else %}#9a3412{% endif %}; 
                                 padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                        {{ record[5].title() }}
                    </span>
                </td>
                <td>{{ record[7] or '-' }}{% if record[7] %}h{% endif %}</td>
                <td>
                    {% if not record[4] %}
                    <form method="POST" action="/attendance/checkout" style="display: inline;">
                        <input type="hidden" name="record_id" value="{{ record[0] }}">
                        <button type="submit" class="btn btn-danger" style="padding: 6px 12px; font-size: 12px;">Check Out</button>
                    </form>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% if not today_records %}
    <p style="text-align: center; color: #64748b; margin-top: 20px;">No attendance records for today</p>
    {% endif %}
</div>
""")

# Routes
@app.route('/')
def dashboard():
    # Get statistics
    today = date.today().isoformat()
    
    total_employees = db.execute_query('SELECT COUNT(*) FROM employees', fetch=True)[0][0]
    today_attendance = db.execute_query('SELECT COUNT(*) FROM attendance WHERE date = ?', (today,), fetch=True)[0][0]
    total_invoices = db.execute_query('SELECT COUNT(*) FROM invoices', fetch=True)[0][0]
    active_deliveries = db.execute_query("SELECT COUNT(*) FROM deliveries WHERE status != 'delivered'", fetch=True)[0][0]
    
    # Calculate storage used (rough estimate)
    storage_used = os.path.getsize('at_commodities.db') // 1024 if os.path.exists('at_commodities.db') else 0
    
    stats = {
        'total_employees': total_employees,
        'today_attendance': today_attendance,
        'total_invoices': total_invoices,
        'active_deliveries': active_deliveries,
        'storage_used': storage_used
    }
    
    return render_template_string(DASHBOARD_TEMPLATE, active_page='dashboard', stats=stats)

@app.route('/attendance')
def attendance():
    employees = db.execute_query('SELECT id, name, department FROM employees', fetch=True)
    
    today = date.today().isoformat()
    today_records = db.execute_query('SELECT * FROM attendance WHERE date = ? ORDER BY check_in DESC', (today,), fetch=True)
    
    # Calculate today's stats
    total = len(today_records)
    checked_out = len([r for r in today_records if r[4]])  # check_out is not None
    office = len([r for r in today_records if r[5] == 'office'])
    warehouse = len([r for r in today_records if r[5] == 'warehouse'])
    field = len([r for r in today_records if r[5] == 'field'])
    
    today_stats = {
        'total': total,
        'checked_out': checked_out,
        'office': office,
        'warehouse': warehouse,
        'field': field
    }
    
    return render_template_string(ATTENDANCE_TEMPLATE, 
                                active_page='attendance', 
                                employees=employees, 
                                today_records=today_records,
                                today_stats=today_stats)

@app.route('/attendance/checkin', methods=['POST'])
def attendance_checkin():
    employee_id = request.form.get('employee_id')
    work_location = request.form.get('work_location')
    
    # Get employee name
    employee = db.execute_query('SELECT name FROM employees WHERE id = ?', (employee_id,), fetch=True)
    if not employee:
        return redirect(url_for('attendance'))
    
    employee_name = employee[0][0]
    today = date.today().isoformat()
    current_time = datetime.now().strftime('%H:%M:%S')
    
    # Check if already checked in today
    existing = db.execute_query('SELECT id FROM attendance WHERE employee_id = ? AND date = ?', (employee_id, today), fetch=True)
    if existing:
        return render_template_string(ATTENDANCE_TEMPLATE.replace('{% if message %}', '{% if True %}'), 
                                    active_page='attendance',
                                    message='Employee already checked in today!',
                                    message_type='error',
                                    employees=db.execute_query('SELECT id, name, department FROM employees', fetch=True),
                                    today_records=db.execute_query('SELECT * FROM attendance WHERE date = ? ORDER BY check_in DESC', (today,), fetch=True),
                                    today_stats={'total': 0, 'checked_out': 0, 'office': 0, 'warehouse': 0, 'field': 0})
    
    # Insert attendance record
    db.execute_query('''
        INSERT INTO attendance (employee_id, employee_name, check_in, work_location, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (employee_id, employee_name, current_time, work_location, today))
    
    return redirect(url_for('attendance'))

@app.route('/attendance/checkout', methods=['POST'])
def attendance_checkout():
    record_id = request.form.get('record_id')
    current_time = datetime.now().strftime('%H:%M:%S')
    
    # Get check-in time to calculate hours
    record = db.execute_query('SELECT check_in FROM attendance WHERE id = ?', (record_id,), fetch=True)
    if record:
        check_in_time = datetime.strptime(record[0][0], '%H:%M:%S')
        check_out_time = datetime.strptime(current_time, '%H:%M:%S')
        total_hours = (check_out_time - check_in_time).total_seconds() / 3600
        
        db.execute_query('''
            UPDATE attendance SET check_out = ?, total_hours = ? WHERE id = ?
        ''', (current_time, round(total_hours, 2), record_id))
    
    return redirect(url_for('attendance'))

@app.route('/invoices')
def invoices():
    invoices_data = db.execute_query('SELECT * FROM invoices ORDER BY date DESC', fetch=True)
    clients = db.execute_query('SELECT * FROM clients', fetch=True)
    
    INVOICES_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="header">
        <h1>📄 Invoice Generator</h1>
        <p>Create and manage invoices for your clients</p>
        <button onclick="showModal('invoiceModal')" class="btn btn-primary" style="float: right; margin-top: -40px;">➕ New Invoice</button>
    </div>

    {% if message %}
    <div class="alert alert-{{ message_type }}">{{ message }}</div>
    {% endif %}

    <div class="card">
        <h3>📋 Invoice History</h3>
        <table class="table">
            <thead>
                <tr>
                    <th>Invoice #</th>
                    <th>Client</th>
                    <th>Date</th>
                    <th>Total</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for invoice in invoices %}
                <tr>
                    <td>{{ invoice[1] }}</td>
                    <td>{{ invoice[3] }}</td>
                    <td>{{ invoice[4] }}</td>
                    <td>Rs{{ "%.2f"|format(invoice[9]) }}</td>
                    <td>
                        <span style="background: {% if invoice[10] == 'paid' %}#d1fae5{% elif invoice[10] == 'sent' %}#dbeafe{% else %}#f3f4f6{% endif %}; 
                                     color: {% if invoice[10] == 'paid' %}#065f46{% elif invoice[10] == 'sent' %}#1e40af{% else %}#374151{% endif %}; 
                                     padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                            {{ invoice[10].title() }}
                        </span>
                    </td>
                    <td>
                        <a href="/invoices/download/{{ invoice[0] }}" class="btn btn-primary" style="padding: 6px 12px; font-size: 12px; text-decoration: none;">📥 PDF</a>
                        <form method="POST" action="/invoices/delete/{{ invoice[0] }}" style="display: inline;" onsubmit="return confirmDelete()">
                            <button type="submit" class="btn btn-danger" style="padding: 6px 12px; font-size: 12px;">🗑️ Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% if not invoices %}
        <p style="text-align: center; color: #64748b; margin-top: 20px;">No invoices created yet</p>
        {% endif %}
    </div>

    <!-- Invoice Modal -->
    <div id="invoiceModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="hideModal('invoiceModal')">&times;</span>
            <h3>📄 Create New Invoice</h3>
            <form method="POST" action="/invoices/create">
                <div class="form-group">
                    <label>Client</label>
                    <select name="client_id" class="form-control" required>
                        <option value="">Select a client</option>
                        {% for client in clients %}
                        <option value="{{ client[0] }}">{{ client[1] }} - {{ client[2] }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label>Invoice Number</label>
                    <input type="text" name="invoice_number" class="form-control" placeholder="e.g., ATC-001" required>
                </div>
                <div id="items-container">
                    <div class="item-row">
                        <h4>Item 1</h4>
                        <div class="form-row">
                            <div class="form-group">
                                <label>Description</label>
                                <input type="text" name="description[]" class="form-control" required>
                            </div>
                            <div class="form-group">
                                <label>Quantity</label>
                                <input type="number" name="quantity[]" class="form-control" step="0.01" required>
                            </div>
                            <div class="form-group">
                                <label>Unit Price</label>
                                <input type="number" name="unit_price[]" class="form-control" step="0.01" required>
                            </div>
                        </div>
                    </div>
                </div>
                <button type="button" onclick="addItem()" class="btn btn-success" style="margin-bottom: 20px;">➕ Add Item</button>
                <div class="form-row">
                    <div class="form-group">
                        <label>Tax (%)</label>
                        <input type="number" name="tax_percent" class="form-control" step="0.01" value="0">
                    </div>
                    <div class="form-group">
                        <label>Discount (%)</label>
                        <input type="number" name="discount_percent" class="form-control" step="0.01" value="0">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">Create Invoice</button>
            </form>
        </div>
    </div>

    <script>
        let itemCount = 1;
        function addItem() {
            itemCount++;
            const container = document.getElementById('items-container');
            const newItem = document.createElement('div');
            newItem.className = 'item-row';
            newItem.innerHTML = `
                <h4>Item ${itemCount} <button type="button" onclick="removeItem(this)" class="btn btn-danger" style="padding: 4px 8px; font-size: 12px; float: right;">Remove</button></h4>
                <div class="form-row">
                    <div class="form-group">
                        <label>Description</label>
                        <input type="text" name="description[]" class="form-control" required>
                    </div>
                    <div class="form-group">
                        <label>Quantity</label>
                        <input type="number" name="quantity[]" class="form-control" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Unit Price</label>
                        <input type="number" name="unit_price[]" class="form-control" step="0.01" required>
                    </div>
                </div>
            `;
            container.appendChild(newItem);
        }
        function removeItem(button) {
            button.closest('.item-row').remove();
        }
    </script>
    """)
    
    return render_template_string(INVOICES_TEMPLATE, 
                                active_page='invoices', 
                                invoices=invoices_data,
                                clients=clients)

@app.route('/invoices/create', methods=['POST'])
def create_invoice():
    client_id = request.form.get('client_id')
    invoice_number = request.form.get('invoice_number')
    descriptions = request.form.getlist('description[]')
    quantities = request.form.getlist('quantity[]')
    unit_prices = request.form.getlist('unit_price[]')
    tax_percent = float(request.form.get('tax_percent', 0))
    discount_percent = float(request.form.get('discount_percent', 0))
    
    # Get client name
    client = db.execute_query('SELECT name FROM clients WHERE id = ?', (client_id,), fetch=True)
    if not client:
        return redirect(url_for('invoices'))
    
    client_name = client[0][0]
    
    # Build items
    items = []
    subtotal = 0
    for i in range(len(descriptions)):
        quantity = float(quantities[i])
        unit_price = float(unit_prices[i])
        total = quantity * unit_price
        subtotal += total
        
        items.append({
            'description': descriptions[i],
            'quantity': quantity,
            'unit_price': unit_price,
            'total': total
        })
    
    # Calculate totals
    tax = subtotal * (tax_percent / 100)
    discount = subtotal * (discount_percent / 100)
    total = subtotal + tax - discount
    
    # Save invoice
    db.execute_query('''
        INSERT INTO invoices (invoice_number, client_id, client_name, date, items, subtotal, tax, discount, total)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (invoice_number, client_id, client_name, date.today().isoformat(), 
          json.dumps(items), subtotal, tax, discount, total))
    
    return redirect(url_for('invoices'))

@app.route('/invoices/download/<int:invoice_id>')
def download_invoice(invoice_id):
    invoice = db.execute_query('SELECT * FROM invoices WHERE id = ?', (invoice_id,), fetch=True)
    if not invoice:
        return "Invoice not found", 404
    
    invoice_data = {
        'invoice_number': invoice[0][1],
        'client_name': invoice[0][3],
        'date': invoice[0][4],
        'items': invoice[0][5],
        'total': invoice[0][9]
    }
    
    filename = invoice_gen.generate_pdf(invoice_data)
    return send_file(filename, as_attachment=True)

@app.route('/invoices/delete/<int:invoice_id>', methods=['POST'])
def delete_invoice(invoice_id):
    db.execute_query('DELETE FROM invoices WHERE id = ?', (invoice_id,))
    return redirect(url_for('invoices'))

@app.route('/deliveries')
def deliveries():
    deliveries_data = db.execute_query('SELECT * FROM deliveries ORDER BY delivery_date DESC, delivery_time DESC', fetch=True)
    
    DELIVERIES_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="header">
        <h1>🚚 Vehicle Delivery Ledger</h1>
        <p>Track vehicle deliveries and logistics</p>
        <button onclick="showModal('deliveryModal')" class="btn btn-primary" style="float: right; margin-top: -40px;">➕ New Delivery</button>
    </div>

    {% if message %}
    <div class="alert alert-{{ message_type }}">{{ message }}</div>
    {% endif %}

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number" style="color: #3b82f6;">{{ stats.total }}</div>
            <div class="stat-label">🚚 Total Deliveries</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #f59e0b;">{{ stats.pending }}</div>
            <div class="stat-label">⏳ Pending</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #3b82f6;">{{ stats.in_transit }}</div>
            <div class="stat-label">🚛 In Transit</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #10b981;">{{ stats.delivered }}</div>
            <div class="stat-label">✅ Delivered</div>
        </div>
    </div>

    <div class="card">
        <h3>📋 Delivery Records</h3>
        <table class="table">
            <thead>
                <tr>
                    <th>Vehicle</th>
                    <th>Driver</th>
                    <th>Date & Time</th>
                    <th>Destination</th>
                    <th>Load Details</th>
                    <th>Status</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                {% for delivery in deliveries %}
                <tr>
                    <td>🚚 {{ delivery[1] }}</td>
                    <td>👤 {{ delivery[2] }}</td>
                    <td>{{ delivery[3] }}<br><small>{{ delivery[4] }}</small></td>
                    <td>📍 {{ delivery[5] }}</td>
                    <td>{{ delivery[6] or '-' }}</td>
                    <td>
                        <form method="POST" action="/deliveries/update_status/{{ delivery[0] }}" style="display: inline;">
                            <select name="status" onchange="this.form.submit()" 
                                    style="background: {% if delivery[7] == 'pending' %}#fef3c7{% elif delivery[7] == 'in-transit' %}#dbeafe{% else %}#d1fae5{% endif %}; 
                                           color: {% if delivery[7] == 'pending' %}#92400e{% elif delivery[7] == 'in-transit' %}#1e40af{% else %}#065f46{% endif %}; 
                                           border: none; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                                <option value="pending" {% if delivery[7] == 'pending' %}selected{% endif %}>Pending</option>
                                <option value="in-transit" {% if delivery[7] == 'in-transit' %}selected{% endif %}>In Transit</option>
                                <option value="delivered" {% if delivery[7] == 'delivered' %}selected{% endif %}>Delivered</option>
                            </select>
                        </form>
                    </td>
                    <td>
                        <form method="POST" action="/deliveries/delete/{{ delivery[0] }}" style="display: inline;" onsubmit="return confirmDelete()">
                            <button type="submit" class="btn btn-danger" style="padding: 6px 12px; font-size: 12px;">🗑️ Delete</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% if not deliveries %}
        <p style="text-align: center; color: #64748b; margin-top: 20px;">No delivery records found</p>
        {% endif %}
    </div>

    <!-- Delivery Modal -->
    <div id="deliveryModal" class="modal">
        <div class="modal-content">
            <span class="close" onclick="hideModal('deliveryModal')">&times;</span>
            <h3>🚚 Add New Delivery</h3>
            <form method="POST" action="/deliveries/create">
                <div class="form-row">
                    <div class="form-group">
                        <label>Vehicle Number</label>
                        <input type="text" name="vehicle_number" class="form-control" placeholder="e.g., ABC-123" required>
                    </div>
                    <div class="form-group">
                        <label>Driver Name</label>
                        <input type="text" name="driver_name" class="form-control" placeholder="Enter driver name" required>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Delivery Date</label>
                        <input type="date" name="delivery_date" class="form-control" value="{{ today }}" required>
                    </div>
                    <div class="form-group">
                        <label>Delivery Time</label>
                        <input type="time" name="delivery_time" class="form-control" required>
                    </div>
                </div>
                <div class="form-group">
                    <label>Destination</label>
                    <input type="text" name="destination" class="form-control" placeholder="Enter delivery destination" required>
                </div>
                <div class="form-group">
                    <label>Load Details</label>
                    <textarea name="load_details" class="form-control" rows="3" placeholder="Describe the load details..."></textarea>
                </div>
                <div class="form-group">
                    <label>Status</label>
                    <select name="status" class="form-control">
                        <option value="pending">Pending</option>
                        <option value="in-transit">In Transit</option>
                        <option value="delivered">Delivered</option>
                    </select>
                </div>
                <button type="submit" class="btn btn-primary">Add Delivery</button>
            </form>
        </div>
    </div>
    """)
    
    # Calculate stats
    total = len(deliveries_data)
    pending = len([d for d in deliveries_data if d[7] == 'pending'])
    in_transit = len([d for d in deliveries_data if d[7] == 'in-transit'])
    delivered = len([d for d in deliveries_data if d[7] == 'delivered'])
    
    stats = {
        'total': total,
        'pending': pending,
        'in_transit': in_transit,
        'delivered': delivered
    }
    
    return render_template_string(DELIVERIES_TEMPLATE, 
                                active_page='deliveries', 
                                deliveries=deliveries_data,
                                stats=stats,
                                today=date.today().isoformat())

@app.route('/deliveries/create', methods=['POST'])
def create_delivery():
    vehicle_number = request.form.get('vehicle_number')
    driver_name = request.form.get('driver_name')
    delivery_date = request.form.get('delivery_date')
    delivery_time = request.form.get('delivery_time')
    destination = request.form.get('destination')
    load_details = request.form.get('load_details')
    status = request.form.get('status')
    
    db.execute_query('''
        INSERT INTO deliveries (vehicle_number, driver_name, delivery_date, delivery_time, destination, load_details, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (vehicle_number, driver_name, delivery_date, delivery_time, destination, load_details, status))
    
    return redirect(url_for('deliveries'))

@app.route('/deliveries/update_status/<int:delivery_id>', methods=['POST'])
def update_delivery_status(delivery_id):
    status = request.form.get('status')
    db.execute_query('UPDATE deliveries SET status = ? WHERE id = ?', (status, delivery_id))
    return redirect(url_for('deliveries'))

@app.route('/deliveries/delete/<int:delivery_id>', methods=['POST'])
def delete_delivery(delivery_id):
    db.execute_query('DELETE FROM deliveries WHERE id = ?', (delivery_id,))
    return redirect(url_for('deliveries'))

@app.route('/downloads')
def downloads():
    DOWNLOADS_TEMPLATE = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', """
    <div class="header">
        <h1>📥 Download Center</h1>
        <p>Export and download reports from all modules</p>
    </div>

    <div class="card">
        <h3>📅 Select Date Range</h3>
        <form method="GET" action="/downloads">
            <div class="form-row">
                <div class="form-group">
                    <label>Start Date</label>
                    <input type="date" name="start_date" class="form-control" value="{{ start_date }}">
                </div>
                <div class="form-group">
                    <label>End Date</label>
                    <input type="date" name="end_date" class="form-control" value="{{ end_date }}">
                </div>
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button type="submit" class="btn btn-primary">Update Range</button>
                </div>
            </div>
        </form>
    </div>

    <div class="form-row">
        <div class="card">
            <h3>🕒 Attendance Reports</h3>
            <p>Download daily or monthly attendance records</p>
            <div style="margin-top: 20px;">
                <a href="/downloads/attendance?type=daily&date={{ end_date }}" class="btn btn-primary" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">📊 Daily Report</a>
                <a href="/downloads/attendance?type=monthly&start={{ start_date }}&end={{ end_date }}" class="btn btn-success" style="display: block; text-decoration: none; text-align: center;">📈 Monthly Report</a>
            </div>
        </div>
        
        <div class="card">
            <h3>📄 Invoice Reports</h3>
            <p>Download invoice data by client or date range</p>
            <div style="margin-top: 20px;">
                <a href="/downloads/invoices?start={{ start_date }}&end={{ end_date }}" class="btn btn-primary" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">📋 All Invoices</a>
                <a href="/downloads/invoices?start={{ start_date }}&end={{ end_date }}&client=1" class="btn btn-success" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">🏢 A.L.U International</a>
                <a href="/downloads/invoices?start={{ start_date }}&end={{ end_date }}&client=2" class="btn" style="background: #f59e0b; color: white; display: block; text-decoration: none; text-align: center;">🧱 Niazi Bricks</a>
            </div>
        </div>
        
        <div class="card">
            <h3>🚚 Delivery Reports</h3>
            <p>Download vehicle delivery ledgers</p>
            <div style="margin-top: 20px;">
                <a href="/downloads/deliveries?type=daily&date={{ end_date }}" class="btn btn-primary" style="display: block; margin-bottom: 10px; text-decoration: none; text-align: center;">📊 Daily Report</a>
                <a href="/downloads/deliveries?type=monthly&start={{ start_date }}&end={{ end_date }}" class="btn btn-success" style="display: block; text-decoration: none; text-align: center;">📈 Monthly Report</a>
            </div>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number" style="color: #3b82f6;">{{ stats.attendance_records }}</div>
            <div class="stat-label">🕒 Attendance Records</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #10b981;">{{ stats.total_invoices }}</div>
            <div class="stat-label">📄 Total Invoices</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #f59e0b;">{{ stats.total_deliveries }}</div>
            <div class="stat-label">🚚 Total Deliveries</div>
        </div>
        <div class="stat-card">
            <div class="stat-number" style="color: #8b5cf6;">Rs{{ stats.total_invoice_value }}</div>
            <div class="stat-label">💰 Total Invoice Value</div>
        </div>
    </div>

    <div class="card" style="background: #eff6ff;">
        <h3 style="color: #1e40af;">📋 Export Instructions</h3>
        <ul style="color: #1e40af; margin-top: 15px;">
            <li><strong>CSV files</strong> can be opened in Excel, Google Sheets, or any spreadsheet application</li>
            <li><strong>Daily reports</strong> show data for the selected end date</li>
            <li><strong>Monthly reports</strong> include all data within the selected date range</li>
            <li><strong>Client-specific reports</strong> filter invoices by the selected client</li>
        </ul>
    </div>
    """)
    
    # Get date range from query params
    start_date = request.args.get('start_date', (date.today().replace(day=1)).isoformat())
    end_date = request.args.get('end_date', date.today().isoformat())
    
    # Calculate stats
    attendance_records = db.execute_query('SELECT COUNT(*) FROM attendance', fetch=True)[0][0]
    total_invoices = db.execute_query('SELECT COUNT(*) FROM invoices', fetch=True)[0][0]
    total_deliveries = db.execute_query('SELECT COUNT(*) FROM deliveries', fetch=True)[0][0]
    total_invoice_value = db.execute_query('SELECT COALESCE(SUM(total), 0) FROM invoices', fetch=True)[0][0]
    
    stats = {
        'attendance_records': attendance_records,
        'total_invoices': total_invoices,
        'total_deliveries': total_deliveries,
        'total_invoice_value': f"{total_invoice_value:,.0f}"
    }
    
    return render_template_string(DOWNLOADS_TEMPLATE, 
                                active_page='downloads',
                                start_date=start_date,
                                end_date=end_date,
                                stats=stats)

@app.route('/downloads/attendance')
def download_attendance():
    report_type = request.args.get('type', 'daily')
    
    if report_type == 'daily':
        report_date = request.args.get('date', date.today().isoformat())
        records = db.execute_query('SELECT * FROM attendance WHERE date = ?', (report_date,), fetch=True)
        filename = f'attendance_daily_{report_date}.csv'
    else:
        start_date = request.args.get('start', (date.today().replace(day=1)).isoformat())
        end_date = request.args.get('end', date.today().isoformat())
        records = db.execute_query('SELECT * FROM attendance WHERE date BETWEEN ? AND ?', (start_date, end_date), fetch=True)
        filename = f'attendance_monthly_{start_date}_to_{end_date}.csv'
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Employee Name', 'Date', 'Check In', 'Check Out', 'Location', 'Total Hours'])
    
    for record in records:
        writer.writerow([
            record[2],  # employee_name
            record[6],  # date
            record[3],  # check_in
            record[4] or 'Not checked out',  # check_out
            record[5],  # work_location
            record[7] or '0'  # total_hours
        ])
    
    # Create response
    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/downloads/invoices')
def download_invoices():
    start_date = request.args.get('start', (date.today().replace(day=1)).isoformat())
    end_date = request.args.get('end', date.today().isoformat())
    client_id = request.args.get('client')
    
    query = 'SELECT * FROM invoices WHERE date BETWEEN ? AND ?'
    params = [start_date, end_date]
    
    if client_id:
        query += ' AND client_id = ?'
        params.append(client_id)
        client_name = db.execute_query('SELECT name FROM clients WHERE id = ?', (client_id,), fetch=True)[0][0]
        filename = f'invoices_{client_name.replace(" ", "_")}_{start_date}_to_{end_date}.csv'
    else:
        filename = f'invoices_all_{start_date}_to_{end_date}.csv'
    
    records = db.execute_query(query, params, fetch=True)
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Invoice Number', 'Client', 'Date', 'Subtotal', 'Tax', 'Discount', 'Total', 'Status'])
    
    for record in records:
        writer.writerow([
            record[1],  # invoice_number
            record[3],  # client_name
            record[4],  # date
            f"{record[6]:.2f}",  # subtotal
            f"{record[7]:.2f}",  # tax
            f"{record[8]:.2f}",  # discount
            f"{record[9]:.2f}",  # total
            record[10]  # status
        ])
    
    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/downloads/deliveries')
def download_deliveries():
    report_type = request.args.get('type', 'daily')
    
    if report_type == 'daily':
        report_date = request.args.get('date', date.today().isoformat())
        records = db.execute_query('SELECT * FROM deliveries WHERE delivery_date = ?', (report_date,), fetch=True)
        filename = f'deliveries_daily_{report_date}.csv'
    else:
        start_date = request.args.get('start', (date.today().replace(day=1)).isoformat())
        end_date = request.args.get('end', date.today().isoformat())
        records = db.execute_query('SELECT * FROM deliveries WHERE delivery_date BETWEEN ? AND ?', (start_date, end_date), fetch=True)
        filename = f'deliveries_monthly_{start_date}_to_{end_date}.csv'
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Vehicle Number', 'Driver Name', 'Date', 'Time', 'Destination', 'Load Details', 'Status'])
    
    for record in records:
        writer.writerow([
            record[1],  # vehicle_number
            record[2],  # driver_name
            record[3],  # delivery_date
            record[4],  # delivery_time
            record[5],  # destination
            record[6] or '',  # load_details
            record[7]  # status
        ])
    
    output.seek(0)
    return app.response_class(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

if __name__ == '__main__':
    print("🚀 Starting A.T Commodities ERP System...")
    print("🌐 Visit http://localhost:5000 to access the system")
    print("📊 Features: Dashboard, Attendance, Invoices, Deliveries, Downloads")
    print("💾 Database: SQLite (at_commodities.db)")
    app.run(debug=True, host='0.0.0.0', port=5000)