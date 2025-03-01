import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlalchemy as sa

app = Flask(__name__)

# SECRET_KEY required for sessions
app.config["SECRET_KEY"] = "some_random_secret_key"

# SQLite database config
base_dir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(base_dir, "site_data.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------------------------------------------------------
# 1. MODELS
# -------------------------------------------------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Establishment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    establishment_id = db.Column(db.Integer, db.ForeignKey("establishment.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    # We'll store an integer for convenience; we also can count from PostLike table
    likes = db.Column(db.Integer, default=0)

    establishment = db.relationship("Establishment", backref=db.backref("posts", lazy=True))
    
    # Virtual properties to handle the case when columns don't exist
    @property
    def title(self):
        return f"Post #{self.id}"
    
    @property
    def rating(self):
        return 0.0
        
    @property
    def comment_count(self):
        return Comment.query.filter_by(post_id=self.id).count()
    
    @property
    def time_since(self):
        """Return human-readable time since post creation"""
        now = datetime.utcnow()
        # Just return "剛剛" since we don't have actual timestamps
        return "剛剛"


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)

    post = db.relationship("Post", backref=db.backref("comments", lazy=True))


# NEW MODELS BELOW:

class PostLike(db.Model):
    """
    Table to track which USER has liked which POST.
    We add a UNIQUE constraint on (user_id, post_id).
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)

    # Ensure uniqueness so a user cannot like the same post multiple times.
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),
    )

class CommentLike(db.Model):
    """
    Table to track which USER has liked which COMMENT.
    UNIQUE constraint on (user_id, comment_id).
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("comment.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_like'),
    )

# -------------------------------------------------------------------------
# 2. INITIAL SETUP
# -------------------------------------------------------------------------

@app.before_first_request
def setup_db():
    db.create_all()

    # Insert sample establishments if none exist
    if not Establishment.query.first():
        samples = ["Starbucks", "McDonald's", "KFC"]
        for name in samples:
            est = Establishment(name=name)
            db.session.add(est)
        db.session.commit()


def is_logged_in():
    return "user_id" in session


# Helper function to check if user has already liked a post
def has_user_liked_post(user_id, post_id):
    return PostLike.query.filter_by(user_id=user_id, post_id=post_id).first() is not None


# Helper function to check if user has already liked a comment
def has_user_liked_comment(user_id, comment_id):
    return CommentLike.query.filter_by(user_id=user_id, comment_id=comment_id).first() is not None


# -------------------------------------------------------------------------
# 3. AUTH ROUTES: register, login, logout
# -------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            return render_template("register.html", error="email_exists")

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            return render_template("register.html", error="username_exists")

        new_user = User(email=email, username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash("註冊成功！現在您可以登入", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            return redirect(url_for("home"))
        else:
            if not user:
                return render_template("login.html", error="email_not_found")
            else:
                return render_template("login.html", error="invalid_password")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return redirect(url_for("home"))


# -------------------------------------------------------------------------
# 4. MAIN ROUTES
# -------------------------------------------------------------------------

@app.route("/")
def home():
    """Displays the home page."""
    return render_template("index.html")

@app.route("/establishments")
def list_establishments():
    """Displays a list of all establishments in a dedicated page."""
    search_query = request.args.get('search', '')
    
    if search_query:
        establishments = Establishment.query.filter(Establishment.name.ilike(f"%{search_query}%")).all()
    else:
        establishments = Establishment.query.all()
        
    return render_template("establishments.html", establishments=establishments, search_query=search_query)

@app.route("/establishment/<int:est_id>")
def show_establishment(est_id):
    """Show posts for a specific establishment."""
    establishment = Establishment.query.get_or_404(est_id)
    # Order posts by likes (descending)
    posts = Post.query.filter_by(establishment_id=est_id).order_by(Post.likes.desc()).all()
    
    # Check for search query
    search_query = request.args.get('search', '')
    if search_query:
        # Filter posts that contain the search query in content
        posts = [p for p in posts if search_query.lower() in p.content.lower()]
    
    return render_template("establishment.html", establishment=establishment, posts=posts, search_query=search_query)

@app.route("/establishment/<int:est_id>/new_post", methods=["POST"])
def new_post(est_id):
    if not is_logged_in():
        return jsonify({"status": "error", "message": "您必須登入才能發佈內容"})

    data = request.get_json()
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    rating = float(data.get("rating", 0))
    
    if not content:
        return jsonify({"status": "error", "message": "內容不能為空！"})

    # Ensure the establishment exists
    Establishment.query.get_or_404(est_id)

    # Make a simpler post without the columns that might not exist
    new_p = Post(
        establishment_id=est_id, 
        content=content, 
        likes=0
    )
    
    db.session.add(new_p)
    db.session.commit()

    return jsonify({"status": "success", "message": "發佈成功！"})

@app.route("/post/<int:post_id>")
def show_post(post_id):
    """Show a single post and its comments."""
    post = Post.query.get_or_404(post_id)
    # Get comments sorted by likes (descending)
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.likes.desc()).all()
    
    # Check if user has liked this post
    user_liked_post = False
    if is_logged_in():
        user_liked_post = has_user_liked_post(session["user_id"], post_id)
    
    # Check if user has liked each comment
    user_liked_comments = {}
    if is_logged_in():
        for comment in comments:
            user_liked_comments[comment.id] = has_user_liked_comment(session["user_id"], comment.id)
    
    return render_template("post.html", post=post, comments=comments, 
                          user_liked_post=user_liked_post,
                          user_liked_comments=user_liked_comments)

@app.route("/post/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    if not is_logged_in():
        flash("您必須登入才能發表評論", "error")
        return redirect(url_for("login"))

    Post.query.get_or_404(post_id)
    comment_content = request.form.get("comment", "").strip()
    if not comment_content:
        flash("評論內容不能為空！", "error")
        return redirect(url_for("show_post", post_id=post_id))

    new_c = Comment(
        post_id=post_id, 
        content=comment_content, 
        likes=0
    )
    db.session.add(new_c)
    db.session.commit()
    flash("評論發佈成功！", "success")
    return redirect(url_for("show_post", post_id=post_id))

# -------------------------------------------------------------------------
# 5. LIKE ROUTES (One like per user)
# -------------------------------------------------------------------------

@app.route("/post/<int:post_id>/like", methods=["POST"])
def like_post(post_id):
    """Toggle the like status of a post."""
    if not is_logged_in():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': '您必須登入才能點讚'
            })
        flash("您必須登入才能點讚", "error")
        return redirect(url_for("login"))

    post = Post.query.get_or_404(post_id)
    user_id = session["user_id"]

    # Check if user already liked this post
    existing_like = PostLike.query.filter_by(user_id=user_id, post_id=post_id).first()
    
    if existing_like:
        # Already liked -> remove the like (unlike)
        db.session.delete(existing_like)
        post.likes -= 1
    else:
        # Not liked yet -> add a like
        new_like = PostLike(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1

    db.session.commit()
    
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'likes': post.likes,
            'liked': existing_like is None
        })
    
    # Otherwise redirect back to the post
    return redirect(url_for("show_post", post_id=post_id))

@app.route("/post/<int:post_id>/comment/<int:comment_id>/like", methods=["POST"])
def like_comment(post_id, comment_id):
    """Toggle the like status of a comment."""
    if not is_logged_in():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'status': 'error',
                'message': '您必須登入才能點讚'
            })
        flash("您必須登入才能點讚", "error")
        return redirect(url_for("login"))

    comment = Comment.query.get_or_404(comment_id)
    if comment.post_id != post_id:
        flash("錯誤：評論不屬於此貼文", "error")
        return redirect(url_for("show_post", post_id=post_id))

    user_id = session["user_id"]
    existing_like = CommentLike.query.filter_by(user_id=user_id, comment_id=comment_id).first()
    
    if existing_like:
        # Already liked -> remove the like (unlike)
        db.session.delete(existing_like)
        comment.likes -= 1
    else:
        # Not liked yet -> add a like
        new_like = CommentLike(user_id=user_id, comment_id=comment_id)
        db.session.add(new_like)
        comment.likes += 1

    db.session.commit()
    
    # If it's an AJAX request, return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'status': 'success',
            'likes': comment.likes,
            'liked': existing_like is None
        })
    
    # Otherwise redirect back to the post
    return redirect(url_for("show_post", post_id=post_id))

if __name__ == "__main__":
    app.run(debug=True)