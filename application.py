import os

from flask import Flask, session, render_template, request, flash, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from passlib.hash import sha256_crypt

app = Flask(__name__)
app.secret_key = os.urandom(28)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register():
    return render_template("signup.html")


@app.route("/signup", methods=["POST"])
def signup():
    # user sign up

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    username = request.form.get("username")
    password = sha256_crypt.encrypt(str(request.form.get("password")))

    if first_name == '' or last_name == '' or email == '' or username == '' or password == '':
        flash(u'Please fill all the fields!', 'danger')
        return redirect(url_for('register'))

    user = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()
    if user is not None:
        flash(u'Username already in use!', 'danger')
        return redirect(url_for('register'))

    db.execute("INSERT INTO users(first_name, last_name, username, password, email) VALUES (:first_name, :last_name, :username, :password, :email)",
               {"first_name": first_name, "last_name": last_name, "username": username, "password": password, "email": email})
    db.commit()
    db.close()
    flash(u'You have been successfully registered.', 'success')
    return redirect(url_for('register'))


@app.route("/login")
def user_login():
    return render_template("login.html")


@app.route("/home", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == '' or password == '':
            flash('Invalid credentials!', 'danger')
            return redirect(url_for('user_login'))
        if db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone() is None:
            flash(u'Invalid username!', 'danger')
            return redirect(url_for('user_login'))

        user = db.execute("SELECT * FROM users WHERE username = :username", {"username": username}).fetchone()

        if sha256_crypt.verify(password, user.password):
            session.clear()
            session['id'] = user.id
            session['logged_in'] = True
            return render_template("index.html")

        flash(u'Wrong password!', 'danger')
        return redirect(url_for('user_login'))
        db.close()

    return redirect(url_for('user_login'))

# Check if user logged in


def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('user_login'))
    return wrap

@app.route("/dashboard/<int:user_id>")
def dashboard(user_id):
    if 'logged_in' in session:
        if session['id'] == user_id:
            user = db.execute("SELECT * FROM users WHERE id = :id",{"id":user_id}).fetchone()
            return render_template("dashboard.html", user=user)
        else:
            flash('Oops!! Looks like you are attempting something unauthorized!', 'danger')
            return redirect(url_for('index'))

    else:
        flash('Unauthorized, Please login', 'danger')
        return redirect(url_for('user_login'))

@app.route("/logout")
def logout():
    session.clear()
    flash(u'You are now logged out.', 'success')
    return redirect(url_for('user_login'))

@app.route("/review/<int:user_id>/<int:book_id>", methods=["POST"])
def review(user_id,book_id):
    if request.method=="POST":
        review = request.form.get("review")
        db.execute("INSERT INTO reviews(review, book_id, user_id) VALUES (:review, :book_id, :user_id)",{"review":review,"book_id":book_id, "user_id":user_id})
        db.commit()
        db.close()
        return redirect(url_for('book', book_id=book_id))


@app.route("/books")
def books():
        # Lists all the books

    books = db.execute("SELECT * FROM books").fetchall()
    db.close()
    return render_template("books.html", books=books)


@app.route("/books/<int:book_id>")
def book(book_id):
        # Detail about book
    book = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    reviews = db.execute("SELECT * FROM reviews WHERE book_id=:id",{"id":book_id}).fetchall()

    db.close()
    if book is None:
        return render_template("error.html", message="No such book.")

    return render_template("book.html", book=book, reviews=reviews)

@app.route("/search", methods=["GET"])
def search():
    query = request.form.get("search")
    books = db.execute("SELECT * FROM books WHERE title = :query ORDER BY title",
        {"query" : query}).fetchall()
    db.close()
    if books is None:
        flash(u"No book matches your search!", "danger")
        return render_template("books.html", books=books)
    
    flash(u"Search results:", "success")
    return render_template("books.html", books=books)
