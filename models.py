from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

# ओनर टेबल
class Owner(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False) # प्रोडक्शन में हैश होना चाहिए

# रेंटर टेबल
class Renter(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    room_no = db.Column(db.String(20), nullable=False)
    monthly_rent = db.Column(db.Integer, nullable=False)
    security_deposit = db.Column(db.Integer)
    rent_due_day = db.Column(db.Integer, nullable=False) # महीने की तारीख (e.g., 5)
    joining_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True) # True = अभी रह रहा है, False = खाली कर दिया
    vacate_date = db.Column(db.Date, nullable=True)
    
    payments = db.relationship('Payment', backref='renter', lazy=True)
    complaints = db.relationship('Complaint', backref='renter', lazy=True)

    def get_id(self):
        return str(self.id) # Flask-Login के लिए जरूरी

# पेमेंट हिस्ट्री टेबल
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    month_year = db.Column(db.String(20), nullable=False) # e.g., "2026-03"

# शिकायत टेबल
class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    renter_id = db.Column(db.Integer, db.ForeignKey('renter.id'), nullable=False)
    issue_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='Open') # Open, Resolved
    created_at = db.Column(db.DateTime, default=datetime.now)

# सिस्टम सेटिंग्स (जैसे रिमाइंडर स्टेटस)
class SystemSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key_name = db.Column(db.String(50), unique=True)
    value = db.Column(db.String(100))