from flask import Flask, render_template, request, session, redirect, url_for, send_file, flash
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time
1
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
    #get all unresponded to requests
    query = "SELECT f.username_follower, firstName, lastName FROM follow AS f JOIN person AS p ON p.username = f.username_follower WHERE username_followed = %s AND followstatus=0"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"]))
    requests = cursor.fetchall()
    #get all followers
    query = "SELECT firstName, lastName FROM follow AS f JOIN person AS p ON p.username = f.username_follower WHERE username_followed = %s AND followstatus=1"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"]))
    followers = cursor.fetchall()
    return render_template("home.html", username=session["username"], requests=requests, followers=followers)

@app.route("/groups")
@login_required
def groups():
    query = "SELECT * FROM friendgroup WHERE groupOwner = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, session['username'])
    data = cursor.fetchall()
    return render_template("groups.html", groups = data)

@app.route("/newgroup")
@login_required
def newgroup():
    return render_template("newgroup.html")

@app.route("/createnewgroup", methods=["GET", "POST"])
@login_required
def createnewgroup():
    if request.form:
        name = request.form["groupName"]
        description = request.form["description"]    
    with connection.cursor() as cursor:
        query = "SELECT * FROM friendgroup WHERE groupOwner = %s AND groupName = %s"
        cursor.execute(query, (session['username'], name))
        data = cursor.fetchone()
        if data:
            message = "Failed to create group, you already have a group with that name."
            flash(message)
            return redirect(url_for("groups"))
        else:
            #create new group
            query = "INSERT INTO friendgroup VALUES (%s, %s, %s);"
            cursor.execute(query, (session['username'], name, description ))
            #add user as member of the group they just created
            query = "INSERT INTO belongto VALUES (%s, %s, %s);"
            cursor.execute(query,(session['username'],session['username'],name))
            message = "Successfully created new friend group."
            flash(message)
            return redirect(url_for("groups"))            

@app.route("/groupdetails", methods=["GET", "POST"])
@login_required
def groupdetails():
    if request.form:
        groupdetails = request.form["details"]
        g = groupdetails.split(",")
        groupOwner = g[0]
        groupName = g[1]
    query = "SELECT member_username FROM belongto WHERE owner_username = %s AND groupName = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, (groupOwner, groupName))
    data = cursor.fetchall()
    return render_template("groupdetails.html",
                           members = data,
                           groupName = groupName)

@app.route("/addmember", methods=["GET", "POST"])
@login_required
def addmember():
    if request.form:
        username = request.form["username"]
        groupName = request.form["groupdetails"]
    query = "SELECT * FROM person WHERE username = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, (username))
    data = cursor.fetchone()
    if data: #if username exists
        query = "SELECT * FROM belongto WHERE member_username = %s AND owner_username = %s AND groupName = %s"
        with connection.cursor() as cursor:
            cursor.execute(query, (username, session['username'], groupName))
        data = cursor.fetchone()
        if data: #if username in group already
            message = username + " is already in the group!"
            return render_template("addmember.html", success = False, message=message)
        else:
            query = "INSERT INTO belongto VALUES (%s, %s, %s);"
            with connection.cursor() as cursor:
                cursor.execute(query, (username, session['username'], groupName))
            return render_template("addmember.html", success = True)
    else:
        message = "Please make sure to type in the username correctly." 
        return render_template("addmember.html", success = False, message = message)


    #MAKE THIS WORK
@app.route("/follow", methods=["GET", "POST"])
@login_required
def follow():
    if request.form:
        username = request.form["username"]
    query = "SELECT username, firstName, lastName, bio FROM person WHERE username = %s"
    with connection.cursor() as cursor:
        cursor.execute(query, (username))
    data = cursor.fetchone()
    if data:
        return render_template("follow.html", userfound = True, user = data)
    else:
        message = "No user found with this username, please make sure you type in the username correctly."
        return render_template("follow.html", userfound = False)

@app.route("/sendfollow", methods=["GET", "POST"])
@login_required
def sendfollow():
    if request.form:
        username = request.form["follow"]
    query = "INSERT INTO follow VALUES (%s, %s, %s)"
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (username, session["username"], 0))
        flash("Follow requested.")
    except pymysql.err.IntegrityError:
        flash("You've already requested to follow this user or you already follow them.")
    return redirect(url_for("home"))

@app.route("/accept", methods=["GET", "POST"])
@login_required
def accept():
    if request.form:
        if "accept" in request.form:
            username = request.form["accept"]
            query = "UPDATE follow SET followstatus = 1 WHERE username_follower = %s AND username_followed = %s"
            with connection.cursor() as cursor:
                cursor.execute(query, (username, session["username"]))
            flash(username + " is now a follower.")
        if "decline" in request.form:
            username = request.form["decline"]
            query = "DELETE FROM follow WHERE username_follower = %s AND username_followed = %s"
            with connection.cursor() as cursor:
                cursor.execute(query, (username, session["username"]))
            flash("You've declined the follow request by " + username + ".")
    return redirect(url_for("home"))

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
    #visible_photos view created once
    #query = "CREATE VIEW AS SELECT * FROM photo WHERE AllFollowers AND (photoPoster) IN (SELECT username_followed FROM follow WHERE followStatus AND username_follower = %s) UNION ( SELECT photoID, postingdate, filepath, allFollowers, caption, photoPoster FROM photo NATURAL JOIN SharedWith WHERE (groupOwner, groupName) IN (SELECT owner_username, groupName FROM BelongTo WHERE member_username = %s) ) ORDER BY postingDate DESC"
    #with connection.cursor() as cursor:
    #    cursor.execute(query, (session['username'], session['username']) )

    #also only executed once
    #view to get the number of likes and tagged people on each post
    #"CREATE VIEW numLikesAndTags AS SELECT photoID, IFNULL(n, 0) AS numtagged, numlikes FROM visible_photos LEFT JOIN (SELECT photoID, count(DISTINCT username) AS n FROM visible_photos LEFT JOIN tagged USING (photoID) WHERE tagstatus = 1 GROUP BY photoID) AS numTags USING (photoID) LEFT JOIN (SELECT photoID, count(liketime) AS numlikes FROM visible_photos LEFT JOIN likes USING (photoID) GROUP BY photoID) AS numoflikes USING (photoID)"
    
    query = "SELECT photoID, postingdate, filepath, allFollowers, caption, photoPoster, firstName, lastName, numLikes, numTagged FROM visible_photos JOIN person ON photoPoster = username JOIN numlikesandtags USING (photoID) ORDER BY postingdate DESC"
    with connection.cursor() as cursor:
        cursor.execute(query)
    images = cursor.fetchall()

    #if likes is selected for a photo, details is true
    details = request.args.get('details')    
    if details:
        photoID = request.args.get('photoID')
        #get all likes and ratings for photo
        query = "SELECT username, rating FROM likes WHERE photoID = %s ORDER BY liketime DESC"
        with connection.cursor() as cursor:
            cursor.execute(query, (photoID))
        likes = cursor.fetchall()
        query = "SELECT username FROM tagged WHERE photoID = %s AND tagstatus = 1"
        with connection.cursor() as cursor:
            cursor.execute(query, (photoID))
        tags = cursor.fetchall()
        return render_template("images.html",
                               details= details,
                               likes = likes,
                               tags = tags)
    return render_template("images.html", images=images)

@app.route("/image", methods=["GET", "POST"])
def imageDetails():
    if request.method == 'POST':
        photoID = request.form['photoID']
    return redirect(url_for("images", details=True, photoID = photoID))

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
        if "friendgroup" in request.form:
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
        flash(message) #added flash since only difference between upload and uploadImage was the message
        return redirect(url_for("upload"))
        #return render_template("upload.html", message=message)
    else:
        message = "Failed to upload image."
        flash(message)
        return redirect(url_for("upload"))
        #return render_template("upload.html", message=message)

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run(debug = True)
