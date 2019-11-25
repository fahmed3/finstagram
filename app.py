from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="",
                             db="finsta",
                             charset="utf8mb4",
                             port=3306,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    query = "SELECT owner_username, groupName FROM BelongTo WHERE member_username = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, session['username'])
    data = cursor.fetchall()
    return render_template("upload.html", friendGroups = data)

@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT * FROM photo WHERE AllFollowers AND (photoPoster) IN (SELECT username_followed FROM follow WHERE followStatus AND username_follower = %s) UNION ( SELECT photoID, postingdate, filepath, allFollowers, caption, photoPoster FROM photo NATURAL JOIN SharedWith WHERE (groupOwner, groupName) IN (SELECT owner_username, groupName FROM BelongTo WHERE member_username = %s) ) ORDER BY postingDate DESC"
    with connection.cursor() as cursor:
        cursor.execute(query, (session['username'], session['username']) )
    data = cursor.fetchall()
    return render_template("images.html", images=data)

@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")

@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["GET", "POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, firstName, lastName) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")

@app.route("/uploadImage", methods=["POST"])
@login_required
def upload_image():
    if request.files:
        allFollowers = False
        caption = request.form["caption"]
        #print(request.form.getlist("allFollowers"))
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        query = "INSERT INTO photo (postingDate, filepath, allFollowers, caption, photoPoster) VALUES (%s, %s, %s, %s, %s)"
        
        if "allFollowers" in request.form:
            allFollowers = True
            with connection.cursor() as cursor:
                cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers, caption, session["username"]))
        else:
            with connection.cursor() as cursor:
                cursor.execute(query, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, allFollowers, caption, session["username"]))
                id = cursor.lastrowid #gets id of last inserted row
            #print(id)
            groups = request.form.getlist("friendgroup") #list of friend groups from checkboxes
            shareWithQuery = "INSERT INTO SharedWith (groupOwner, groupName, photoID) VALUES (%s, %s, %s)"
            for group in groups:
                g = group.split(",")
                #print(g)
                #g[0] -> owner_username
                #g[1] -> groupName
                with connection.cursor() as cursor:
                    cursor.execute(shareWithQuery, (g[0], g[1], id) )
        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug = True)
