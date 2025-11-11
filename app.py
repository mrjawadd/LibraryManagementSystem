# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-secret'  # change for production
db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'library.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------- Models ----------
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)

    def is_available(self):
        return self.quantity > 0

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

class Borrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)

    user = db.relationship('User', backref=db.backref('borrow_records', cascade='all, delete-orphan'))
    book = db.relationship('Book', backref=db.backref('borrow_records', cascade='all, delete-orphan'))

# ---------- Seed Data ----------
def seed_data():
    # Seed books if none exist
    if Book.query.count() == 0:
        samples = [
            Book(title="Harry Potter and the Sorcerer's Stone", author="J.K. Rowling", quantity=5),
            Book(title="The Hobbit", author="J.R.R. Tolkien", quantity=3),
            Book(title="1984", author="George Orwell", quantity=4),
            Book(title="To Kill a Mockingbird", author="Harper Lee", quantity=2),
        ]
        db.session.bulk_save_objects(samples)
        db.session.commit()

    # Seed a default user if none exist
    if User.query.count() == 0:
        db.session.add(User(name="Alice"))
        db.session.commit()

def create_tables_and_seed():
    """Create DB tables and seed initial data. Safe to call multiple times."""
    with app.app_context():
        db.create_all()
        seed_data()

# Initialize DB and seed (runs once when app starts)
create_tables_and_seed()

# ---------- Routes ----------
@app.route('/')
def index():
    total_books = Book.query.count()
    total_users = User.query.count()
    total_borrowed = Borrow.query.count()
    top = (
        db.session.query(Book.title, func.count(Borrow.id).label('times'))
        .join(Borrow, Book.id == Borrow.book_id, isouter=True)
        .group_by(Book.id)
        .order_by(func.count(Borrow.id).desc())
        .limit(5)
        .all()
    )
    return render_template('index.html', total_books=total_books, total_users=total_users,
                           total_borrowed=total_borrowed, top=top)

# Books
@app.route('/books')
def books():
    q = request.args.get('q', '')
    if q:
        books = Book.query.filter(Book.title.ilike(f'%{q}%')).order_by(Book.title).all()
    else:
        books = Book.query.order_by(Book.title).all()
    return render_template('books.html', books=books, q=q)

@app.route('/books/add', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        title = request.form['title'].strip()
        author = request.form['author'].strip()
        try:
            quantity = int(request.form['quantity'] or 1)
        except ValueError:
            quantity = 1
        if not title or not author:
            flash("Title and author are required.", "warning")
            return redirect(url_for('add_book'))
        book = Book(title=title, author=author, quantity=quantity)
        db.session.add(book)
        db.session.commit()
        flash(f"Book '{title}' added.", "success")
        return redirect(url_for('books'))
    return render_template('add_book.html')

# Users
@app.route('/users')
def users():
    users = User.query.order_by(User.name).all()
    return render_template('users.html', users=users)

@app.route('/users/add', methods=['GET', 'POST'])
def add_user():
    if request.method == 'POST':
        name = request.form['name'].strip()
        if not name:
            flash("User name is required.", "warning")
            return redirect(url_for('add_user'))
        user = User(name=name)
        db.session.add(user)
        db.session.commit()
        flash(f"User '{name}' registered.", "success")
        return redirect(url_for('users'))
    return render_template('add_user.html')

# Borrow
@app.route('/borrow', methods=['GET', 'POST'])
def borrow():
    users = User.query.order_by(User.name).all()
    books = Book.query.filter(Book.quantity > 0).order_by(Book.title).all()
    if request.method == 'POST':
        try:
            user_id = int(request.form['user_id'])
            book_id = int(request.form['book_id'])
        except (ValueError, KeyError):
            flash("Invalid form submission.", "danger")
            return redirect(url_for('borrow'))

        user = User.query.get(user_id)
        book = Book.query.get(book_id)
        if not user or not book:
            flash("Invalid user or book selection.", "danger")
            return redirect(url_for('borrow'))
        if not book.is_available():
            flash(f"'{book.title}' is not available.", "warning")
            return redirect(url_for('borrow'))

        borrow_rec = Borrow(user_id=user.id, book_id=book.id)
        book.quantity -= 1
        db.session.add(borrow_rec)
        db.session.commit()
        flash(f"{user.name} borrowed '{book.title}'.", "success")
        return redirect(url_for('index'))
    return render_template('borrow.html', users=users, books=books)

# Return
@app.route('/return', methods=['GET', 'POST'])
def return_book():
    users = User.query.order_by(User.name).all()
    if request.method == 'POST':
        try:
            user_id = int(request.form['user_id'])
            book_id = int(request.form['book_id'])
        except (ValueError, KeyError):
            flash("Invalid form submission.", "danger")
            return redirect(url_for('return_book'))

        record = Borrow.query.filter_by(user_id=user_id, book_id=book_id).first()
        if not record:
            flash("This borrow record does not exist.", "warning")
            return redirect(url_for('return_book'))
        book = Book.query.get(book_id)
        db.session.delete(record)
        book.quantity += 1
        db.session.commit()
        user = User.query.get(user_id)
        flash(f"{user.name} returned '{book.title}'.", "success")
        return redirect(url_for('index'))
    return render_template('return.html', users=users)

# AJAX helper to fetch a user's borrowed books
@app.route('/user/<int:user_id>/borrowed')
def user_borrowed(user_id):
    records = Borrow.query.filter_by(user_id=user_id).all()
    result = [{"book_id": r.book.id, "title": r.book.title} for r in records]
    return jsonify({"borrowed": result})

# Run
if __name__ == '__main__':
    # For development only. Use a proper WSGI server in production.
    app.run(debug=True)
