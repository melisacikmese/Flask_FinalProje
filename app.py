from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, SubmitField
from wtforms.validators import DataRequired, NumberRange
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'cok_gizli_ve_guclu_bir_anahtar_degistirilmeli' 

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    
    transactions = db.relationship('Transaction', backref='owner', lazy=True)

    def set_password(self, password):
        """Şifreyi hashleyerek kaydeder"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Hashlenmiş şifreyi kontrol eder"""
        return check_password_hash(self.password_hash, password)

class Transaction(db.Model):
    """Bütçe İşlemlerini (Gelir/Gider) Tutar"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False) 
    type = db.Column(db.String(10), nullable=False) 
    date = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 

    def __repr__(self):
        return f'<Transaction {self.title} - {self.amount}>'

with app.app_context():
    db.create_all()

class TransactionForm(FlaskForm):
    title = StringField('Başlık', validators=[DataRequired()])
    amount = FloatField('Miktar (TL)', validators=[DataRequired(), NumberRange(min=0.01)])
    transaction_type = SelectField('Tür', choices=[('Gider', 'Gider'), ('Gelir', 'Gelir')], validators=[DataRequired()])
    category = SelectField('Kategori', choices=[
        ('Maaş', 'Maaş'), ('Yatırım', 'Yatırım'), ('Kira', 'Kira'),
        ('Gıda', 'Gıda'), ('Fatura', 'Fatura'), ('Ulaşım', 'Ulaşım'),
        ('Eğlence', 'Eğlence'), ('Diğer', 'Diğer')
    ], validators=[DataRequired()])
    submit = SubmitField('Kaydet')

class RegistrationForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired()])
    password = StringField('Şifre', validators=[DataRequired()])
    submit = SubmitField('Kayıt Ol')

class LoginForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired()])
    password = StringField('Şifre', validators=[DataRequired()])
    submit = SubmitField('Giriş Yap')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Yeni kullanıcı kaydı"""
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            return render_template('register.html', form=form, error="Bu kullanıcı adı zaten alınmış.")
        
        new_user = User(username=form.username.data)
        new_user.set_password(form.password.data)
        
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
        
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Kullanıcı girişi"""
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user) 
            return redirect(url_for('index'))
        else:
            return render_template('login.html', form=form, error="Geçersiz kullanıcı adı veya şifre.")
            
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required 
def logout():
    """Kullanıcı çıkışı"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset', methods=['POST'])
@login_required 
def reset_data():
    """Giriş yapmış kullanıcının tüm bütçe işlemlerini siler."""
    
    transactions_to_delete = Transaction.query.filter_by(user_id=current_user.id)
    
    transactions_to_delete.delete()
    

    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
@login_required 
def index():
    """Ana bütçe takip sayfası ve işlem kaydetme"""
    form = TransactionForm()
    
    if form.validate_on_submit():
        amount = form.amount.data
        t_type = form.transaction_type.data
        
        if t_type == 'Gider':
            amount = -abs(amount)
        
        new_transaction = Transaction(
            title=form.title.data,
            amount=amount,
            type=t_type,
            category=form.category.data,
            date=datetime.utcnow(),
            user_id=current_user.id 
        )
        
        db.session.add(new_transaction)
        db.session.commit()
        
        return redirect(url_for('index'))

    
    all_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()


    total_income = sum(t.amount for t in all_transactions if t.type == 'Gelir')
    total_expense = sum(t.amount for t in all_transactions if t.type == 'Gider')
    net_balance = total_income + total_expense
    
 
    expense_by_category = {}
    for t in all_transactions:
        if t.type == 'Gider':
            category = t.category
            amount = abs(t.amount)
            expense_by_category[category] = expense_by_category.get(category, 0) + amount

    chart_labels = list(expense_by_category.keys())
    chart_data = [round(v, 2) for v in list(expense_by_category.values())]

    return render_template(
        'index.html', 
        form=form, 
        transactions=all_transactions, 
        total_income=total_income,
        total_expense=abs(total_expense),
        net_balance=net_balance,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

if __name__ == '__main__':
    app.run(debug=True)