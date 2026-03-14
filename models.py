from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ==============================
# PRINT JOB MODEL
# ==============================
class PrintJob(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    job_id = db.Column(db.String(100), unique=True, nullable=False)

    filename = db.Column(db.String(200), nullable=False)

    copies = db.Column(db.Integer, default=1)

    color_mode = db.Column(db.String(50), default="Black & White")

    paper_size = db.Column(db.String(50), default="A4")

    # Pricing Column
    price = db.Column(db.Float, default=0.0)

    # Payment Status
    is_paid = db.Column(db.Boolean, default=False)

    # Job Status
    status = db.Column(db.String(50), default="Pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Constructor
    def __init__(self, filename, copies, color_mode, paper_size, price=0.0):
        self.job_id = str(uuid.uuid4())
        self.filename = filename
        self.copies = copies
        self.color_mode = color_mode
        self.paper_size = paper_size
        self.price = price


# ==============================
# ADMIN MODEL (SECURE LOGIN)
# ==============================
class Admin(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True, nullable=False)

    password_hash = db.Column(db.String(200), nullable=False)

    # Set password securely
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Check password securely
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)