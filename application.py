import os
import requests

from flask import Flask, session, render_template, request, flash, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from passlib.hash import sha256_crypt

app = Flask(__name__)
app.secret_key = os.urandom(28)

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgres://pxxzyihasjzuii:e687475b54944c5767133f157930a35d6301b3e47d79ab6675dcc2d34df0859d@ec2-174-129-18-98.compute-1.amazonaws.com:5432/d245qbs9kvupbv")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    try:
        return render_template("index.html")
    except TimeoutError:
        return render_template("error.html", message="looks like something went wrong")


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

    used_email = db.execute("SELECT * FROM users WHERE email = :email", {"email": email}).fetchone()
    if used_email is not None:
        flash(u'Email already in use!', 'danger')
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
            return render_template("index.html", username=user.username)

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
            user = db.execute("SELECT * FROM users WHERE id = :id",{"id" : user_id}).fetchone()
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


@app.route("/books/<int:book_id>")
def book(book_id):
        # Detail about book
    book_ = db.execute("SELECT * FROM books WHERE id = :id", {"id": book_id}).fetchone()
    reviews = db.execute("SELECT * FROM reviews WHERE book_id=:id",{"id":book_id}).fetchall()

    db.close()
    if book_ is None:
        return render_template("error.html", message="No such book.")

    rating = 0
    count = 0
    for review in reviews:
        rating += review.rating
        count += 1

    if count:
        average_rating = rating / count
    else:
        rating = 0

# Goodreads API
    res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "6OOHh35wgg9yplRXmlARw", "isbns": book_.isbn}).json()["books"][0]

    goodreads_rating = res ["average_rating"]


    return render_template("book.html", book=book_, reviews=reviews,kitab_rating=average_rating, goodreads_rating=goodreads_rating)


@app.route("/search", methods=["POST"])
def search():
    try:
        if "logged_in" not in session:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('user_login'))

        query = request.form.get("search")
        option = request.form.get("search_option")

        if option == 'year':
            booklist = db.execute("SELECT * FROM books WHERE year = :query ORDER BY title",
                                    {"query" : query}).fetchall()
        else:
            booklist = db.execute("SELECT * FROM books WHERE UPPER(" + option + ") = :query ORDER BY title",
                                    {"query" : query.upper()}).fetchall()


        #for matching search queries of book title, author and isbn
        if len(booklist) == 0:
            booklist = db.execute("SELECT * FROM books WHERE UPPER(" + option +") LIKE :query ORDER BY title",
                                    {"query" : "%" + query.upper() + "%"}).fetchall()
            if len(booklist) == 0:
                flash(u"No results found!", "danger")
                return render_template("books.html")
            else:
                flash(u"No results match your search. Similar results:", "danger")
                return render_template("books.html", books=booklist)

        if len(booklist) == 0:
            flash(u"No book matches your search!", "danger")
            return render_template("books.html", books=booklist)

        flash(u"Search results for", "success")
        return render_template("books.html", is_book = True, books = booklist, option = option, info = query)

    except TimeoutError:
        return render_template("error.html", message="Looks like something went wrong!")

#api for kitab
@app.route("/api/<isbn>", methods= ["GET"])
def book_api(isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn" : isbn}).fetchone()
    if book is None:
        return render_template("error.html", message =  "Error : Invalid isbn")
    reviews = db.execute("SELECT * FROM reviews WHERE book_id = :book_id", {"book_id" : book.id}).fetchall()

    rating = 0
    count = 0
    for review in reviews:
        rating += review.rating
        count += 1

    if count:
        average_rating = rating / count
    else:
        rating = 0
    return jsonify({
        "isbn" : book.isbn,
        "title" : book.title,
        "author" : book.author,
        "kitab_rating" : average_rating,
        "rating_count" : count
    })


if __name__ == "__main__":
    app.run(debug=True)
