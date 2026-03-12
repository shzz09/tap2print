from flask import Flask, render_template, request, url_for, redirect, session
from models import db, PrintJob, Admin
from sqlalchemy import func
from werkzeug.utils import secure_filename
import os
import qrcode
import uuid
import razorpay

app = Flask(__name__)

# ==============================
# SECRET KEY
# ==============================
app.secret_key = "tap2print_secret_key"

# ==============================
# RAZORPAY CONFIG
# ==============================
RAZORPAY_KEY_ID = "rzp_live_SPws4T1Osoyopu"
RAZORPAY_KEY_SECRET = "2Hx2q5kuvZPAcYnU80tjmHCC"

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ==============================
# DATABASE CONFIGURATION
# ==============================
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tap2print.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==============================
# FILE SECURITY CONFIG
# ==============================
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE = 5 * 1024 * 1024
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# ==============================
# UPLOAD & STATIC FOLDER CONFIG
# ==============================
UPLOAD_FOLDER = 'uploads'
QR_FOLDER = 'static/qrcodes'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

# ==============================
# INITIALIZE DATABASE
# ==============================
db.init_app(app)

with app.app_context():
    db.create_all()

    if not Admin.query.filter_by(username="admin").first():
        default_admin = Admin(username="admin")
        default_admin.set_password("admin123")
        db.session.add(default_admin)
        db.session.commit()

# ==============================
# HELPER FUNCTION
# ==============================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==============================
# HOME
# ==============================
@app.route('/')
def home():
    return render_template('index.html')

# ==============================
# ADMIN LOGIN
# ==============================
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form.get('username')
        password = request.form.get('password')

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            session['admin'] = admin.username
            return redirect('/dashboard')

        else:
            return render_template('login.html', error="Invalid Credentials")

    return render_template('login.html')

# ==============================
# LOGOUT
# ==============================
@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')

# ==============================
# FILE UPLOAD
# ==============================
@app.route('/upload', methods=['POST'])
def upload_file():

    file = request.files.get('file')
    copies = request.form.get('copies', 1)
    color_mode = request.form.get('color_mode', "Black & White")
    paper_size = request.form.get('paper_size', "A4")

    if not file or file.filename == "":
        return "No file selected."

    if not allowed_file(file.filename):
        return "Invalid file type."

    original_filename = secure_filename(file.filename)
    unique_filename = str(uuid.uuid4()) + "_" + original_filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(filepath)

    price_per_copy = 2 if color_mode == "Black & White" else 5
    total_price = price_per_copy * int(copies)

    new_job = PrintJob(
        filename=unique_filename,
        copies=int(copies),
        color_mode=color_mode,
        paper_size=paper_size,
        price=total_price
    )

    db.session.add(new_job)
    db.session.commit()

    return redirect(url_for('payment', job_id=new_job.job_id))

# ==============================
# PAYMENT PAGE
# ==============================
@app.route('/payment/<job_id>')
def payment(job_id):

    job = PrintJob.query.filter_by(job_id=job_id).first_or_404()

    amount = int(job.price * 100)

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": "1"
    })

    return render_template(
        "payment.html",
        job=job,
        order_id=order['id'],
        razorpay_key=RAZORPAY_KEY_ID
    )

# ==============================
# PAYMENT SUCCESS
# ==============================
@app.route('/pay/<job_id>', methods=['POST'])
def pay(job_id):

    job = PrintJob.query.filter_by(job_id=job_id).first_or_404()

    job.is_paid = True
    db.session.commit()

    qr_data = url_for('kiosk', job_id=job.job_id, _external=True)

    qr = qrcode.make(qr_data)

    qr_path = os.path.join(QR_FOLDER, f"{job.job_id}.png")
    qr.save(qr_path)

    return render_template(
        "success.html",
        job=job,
        qr_image=f"qrcodes/{job.job_id}.png"
    )

# ==============================
# KIOSK
# ==============================
@app.route('/kiosk/<job_id>')
def kiosk(job_id):

    job = PrintJob.query.filter_by(job_id=job_id).first_or_404()

    if not job.is_paid:
        return "Payment not completed."

    if job.status == "Pending":

        job.status = "Printed"

        file_path = os.path.join(app.config['UPLOAD_FOLDER'], job.filename)

        if os.path.exists(file_path):
            os.remove(file_path)

        db.session.commit()

        return "Job printed successfully."

    else:
        return "Already printed."

# ==============================
# DASHBOARD
# ==============================
@app.route('/dashboard')
def dashboard():

    if not session.get('admin'):
        return redirect('/login')

    filter_type = request.args.get('filter', 'all')

    query = PrintJob.query

    if filter_type == 'paid':
        query = query.filter_by(is_paid=True)

    elif filter_type == 'unpaid':
        query = query.filter_by(is_paid=False)

    elif filter_type == 'printed':
        query = query.filter_by(status="Printed")

    elif filter_type == 'pending':
        query = query.filter_by(status="Pending")

    jobs = query.order_by(PrintJob.created_at.desc()).all()

    total_revenue = sum(
        job.price for job in PrintJob.query.filter_by(is_paid=True).all()
    )

    revenue_data = (
        db.session.query(
            func.date(PrintJob.created_at),
            func.sum(PrintJob.price)
        )
        .filter(PrintJob.is_paid == True)
        .group_by(func.date(PrintJob.created_at))
        .order_by(func.date(PrintJob.created_at))
        .all()
    )

    chart_dates = [str(data[0]) for data in revenue_data]
    chart_revenues = [data[1] for data in revenue_data]

    return render_template(
        "dashboard.html",
        jobs=jobs,
        total_revenue=total_revenue,
        current_filter=filter_type,
        chart_dates=chart_dates,
        chart_revenues=chart_revenues
    )

# ==============================
# RUN SERVER
# ==============================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
