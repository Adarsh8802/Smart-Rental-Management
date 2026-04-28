import os
import io
import random
import requests
from datetime import date, datetime, timedelta
from threading import Thread
from werkzeug.utils import secure_filename
from flask import Flask, render_template, redirect, url_for, flash, request, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_apscheduler import APScheduler
from flask_mail import Mail, Message

# ✅ OLD PDF LIBRARY (Ye best aur stable hai)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = 'mundrawati_secret_key_secure_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Mundrawati.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- 📧 EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'adarsh029948@gmail.com' 
app.config['MAIL_PASSWORD'] = 'azfh nqqy yrho zasa'  # App Password
app.config['MAIL_DEFAULT_SENDER'] = ('Mundrawati Niketan', 'adarsh029948@gmail.com')

mail = Mail(app)

# File Upload Config
app.config['UPLOAD_FOLDER'] = 'static/uploads' 
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)
scheduler = APScheduler()

# --- MODELS ---

class Owner(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Renter(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    room_no = db.Column(db.String(20), nullable=False)
    monthly_rent = db.Column(db.Integer, nullable=False)
    security_deposit = db.Column(db.Integer)
    rent_due_day = db.Column(db.Integer, nullable=False)
    joining_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)
    vacate_date = db.Column(db.Date, nullable=True)
    photo = db.Column(db.String(150), nullable=False, default='default.png')
    id_proof = db.Column(db.String(150), nullable=True) 
    current_balance = db.Column(db.Integer, default=0)
    payments = db.relationship('Payment', backref='renter', lazy=True)
    complaints = db.relationship('Complaint', backref='renter', lazy=True)
    def get_id(self): return str(self.id)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    month_year = db.Column(db.String(20), nullable=False)
    mode = db.Column(db.String(20), default='Cash')
    transaction_id = db.Column(db.String(50), nullable=True)
    screenshot = db.Column(db.String(150), nullable=True)
    status = db.Column(db.String(20), default='Approved')
    prev_reading = db.Column(db.Integer, default=0)
    curr_reading = db.Column(db.Integer, default=0)
    elec_rate = db.Column(db.Integer, default=0) 
    elec_amount = db.Column(db.Integer, default=0) 

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_active = db.Column(db.Boolean, default=True)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Open')
    created_at = db.Column(db.DateTime, default=datetime.now)

class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_name = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(100))

# --- LOGIN MANAGER ---
login_manager = LoginManager(app)
login_manager.login_view = 'main_login'

@login_manager.user_loader
def load_user(user_id):
    if 'user_type' in session and session['user_type'] == 'renter':
        return db.session.get(Renter, int(user_id))
    return db.session.get(Owner, int(user_id))

# --- HELPER FUNCTIONS ---
def get_current_month_year():
    return date.today().strftime("%Y-%m")

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
            print("✅ Email Sent Successfully!")
        except Exception as e:
            print(f"❌ Email Failed: {e}")

# --- 👇 PDF GENERATION FUNCTIONS (REPORTLAB) 👇 ---

def create_receipt_pdf(payment, renter):
    """Generates the EXACT original receipt PDF with Electricity Breakdown"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- HEADER ---
    c.setFillColorRGB(0.1, 0.2, 0.5) 
    c.rect(0, height - 120, width, 120, fill=1, stroke=0) 
    
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 100, width=80, height=80, mask='auto')

    c.setFillColorRGB(1, 1, 1) 
    c.setFont("Helvetica-Bold", 26)
    c.drawString(140, height - 60, "MUNDRAWATI NIKETAN")
    c.setFont("Helvetica", 12)
    c.drawString(140, height - 80, "Smart Renter Management System")
    c.drawString(140, height - 95, "Sahjanand Colony 07, Muzaffarpur, Bihar | +91 6207418250")

    # --- RECEIPT INFO ---
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(width - 50, height - 160, "PAYMENT RECEIPT")
    c.setFont("Helvetica", 12)
    c.setFillColorRGB(0.4, 0.4, 0.4) 
    c.drawRightString(width - 50, height - 180, f"Receipt #: {payment.id:04d}")
    c.drawRightString(width - 50, height - 200, f"Date: {payment.payment_date.strftime('%d %B, %Y')}")

    # --- TENANT INFO BOX ---
    y_pos = height - 240
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(1)
    c.roundRect(40, y_pos - 60, width - 80, 70, 10, stroke=1, fill=0)
    
    c.setFillColorRGB(0.1, 0.2, 0.5)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(55, y_pos - 15, "BILLED TO:")
    c.setFillColorRGB(0, 0, 0) 
    c.setFont("Helvetica-Bold", 14)
    c.drawString(55, y_pos - 35, f"{renter.name}")
    c.setFont("Helvetica", 12)
    c.drawString(55, y_pos - 52, f"Room No: {renter.room_no} | Mobile: {renter.mobile}")

    # --- TABLE HEADER ---
    y_pos -= 110
    c.setFillColorRGB(0.9, 0.9, 0.9) 
    c.rect(40, y_pos, width - 80, 30, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, y_pos + 10, "DESCRIPTION")
    c.drawString(300, y_pos + 10, "DETAILS / MODE")
    c.drawRightString(width - 60, y_pos + 10, "AMOUNT")
    
    # --- TABLE ROWS (MAIN LOGIC) ---
    y_pos -= 40
    c.setFont("Helvetica", 12)
    
    # Values check karein
    e_amt = payment.elec_amount if payment.elec_amount else 0
    rent_amt = payment.amount - e_amt  # Total me se Electricity ghata kar Rent nikalo

    # 1. Rent Line
    c.drawString(60, y_pos, f"Room Rent ({payment.month_year})")
    mode_text = f"Online ({payment.transaction_id})" if payment.mode == 'Online' else "Cash"
    c.drawString(300, y_pos, mode_text)
    c.drawRightString(width - 60, y_pos, f"Rs. {rent_amt}/-")
    
    # 2. Electricity Line (Sirf tab dikhega jab amount > 0 ho)
    if e_amt > 0:
        y_pos -= 30  # Thoda niche aao
        
        # Readings nikalo
        curr = payment.curr_reading if payment.curr_reading else 0
        prev = payment.prev_reading if payment.prev_reading else 0
        rate = payment.elec_rate if payment.elec_rate else 0
        units = curr - prev

        c.drawString(60, y_pos, "Electricity Bill")
        c.setFont("Helvetica", 10)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(300, y_pos, f"Reading: {prev} -> {curr} ({units} Units @ {rate}/u)")
        
        c.setFont("Helvetica", 12)
        c.setFillColorRGB(0, 0, 0)
        c.drawRightString(width - 60, y_pos, f"Rs. {e_amt}/-")

    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(40, y_pos - 15, width - 40, y_pos - 15)

    # --- TOTAL & SIGNATURE ---
    y_pos -= 60
    c.setFont("Helvetica-Bold", 16)
    c.setFillColorRGB(0.1, 0.2, 0.5) 
    c.drawRightString(width - 60, y_pos, f"TOTAL PAID: Rs. {payment.amount}/-")

    y_pos -= 100
    sig_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
    if os.path.exists(sig_path):
        c.drawImage(sig_path, width - 200, y_pos + 25, width=120, height=50, mask='auto')
    
    c.setStrokeColorRGB(0, 0, 0)
    c.line(width - 220, y_pos + 20, width - 60, y_pos + 20)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColorRGB(0, 0, 0)
    c.drawCentredString(width - 140, y_pos + 5, "Authorized Signature")
    
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def create_agreement_pdf(renter):
    """Generates Agreement PDF with Owner's Signature"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- HEADER ---
    c.setFillColorRGB(0.1, 0.2, 0.5) 
    c.rect(0, height - 120, width, 120, fill=1, stroke=0) 
    
    logo_path = os.path.join(app.root_path, 'static', 'images', 'logo.png')
    if os.path.exists(logo_path):
        c.drawImage(logo_path, 40, height - 100, width=80, height=80, mask='auto')

    c.setFillColorRGB(1, 1, 1) 
    c.setFont("Helvetica-Bold", 26)
    c.drawString(140, height - 60, "MUNDRAWATI NIKETAN")
    c.setFont("Helvetica", 12)
    c.drawString(140, height - 80, "RENTAL AGREEMENT / WELCOME LETTER")
    c.drawString(140, height - 95, "Sahjanand Colony 07, Muzaffarpur, Bihar")

    # --- BODY ---
    c.setFillColorRGB(0, 0, 0)
    y_pos = height - 160
    
    c.setFont("Helvetica", 12)
    c.drawString(40, y_pos, f"This agreement is made on {date.today().strftime('%d %B, %Y')} between:")
    y_pos -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y_pos, "Owner: Mundrawati Niketan")
    c.drawString(300, y_pos, f"Renter: {renter.name}")
    
    # Details Box
    y_pos -= 40
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.setLineWidth(1)
    c.roundRect(40, y_pos - 120, width - 80, 130, 10, stroke=1, fill=0)
    
    text_y = y_pos - 25
    c.setFont("Helvetica", 12)
    c.drawString(55, text_y, "Registered Mobile:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, text_y, f"{renter.mobile}")
    
    text_y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(55, text_y, "Allocated Room:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, text_y, f"Room No. {renter.room_no}")

    text_y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(55, text_y, "Monthly Rent:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, text_y, f"Rs. {renter.monthly_rent} /-")

    text_y -= 25
    c.setFont("Helvetica", 12)
    c.drawString(55, text_y, "Security Deposit:")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(200, text_y, f"Rs. {renter.security_deposit} /-")

    # Rules Section
    y_pos -= 160
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y_pos, "TERMS AND CONDITIONS:")
    
    y_pos -= 30
    c.setFont("Helvetica", 12)
    rules = [
        f"1. Rent must be paid by the {renter.rent_due_day}th of every month.",
        "2. Electricity bill is extra (based on sub-meter reading).",
        "3. One month notice is mandatory before vacating the room.",
        "4. Security deposit is refundable after clearing all dues.",
        "5. Main gate locks at 11:00 PM.",
        "6. No loud music or disturbance to other renters allowed."
    ]
    
    for rule in rules:
        c.drawString(40, y_pos, rule)
        y_pos -= 20

    # Login Details
    y_pos -= 40
    c.setFillColorRGB(0.1, 0.2, 0.5)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y_pos, "YOUR LOGIN DETAILS:")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 12)
    c.drawString(40, y_pos - 20, f"Portal: http://127.0.0.1:5000/login")
    c.drawString(40, y_pos - 40, f"Username/Email: {renter.email}")

    # --- SIGNATURE SECTION (Updated) ---
    y_pos -= 100
    
    # 👇 ओनर के सिग्नेचर की इमेज डालें (लाइन के ऊपर)
    sig_path = os.path.join(app.root_path, 'static', 'images', 'signature.png')
    if os.path.exists(sig_path):
        # x=60, y=y_pos+5 (ताकि लाइन के ठीक ऊपर दिखे)
        c.drawImage(sig_path, 60, y_pos + 5, width=100, height=40, mask='auto')

    c.setStrokeColorRGB(0, 0, 0)
    c.line(40, y_pos, 200, y_pos) # Owner line
    c.line(width - 200, y_pos, width - 40, y_pos) # Tenant line
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, y_pos - 20, "Authorized Signature") # (Owner)
    c.drawRightString(width - 60, y_pos - 20, "Renter Signature")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

def send_email_otp(to_email, otp):
    try:
        msg = Message('Your Login OTP - Mundrawati Niketan', recipients=[to_email])
        msg.body = f"Hello,\n\nYour OTP for login is: {otp}\n\nRegards,\nMundrawati Niketan"
        Thread(target=send_async_email, args=(app, msg)).start()
        return True
    except Exception as e:
        print(f"Email Sending Error: {e}")
        return False

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('home.html', date=date)

@app.route('/login')
def main_login():
    if session.get('user_type') == 'owner': return redirect(url_for('owner_dashboard'))
    elif session.get('user_type') == 'renter': return redirect(url_for('renter_dashboard'))
    return render_template('login.html')

# OWNER LOGIN
@app.route('/owner/login', methods=['GET', 'POST'])
def owner_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = Owner.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_type'] = 'owner'
            login_user(user)
            return redirect(url_for('owner_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return redirect(url_for('main_login'))
    return render_template('login.html')

@app.route('/owner/logout')
@login_required
def owner_logout():
    logout_user()
    session.pop('user_type', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('main_login'))

@app.route('/owner/dashboard')
@login_required
def owner_dashboard():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    
    active_renters = Renter.query.filter_by(is_active=True).all()
    total_occupied = len(active_renters)
    TOTAL_ROOMS = 7 
    current_month = get_current_month_year()
    payments = Payment.query.filter_by(month_year=current_month, status='Approved').all()
    
    collected = sum(p.amount for p in payments)
    total_elec = sum(p.elec_amount for p in payments)
    total_rent = collected - total_elec
    
    potential = sum(r.monthly_rent for r in active_renters)
    pending = potential - total_rent
    if pending < 0: pending = 0
    
    recent_payments = Payment.query.filter_by(status='Approved').order_by(Payment.payment_date.desc()).limit(5).all()
    pending_complaints = Complaint.query.filter_by(status='Open').count()
    active_notices = Notice.query.filter_by(is_active=True).order_by(Notice.created_at.desc()).all()

    return render_template('owner/dashboard.html', active_page='dashboard', collected=collected, total_rent=total_rent, total_elec=total_elec, pending=pending, occupied=total_occupied, vacant=TOTAL_ROOMS - total_occupied, recent_payments=recent_payments, pending_issues=pending_complaints, notices=active_notices, date=date)

@app.route('/owner/add-renter', methods=['GET', 'POST'])
@login_required
def add_renter():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    
    if request.method == 'POST':
        try:
            mobile = request.form.get('mobile')
            email = request.form.get('email')
            
            # Check for duplicates
            if Renter.query.filter_by(mobile=mobile).first():
                flash('Mobile number already registered!', 'danger')
                return redirect(url_for('add_renter'))
                
            if Renter.query.filter_by(email=email).first():
                flash('Email ID already registered!', 'danger')
                return redirect(url_for('add_renter'))

            j_date = datetime.strptime(request.form.get('joining_date'), '%Y-%m-%d').date()

            # 👇 1. PHOTO UPLOAD LOGIC (New)
            photo_filename = 'default.png' # Default fallback
            if 'renter_photo' in request.files:
                file = request.files['renter_photo']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    # Unique name: dp_timestamp_filename
                    unique_name = f"dp_{datetime.now().timestamp()}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                    photo_filename = unique_name

            # 👇 2. ID PROOF UPLOAD LOGIC (Existing)
            id_filename = None
            if 'id_proof' in request.files:
                file = request.files['id_proof']
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    unique_name = f"id_{datetime.now().timestamp()}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                    id_filename = unique_name

            # 👇 3. SAVE TO DATABASE
            new_renter = Renter(
                name=request.form.get('name'),
                mobile=mobile,
                email=email,
                room_no=request.form.get('room_no'),
                monthly_rent=int(request.form.get('monthly_rent')),
                security_deposit=int(request.form.get('security_deposit') or 0),
                rent_due_day=int(request.form.get('rent_due_day')),
                joining_date=j_date,
                id_proof=id_filename,
                photo=photo_filename  # ✅ Photo saved here
            )
            db.session.add(new_renter)
            db.session.commit()

            # 👇 4. SEND AGREEMENT EMAIL
            try:
                pdf_buffer = create_agreement_pdf(new_renter)
                msg = Message("Welcome to Mundrawati Niketan - Agreement", recipients=[new_renter.email])
                msg.body = f"Dear {new_renter.name},\n\nWelcome! Please find your Rent Agreement attached.\n\nRegards,\nMundrawati Niketan"
                msg.attach(f"Agreement_{new_renter.name}.pdf", "application/pdf", pdf_buffer.getvalue())
                Thread(target=send_async_email, args=(app, msg)).start()
                flash('Renter added & Agreement sent!', 'success')
            except Exception as e:
                print(f"Email Error: {e}")
                flash('Renter added but Email failed.', 'warning')

            return redirect(url_for('add_renter'))
            
        except Exception as e:
             flash(f'Error: {str(e)}', 'danger')
    
    return render_template('owner/add_renter.html', active_page='add_renter', date=date)


@app.route('/owner/payment-entry', methods=['GET', 'POST'])
@login_required
def payment_entry():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    
    if request.method == 'POST':
        try:
            # 1. Form Data Retrieve
            renter_id = request.form.get('renter_id')
            p_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            month_year_val = request.form.get('month_year')
            
            # 2. Electricity Calculation
            prev = int(request.form.get('prev_reading') or 0)
            curr = int(request.form.get('curr_reading') or 0)
            rate = int(request.form.get('elec_rate') or 0)
            units = max(0, curr - prev)
            elec_cost = units * rate
            
            # 3. Amount Logic (Total Paid vs Actual Bill)
            total_paid = int(request.form.get('amount')) # Jo Owner ne Cash receive kiya
            
            renter = Renter.query.get(renter_id)
            
            # Actual Bill for this month = Rent + Elec
            actual_bill = renter.monthly_rent + elec_cost
            
            # 👇 MAIN LOGIC: UPDATE RENTER BALANCE
            # Formula: Old Balance + (Abhi ka Bill) - (Jo Pay Kiya)
            renter.current_balance = (renter.current_balance + actual_bill) - total_paid
            
            # 4. Save Payment Record
            new_pay = Payment(
                renter_id=renter_id, 
                amount=total_paid, # Receipt me wahi amount jayega jo pay kiya
                payment_date=p_date,
                month_year=month_year_val, 
                mode='Cash', 
                status='Approved',
                prev_reading=prev, 
                curr_reading=curr, 
                elec_rate=rate, 
                elec_amount=elec_cost
            )
            db.session.add(new_pay)
            db.session.commit()

            # 5. Send Receipt Email
            try:
                pdf_buffer = create_receipt_pdf(new_pay, renter)
                msg = Message(f"Payment Receipt - {month_year_val}", recipients=[renter.email])
                msg.body = f"Dear {renter.name},\n\nPayment received: Rs. {total_paid}.\nYour Current Balance is: Rs. {renter.current_balance} (Positive=Due, Negative=Advance).\n\nRegards,\nMundrawati Niketan"
                msg.attach(f"Receipt_{new_pay.id}.pdf", "application/pdf", pdf_buffer.getvalue())
                Thread(target=send_async_email, args=(app, msg)).start()
                
                # Flash Message with Balance Info
                flash(f'Payment Recorded! Renter New Balance: ₹{renter.current_balance}', 'success')
            except Exception as e:
                print(e)
                flash('Payment recorded but Email failed.', 'warning')

            return redirect(url_for('payment_entry'))
            
        except Exception as e:
            flash(f"Error: {str(e)}", 'danger')

    active_renters = Renter.query.filter_by(is_active=True).all()
    return render_template('owner/payment_entry.html', active_page='payment_entry', renters=active_renters, date=date)

@app.route('/owner/download-receipt/<int:payment_id>')
@login_required
def download_receipt(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment: return redirect(url_for('owner_dashboard'))
    renter = payment.renter
    # Use Helper Function
    pdf_buffer = create_receipt_pdf(payment, renter)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"Receipt_{payment.id}.pdf", mimetype='application/pdf')

@app.route('/owner/approve/<int:id>')
@login_required
def approve_payment(id):
    if session.get('user_type') != 'owner': return redirect(url_for('main_login'))
    payment = Payment.query.get_or_404(id)
    payment.status = 'Approved'
    db.session.commit()

    # --- SEND RECEIPT EMAIL ---
    try:
        renter = Renter.query.get(payment.renter_id)
        pdf_buffer = create_receipt_pdf(payment, renter)
        msg = Message(f"Payment Approved - {payment.month_year}", recipients=[renter.email])
        msg.body = f"Dear {renter.name},\n\nYour online payment is approved. Receipt attached.\n\nRegards,\nMundrawati Niketan"
        msg.attach(f"Receipt_{payment.id}.pdf", "application/pdf", pdf_buffer.getvalue())
        Thread(target=send_async_email, args=(app, msg)).start()
        flash('Approved & Receipt Sent!', 'success')
    except: flash('Approved but Email failed.', 'warning')
    return redirect(url_for('owner_online_requests'))

# --- OTHER ROUTES (View Renters, History, Complaints, etc.) ---
# (Keeping minimal for brevity, add back existing routes for view-renters, etc.)

@app.route('/owner/view-renters')
@login_required
def view_renters():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    
    renters = Renter.query.filter_by(is_active=True).all()
    data = []
    curr_m = get_current_month_year()
    
    for r in renters:
        is_paid = Payment.query.filter_by(renter_id=r.id, month_year=curr_m, status='Approved').first()
        status = 'Paid' if is_paid else 'Pending'
        due = f"{date.today().year}-{date.today().month:02d}-{r.rent_due_day:02d}"
        
        # 👇 Dictionary me Photo aur ID Proof add kiya
        data.append({
            'id': r.id, 
            'name': r.name, 
            'room_no': r.room_no, 
            'rent': r.monthly_rent, 
            'due_date': due, 
            'status': status, 
            'email': r.email, 
            'mobile': r.mobile,
            'photo': r.photo,        # ✅ Ye line jaruri hai DP ke liye
            'id_proof': r.id_proof,  # ✅ Ye line jaruri hai Documents ke liye
            'current_balance': r.current_balance
        })
        
    return render_template('owner/view_renters.html', active_page='view_renters', renters=data)

@app.route('/owner/vacate/<int:renter_id>')
@login_required
def vacate_renter(renter_id):
    r = db.session.get(Renter, renter_id)
    if r:
        r.is_active = False; r.vacate_date = date.today(); db.session.commit(); flash('Renter vacated.', 'success')
    return redirect(url_for('view_renters'))

@app.route('/owner/history')
@login_required
def history():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    past = Renter.query.filter_by(is_active=False).all()
    data = []
    for r in past:
        paid = db.session.query(db.func.sum(Payment.amount)).filter_by(renter_id=r.id, status='Approved').scalar() or 0
        months = 0
        if r.vacate_date and r.joining_date:
            months = (r.vacate_date.year - r.joining_date.year) * 12 + r.vacate_date.month - r.joining_date.month
        data.append({'name':r.name, 'room_no':r.room_no, 'joining':r.joining_date, 'vacate':r.vacate_date, 'months':months, 'total_paid':paid})
    return render_template('owner/history.html', active_page='history', history=data)

@app.route('/owner/online-requests')
@login_required
def owner_online_requests():
    if session.get('user_type') != 'owner': return redirect(url_for('main_login'))
    pending_payments = Payment.query.filter_by(status='Pending').all()
    return render_template('owner/online_requests.html', payments=pending_payments)

@app.route('/owner/transactions')
@login_required
def transaction_history():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    selected_month = request.args.get('month', get_current_month_year())
    selected_renter_id = request.args.get('renter_id', 'all')
    query = Payment.query.filter_by(status='Approved')
    if selected_month: query = query.filter_by(month_year=selected_month)
    if selected_renter_id != 'all': query = query.filter_by(renter_id=selected_renter_id)
    transactions = query.order_by(Payment.payment_date.desc()).all()
    total_amount = sum(t.amount for t in transactions)
    return render_template('owner/transactions.html', active_page='transactions', transactions=transactions, renters=Renter.query.all(), selected_month=selected_month, selected_renter_id=selected_renter_id, total_amount=total_amount)

@app.route('/owner/complaints')
@login_required
def owner_complaints():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    return render_template('owner/complaints.html', active_page='complaints', complaints=Complaint.query.order_by(Complaint.created_at.desc()).all())

@app.route('/owner/resolve-complaint/<int:id>')
@login_required
def resolve_complaint(id):
    c = db.session.get(Complaint, id); 
    if c: c.status = 'Resolved'; db.session.commit()
    return redirect(url_for('owner_complaints'))

@app.route('/owner/reminders', methods=['GET', 'POST'])
@login_required
def reminder_status():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    setting = SystemSetting.query.filter_by(key_name='reminder_active').first()
    if not setting: setting = SystemSetting(key_name='reminder_active', value='False'); db.session.add(setting); db.session.commit()
    if request.method == 'POST':
        setting.value = 'True' if request.form.get('action') == 'enable' else 'False'; db.session.commit()
        flash(f'Reminders: {setting.value}', 'success'); return redirect(url_for('reminder_status'))
    return render_template('owner/reminder_status.html', active_page='reminder_status', is_active=(setting.value=='True'), last_sent="N/A", upcoming="Tomorrow 10 AM")

@app.route('/owner/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if session.get('user_type') != 'owner': return redirect(url_for('owner_login'))
    if request.method == 'POST':
        if current_user.password != request.form.get('current_password'): flash('Incorrect current password!', 'danger')
        elif request.form.get('new_password') != request.form.get('confirm_password'): flash('Passwords do not match!', 'danger')
        else: current_user.password = request.form.get('new_password'); db.session.commit(); flash('Password updated!', 'success'); return redirect(url_for('owner_dashboard'))
    return render_template('owner/change_password.html', active_page='change_password')

@app.route('/owner/add-notice', methods=['POST'])
@login_required
def add_notice():
    msg = request.form.get('message')
    if msg: db.session.add(Notice(message=msg)); db.session.commit(); flash('Notice added!', 'success')
    return redirect(url_for('owner_dashboard'))

@app.route('/owner/delete-notice/<int:id>')
@login_required
def delete_notice(id):
    n = Notice.query.get(id); 
    if n: db.session.delete(n); db.session.commit(); flash('Notice deleted.', 'info')
    return redirect(url_for('owner_dashboard'))

# RENTER LOGIN/DASHBOARD
@app.route('/renter/login', methods=['GET', 'POST'])
def renter_login():
    if current_user.is_authenticated and session.get('user_type') == 'renter': return redirect(url_for('renter_dashboard'))
    if request.method == 'POST':
        login_input = request.form.get('login_input')
        renter = Renter.query.filter_by(email=login_input).first() if '@' in login_input else Renter.query.filter_by(mobile=login_input).first()
        if renter:
            otp = str(random.randint(1000, 9999))
            if '@' in login_input: send_email_otp(renter.email, otp)
            return render_template('renter_otp.html', contact=login_input, generated_otp=otp, visible_otp=otp if '@' not in login_input else None)
        else: flash('Renter not found!', 'danger'); return redirect(url_for('main_login'))
    return redirect(url_for('main_login'))

@app.route('/renter/verify-otp', methods=['POST'])
def renter_verify_otp():
    contact = request.form.get('contact')
    if request.form.get('user_otp') == request.form.get('actual_otp'):
        renter = Renter.query.filter_by(email=contact).first() if '@' in contact else Renter.query.filter_by(mobile=contact).first()
        if renter: login_user(renter); session['user_type'] = 'renter'; return redirect(url_for('renter_dashboard'))
    flash('Invalid OTP', 'danger'); return redirect(url_for('main_login'))

@app.route('/renter/logout')
@login_required
def renter_logout():
    logout_user(); session.pop('user_type', None); flash('Logged out.', 'info'); return redirect(url_for('main_login'))

@app.route('/renter/dashboard')
@login_required
def renter_dashboard():
    if session.get('user_type') != 'renter': return redirect(url_for('renter_login'))
    r = current_user; today = date.today(); curr_m = get_current_month_year()
    last = Payment.query.filter_by(renter_id=r.id, status='Approved').order_by(Payment.payment_date.desc()).first()
    paid = Payment.query.filter_by(renter_id=r.id, month_year=curr_m, status='Approved').first() is not None
    status = 'Paid' if paid else 'Pending'; cls = 'status-paid' if paid else 'status-pending'
    due_display = f"{today.strftime('%b')} {r.rent_due_day}, {today.year}"
    alert = (not paid) and (today.day >= r.rent_due_day)
    delta_years = today.year - r.joining_date.year; delta_months = today.month - r.joining_date.month
    if delta_months < 0: delta_years -= 1; delta_months += 12
    dur = f"{delta_years}Y " if delta_years > 0 else ""; dur += f"{delta_months}M"
    if dur == "0M": dur = "Just Joined"
    return render_template('renter/dashboard.html', renter=r, status=status, status_class=cls, last_payment=last, due_date=due_display, show_alert=alert, duration=dur, open_issues=Complaint.query.filter_by(renter_id=r.id, status='Open').count(), notices=Notice.query.filter_by(is_active=True).all(), recent_payments=Payment.query.filter_by(renter_id=r.id).order_by(Payment.payment_date.desc()).limit(3).all(), date=date)

@app.route('/renter/pay-online', methods=['GET', 'POST'])
@login_required
def renter_pay_online():
    if session.get('user_type') != 'renter': return redirect(url_for('main_login'))
    
    OWNER_UPI_ID = "7632956506@ybl"
    OWNER_NAME = "Nisha Kumari"
    
    if request.method == 'POST':
        amount = request.form.get('amount')
        txn_id = request.form.get('txn_id')
        month_year = request.form.get('month_year')
        
        prev = int(request.form.get('prev_reading') or 0)
        curr = int(request.form.get('curr_reading') or 0)
        rate = int(request.form.get('elec_rate') or 0)
        units = max(0, curr - prev)
        elec_amount = units * rate

        # 👇 SCREENSHOT UPLOAD LOGIC START
        screenshot_filename = None
        if 'screenshot' in request.files:
            file = request.files['screenshot']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                # Unique name banayenge taaki overwrite na ho
                unique_name = f"pay_{datetime.now().timestamp()}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_name))
                screenshot_filename = unique_name
        # 👆 SCREENSHOT UPLOAD LOGIC END

        new_payment = Payment(
            renter_id=current_user.id,
            amount=amount,
            month_year=month_year,
            payment_date=date.today(),
            mode='Online',
            transaction_id=txn_id,
            status='Pending',
            prev_reading=prev,
            curr_reading=curr,
            elec_rate=rate,
            elec_amount=elec_amount,
            screenshot=screenshot_filename  # ✅ Database me save kiya
        )
        db.session.add(new_payment)
        db.session.commit()
        flash('Payment & Screenshot submitted! Waiting for approval.', 'info')
        return redirect(url_for('renter_history'))

    # ... (QR Code logic wahi rahega)
    qr_data = f"upi://pay?pa={OWNER_UPI_ID}&pn={OWNER_NAME}&cu=INR"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={qr_data}"
    
    return render_template('renter/pay_online.html', qr_url=qr_url, date=date, renter=current_user)

@app.route('/renter/history')
@login_required
def renter_history():
    if session.get('user_type') != 'renter': return redirect(url_for('main_login'))
    return render_template('renter/history.html', payments=Payment.query.filter_by(renter_id=current_user.id).order_by(Payment.payment_date.desc()).all())

@app.route('/renter/raise-complaint', methods=['GET', 'POST'])
@login_required
def raise_complaint():
    if session.get('user_type') != 'renter': return redirect(url_for('renter_login'))
    if request.method == 'POST':
        db.session.add(Complaint(renter_id=current_user.id, issue_type=request.form.get('issue_type'), message=request.form.get('message')))
        db.session.commit(); flash('Complaint Submitted!', 'success'); return redirect(url_for('raise_complaint'))
    return render_template('renter/raise_complaint.html')

def check_rent_due_daily():
    with app.app_context():
        if not SystemSetting.query.filter_by(key_name='reminder_active', value='True').first(): return
        today = date.today(); cm = today.strftime("%Y-%m")
        for r in Renter.query.filter_by(is_active=True).all():
            if not Payment.query.filter_by(renter_id=r.id, month_year=cm, status='Approved').first():
                try: dd = date(today.year, today.month, r.rent_due_day)
                except: continue
                if today == dd - timedelta(days=3): send_reminder_email(r, "UPCOMING")
                if today == dd: send_reminder_email(r, "DUE_TODAY")
                if today == dd + timedelta(days=5): send_reminder_email(r, "OVERDUE")

def send_reminder_email(renter, type):
    msg = Message(f"Rent Reminder - {type}", recipients=[renter.email])
    msg.body = f"Hello {renter.name},\nThis is a rent reminder from Mundrawati Niketan."
    Thread(target=send_async_email, args=(app, msg)).start()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Owner.query.filter_by(username='guriyamishra').first(): db.session.add(Owner(username='guriyamishra', password='Guriya@1995')); db.session.commit()
        scheduler.add_job(id='DailyReminder', func=check_rent_due_daily, trigger='cron', hour=10, minute=0)
        scheduler.start()
    app.run(debug=True)