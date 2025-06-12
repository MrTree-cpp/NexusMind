import os
import logging
from datetime import datetime, date # Ensured imports
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder_path = os.path.join(basedir, 'instance')
db_path = os.path.join(instance_folder_path, 'app.db')

if not os.path.exists(instance_folder_path):
    os.makedirs(instance_folder_path)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_very_secret_key_for_flash_and_sessions'

if not app.debug and not app.testing:
    if not app.logger.handlers:
        from logging.handlers import RotatingFileHandler
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/nexusmanager.log', maxBytes=10240, backupCount=5)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [PID %(process)d] [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('NexusManager application starting up...')
else:
    if not app.logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.DEBUG)
    app.logger.debug('NexusManager running in DEBUG mode.')


db = SQLAlchemy(app)

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    initial_hours = db.Column(db.Float, default=0.0)
    default_call_out_time = db.Column(db.Integer, default=30)
    contracts = db.relationship('Contract', backref='client', lazy=True, cascade="all, delete-orphan")
    interventions = db.relationship('Intervention', backref='client', lazy=True, cascade="all, delete-orphan")
    hour_purchases = db.relationship('HourPurchase', backref='client', lazy=True, cascade="all, delete-orphan")
    def __repr__(self): return f'<Client {self.name}>'

class Contract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    annual_fee = db.Column(db.Float, nullable=True)
    contract_expiry_date = db.Column(db.Date, nullable=True)
    includes_call_out_fee = db.Column(db.Boolean, default=True)
    min_chargeable_time = db.Column(db.Integer, default=30)
    call_out_time_if_not_included = db.Column(db.Integer, default=30)
    def __repr__(self): return f'<Contract {self.id} for Client {self.client_id}>'

class Intervention(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    intervention_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    technician_name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=False)
    is_remote = db.Column(db.Boolean, default=False)
    time_spent_on_site = db.Column(db.Integer, nullable=False)
    def __repr__(self): return f'<Intervention {self.id} on {self.intervention_date.strftime("%Y-%m-%d")}>'

class HourPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    hours_purchased = db.Column(db.Float, nullable=False)
    invoice_reference = db.Column(db.String(200), nullable=True)
    def __repr__(self): return f'<HourPurchase {self.id} of {self.hours_purchased}h for Client {self.client_id}>'

@app.route('/')
def index():
    try: return render_template('index.html', message="Welcome to NexusManager!")
    except Exception as e:
        app.logger.error(f"Error rendering index.html: {e}")
        return "Welcome to NexusManager! Error loading template."

@app.route('/dashboard')
def dashboard():
    try: return render_template('dashboard.html')
    except: return render_template('base.html', title='Dashboard')

@app.route('/clients')
def list_clients():
    clients = Client.query.order_by(Client.name).all()
    return render_template('clients/list_clients.html', clients=clients)

@app.route('/clients/add', methods=['GET', 'POST'])
def add_client():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form.get('email')
        notes = request.form.get('notes')
        try:
            initial_hours = float(request.form.get('initial_hours', 0.0) or 0.0)
            default_call_out_time = int(request.form.get('default_call_out_time', 30) or 30)
        except ValueError:
            flash('Invalid input for hours or call-out time.', 'danger')
            return render_template('clients/add_client.html', form_data=request.form)

        if not name:
            flash('Client name is required.', 'danger')
            return render_template('clients/add_client.html', form_data=request.form)
        if Client.query.filter_by(name=name).first():
            flash(f'Client with name "{name}" already exists.', 'warning')
            return render_template('clients/add_client.html', form_data=request.form)
        new_client = Client(name=name, email=email, notes=notes, initial_hours=initial_hours, default_call_out_time=default_call_out_time)
        try:
            db.session.add(new_client)
            db.session.commit()
            flash(f'Client "{name}" added successfully!', 'success')
            return redirect(url_for('list_clients'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding client {name}: {e}")
            flash(f'Error adding client: {str(e)}', 'danger')
    return render_template('clients/add_client.html')

@app.route('/clients/<int:client_id>')
def view_client(client_id):
    client = Client.query.get_or_404(client_id)
    return render_template('clients/view_client.html', client=client)

@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        new_name = request.form['name']
        if not new_name:
            flash('Client name cannot be empty.', 'danger')
            return render_template('clients/edit_client.html', client=client)
        if new_name != client.name and Client.query.filter(Client.name == new_name, Client.id != client_id).first():
            flash(f'Another client with the name "{new_name}" already exists.', 'warning')
            return render_template('clients/edit_client.html', client=client)
        client.name = new_name
        client.email = request.form.get('email')
        client.notes = request.form.get('notes')
        try:
            client.initial_hours = float(request.form.get('initial_hours', client.initial_hours) or 0.0)
            client.default_call_out_time = int(request.form.get('default_call_out_time', client.default_call_out_time) or 30)
        except ValueError:
            flash('Invalid input for hours or call-out time.', 'danger')
            return render_template('clients/edit_client.html', client=client)

        try:
            db.session.commit()
            flash(f'Client "{client.name}" updated successfully!', 'success')
            return redirect(url_for('view_client', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating client {client.id}: {e}")
            flash(f'Error updating client: {str(e)}', 'danger')
    return render_template('clients/edit_client.html', client=client)

@app.route('/clients/<int:client_id>/delete', methods=['POST'])
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    try:
        db.session.delete(client)
        db.session.commit()
        flash(f'Client "{client.name}" and all related data deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting client {client.id}: {e}")
        flash(f'Error deleting client: {str(e)}.', 'danger')
    return redirect(url_for('list_clients'))

# --- Contract Management Routes ---
@app.route('/clients/<int:client_id>/contracts/add', methods=['GET', 'POST'])
def add_contract(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        annual_fee_str = request.form.get('annual_fee')
        annual_fee = float(annual_fee_str) if annual_fee_str and annual_fee_str.strip() else None
        contract_expiry_date_str = request.form.get('contract_expiry_date')
        contract_expiry_date = datetime.strptime(contract_expiry_date_str, '%Y-%m-%d').date() if contract_expiry_date_str else None
        includes_call_out_fee = 'includes_call_out_fee' in request.form
        min_chargeable_time = int(request.form.get('min_chargeable_time', 30))
        call_out_time_if_not_included = int(request.form.get('call_out_time_if_not_included', 30))
        new_contract = Contract(client_id=client.id, annual_fee=annual_fee, contract_expiry_date=contract_expiry_date, includes_call_out_fee=includes_call_out_fee, min_chargeable_time=min_chargeable_time, call_out_time_if_not_included=call_out_time_if_not_included)
        try:
            db.session.add(new_contract)
            db.session.commit()
            flash('Contract added successfully!', 'success')
            return redirect(url_for('view_client', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding contract for client {client.id}: {e}")
            flash(f'Error adding contract: {str(e)}', 'danger')
    return render_template('contracts/add_contract.html', client=client)

@app.route('/contracts/<int:contract_id>/edit', methods=['GET', 'POST'])
def edit_contract(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    if request.method == 'POST':
        annual_fee_str = request.form.get('annual_fee')
        contract.annual_fee = float(annual_fee_str) if annual_fee_str and annual_fee_str.strip() else None
        contract_expiry_date_str = request.form.get('contract_expiry_date')
        contract.contract_expiry_date = datetime.strptime(contract_expiry_date_str, '%Y-%m-%d').date() if contract_expiry_date_str else None
        contract.includes_call_out_fee = 'includes_call_out_fee' in request.form
        contract.min_chargeable_time = int(request.form.get('min_chargeable_time', 30))
        contract.call_out_time_if_not_included = int(request.form.get('call_out_time_if_not_included', 30))
        try:
            db.session.commit()
            flash('Contract updated successfully!', 'success')
            return redirect(url_for('view_client', client_id=contract.client_id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating contract {contract.id}: {e}")
            flash(f'Error updating contract: {str(e)}', 'danger')
    return render_template('contracts/edit_contract.html', contract=contract, client=contract.client)

@app.route('/contracts/<int:contract_id>/delete', methods=['POST'])
def delete_contract(contract_id):
    contract = Contract.query.get_or_404(contract_id)
    client_id = contract.client_id
    try:
        db.session.delete(contract)
        db.session.commit()
        flash('Contract deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting contract {contract.id}: {e}")
        flash(f'Error deleting contract: {str(e)}', 'danger')
    return redirect(url_for('view_client', client_id=client_id))

def init_db():
    with app.app_context():
        if not os.path.exists(instance_folder_path):
            os.makedirs(instance_folder_path)
        db.create_all()
        app.logger.info("Database tables created (if they didn't exist).")


# --- Hour Purchase Management Routes ---
@app.route('/clients/<int:client_id>/hourpurchase/add', methods=['GET', 'POST'])
def add_hour_purchase(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        hours_purchased_str = request.form.get('hours_purchased')
        purchase_date_str = request.form.get('purchase_date')
        invoice_reference = request.form.get('invoice_reference')

        if not hours_purchased_str or not purchase_date_str:
            flash('Hours purchased and purchase date are required.', 'danger')
            return render_template('hour_purchases/add_hour_purchase.html', client=client, today_date=date.today().strftime('%Y-%m-%d'), form_data=request.form)

        try:
            hours_purchased = float(hours_purchased_str)
            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid data for hours or date.', 'danger')
            return render_template('hour_purchases/add_hour_purchase.html', client=client, today_date=date.today().strftime('%Y-%m-%d'), form_data=request.form)

        if hours_purchased <= 0:
            flash('Hours purchased must be positive.', 'warning')
            return render_template('hour_purchases/add_hour_purchase.html', client=client, today_date=date.today().strftime('%Y-%m-%d'), form_data=request.form)

        new_purchase = HourPurchase(
            client_id=client.id,
            hours_purchased=hours_purchased,
            purchase_date=datetime.combine(purchase_date, datetime.min.time()),
            invoice_reference=invoice_reference
        )
        try:
            db.session.add(new_purchase)
            db.session.commit()
            flash('Hour purchase recorded successfully!', 'success')
            return redirect(url_for('view_client', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error recording hour purchase for client {client.id}: {e}')
            flash(f'Error recording hour purchase: {str(e)}', 'danger')

    return render_template('hour_purchases/add_hour_purchase.html', client=client, today_date=date.today().strftime('%Y-%m-%d'))

@app.route('/hourpurchase/<int:purchase_id>/delete', methods=['POST'])
def delete_hour_purchase(purchase_id):
    purchase = HourPurchase.query.get_or_404(purchase_id)
    client_id = purchase.client_id
    try:
        db.session.delete(purchase)
        db.session.commit()
        flash('Hour purchase record deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting hour purchase {purchase.id}: {e}')
        flash(f'Error deleting hour purchase record: {str(e)}', 'danger')
    return redirect(url_for('view_client', client_id=client_id))



# --- Intervention Management Routes ---
@app.route('/clients/<int:client_id>/intervention/add', methods=['GET', 'POST'])
def add_intervention(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        intervention_date_str = request.form.get('intervention_date')
        technician_name = request.form.get('technician_name')
        description = request.form.get('description')
        time_spent_on_site_str = request.form.get('time_spent_on_site')
        is_remote = 'is_remote' in request.form

        if not intervention_date_str or not description or not time_spent_on_site_str:
            flash('Intervention date, description, and time spent are required.', 'danger')
            return render_template('interventions/add_intervention.html', client=client, now_datetime=datetime.utcnow().strftime('%Y-%m-%dT%H:%M'), form_data=request.form)

        try:
            intervention_date = datetime.strptime(intervention_date_str, '%Y-%m-%dT%H:%M')
            time_spent_on_site = int(time_spent_on_site_str)
        except ValueError:
            flash('Invalid data format for date or time spent.', 'danger')
            return render_template('interventions/add_intervention.html', client=client, now_datetime=datetime.utcnow().strftime('%Y-%m-%dT%H:%M'), form_data=request.form)

        if time_spent_on_site <= 0:
            flash('Time spent must be a positive number of minutes.', 'warning')
            return render_template('interventions/add_intervention.html', client=client, now_datetime=datetime.utcnow().strftime('%Y-%m-%dT%H:%M'), form_data=request.form)

        new_intervention = Intervention(
            client_id=client.id,
            intervention_date=intervention_date,
            technician_name=technician_name,
            description=description,
            is_remote=is_remote,
            time_spent_on_site=time_spent_on_site
        )
        try:
            db.session.add(new_intervention)
            db.session.commit()
            flash('Intervention logged successfully!', 'success')
            return redirect(url_for('view_client', client_id=client.id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error logging intervention for client {client.id}: {e}')
            flash(f'Error logging intervention: {str(e)}', 'danger')

    return render_template('interventions/add_intervention.html', client=client, now_datetime=datetime.utcnow().strftime('%Y-%m-%dT%H:%M'))

@app.route('/intervention/<int:intervention_id>/delete', methods=['POST'])
def delete_intervention(intervention_id):
    intervention = Intervention.query.get_or_404(intervention_id)
    client_id = intervention.client_id
    try:
        db.session.delete(intervention)
        db.session.commit()
        flash('Intervention record deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error deleting intervention {intervention.id}: {e}')
        flash(f'Error deleting intervention record: {str(e)}', 'danger')
    return redirect(url_for('view_client', client_id=client_id))


@app.cli.command('init-db')
def init_db_command_wrapper():
    init_db()
    print('Initialized the database.')

if __name__ == '__main__':
    with app.app_context():
        if not os.path.exists(db_path):
            print("Database file not found at app startup, creating and initializing...")
            init_db()
            print("Database initialized automatically on first run.")
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5007)))
