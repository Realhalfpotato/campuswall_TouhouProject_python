from flask import Flask, render_template, request, jsonify, redirect, session, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "campus_wall_secret_2026"
DB = "wall.db"


def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS user(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        avatar_path TEXT DEFAULT 'avatar.png'
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS follow(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        follower TEXT NOT NULL,
        target TEXT NOT NULL,
        UNIQUE(follower, target)
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS post(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        author TEXT NOT NULL,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        anonymous INTEGER DEFAULT 0,
        like_count INTEGER DEFAULT 0,
        create_time TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS comment(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        author TEXT,
        content TEXT,
        create_time TEXT
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS like_record(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        username TEXT
    )''')
    conn.commit()
    conn.close()


init_db()

cat_map = {
    "lost": "失物招领",
    "help": "求助问答",
    "trade": "二手交易",
    "talk": "闲聊吐槽"
}
categories = list(cat_map.values())

post_rule = """【发帖须知】
1.禁止发布广告、辱骂、造谣、低俗内容
2.匿名不代表可以肆意发言，后台留存发布者信息
3.二手交易注意甄别风险
4.违规内容管理员有权删除"""


def get_user():
    return session.get("username")


def get_follow_info(username):
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT target FROM follow WHERE follower=?", (username,))
    follow_list = [row["target"] for row in cur.fetchall()]
    cur.execute("SELECT follower FROM follow WHERE target=?", (username,))
    fan_list = [row["follower"] for row in cur.fetchall()]
    conn.close()
    return {
        "follow_count": len(follow_list),
        "fan_count": len(fan_list),
        "follow_list": follow_list,
        "fan_list": fan_list
    }


@app.route("/")
def index():
    user = get_user()
    if not user:
        return redirect(url_for("login"))
    cat = request.args.get("cat")
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    if cat:
        reverse_map = {v: k for k, v in cat_map.items()}
        key = reverse_map.get(cat)
        if key:
            cur.execute("SELECT * FROM post WHERE category=? ORDER BY id DESC", (key,))
        else:
            cur.execute("SELECT * FROM post ORDER BY id DESC")
    else:
        cur.execute("SELECT * FROM post ORDER BY id DESC")
    posts = cur.fetchall()
    conn.close()
    return render_template("index.html",
                           user=user,
                           posts=posts,
                           cat_map=cat_map,
                           categories=categories,
                           select_cat=cat,
                           post_rule=post_rule)


@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT id FROM user WHERE username=? AND password=?", (u, p))
        row = cur.fetchone()
        conn.close()
        if row:
            session["username"] = u
            return redirect(url_for("index"))
        else:
            msg = "账号密码错误"
    return render_template("login.html", msg=msg)


@app.route("/register", methods=["GET", "POST"])
def register():
    msg = ""
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")
        try:
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("INSERT INTO user(username,password) VALUES(?,?)", (u, p))
            conn.commit()
            conn.close()
            session["username"] = u
            return redirect(url_for("index"))
        except sqlite3.IntegrityError:
            msg = "用户名已存在"
    return render_template("register.html", msg=msg)


@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user = get_user()
    if not user:
        return redirect(url_for("login"))
    follow_info = get_follow_info(user)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM post WHERE author=? ORDER BY id DESC", (user,))
    my_posts = cur.fetchall()
    conn.close()
    return render_template("profile.html",
                           user=user,
                           my_posts=my_posts,
                           cat_map=cat_map,
                           **follow_info)


@app.route("/api/follow/<target_name>", methods=["POST"])
def api_follow(target_name):
    me = get_user()
    if not me:
        return jsonify({"code": 403, "msg": "请登录"})
    if me == target_name:
        return jsonify({"code": 400, "msg": "不能关注自己"})
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO follow(follower,target) VALUES(?,?)", (me, target_name))
        conn.commit()
        res_msg = f"已关注 {target_name}"
    except sqlite3.IntegrityError:
        cur.execute("DELETE FROM follow WHERE follower=? AND target=?", (me, target_name))
        conn.commit()
        res_msg = f"已取消关注 {target_name}"
    conn.close()
    return jsonify({"code": 200, "msg": res_msg})


# ======修复：这里补充cat_map参数======
@app.route("/post_detail/<int:pid>")
def post_detail(pid):
    user = get_user()
    if not user:
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM post WHERE id=?", (pid,))
    post = cur.fetchone()
    cur.execute("SELECT * FROM comment WHERE post_id=? ORDER BY id ASC", (pid,))
    comments = cur.fetchall()
    conn.close()
    return render_template("post_detail.html",
                           user=user,
                           post=post,
                           comments=comments,
                           cat_map=cat_map)


@app.route("/api/add_post", methods=["POST"])
def api_add_post():
    user = get_user()
    if not user:
        return jsonify({"code": 403, "msg": "请登录"})
    content = request.form.get("content", "").strip()
    category = request.form.get("category")
    anonymous = 1 if request.form.get("anonymous") else 0
    if not content:
        return jsonify({"code": 400, "msg": "内容不能为空"})
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('''INSERT INTO post(author,category,content,anonymous,like_count,create_time)
        VALUES(?,?,?,?,0,?)''', (user, category, content, anonymous, now_time))
    conn.commit()
    conn.close()
    return jsonify({"code": 200, "msg": "发布成功"})


@app.route("/api/like/<int:pid>", methods=["POST"])
def api_like(pid):
    user = get_user()
    if not user:
        return jsonify({"code": 403, "msg": "请登录"})
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT id FROM like_record WHERE post_id=? AND username=?", (pid, user))
    rec = cur.fetchone()
    if rec:
        cur.execute("DELETE FROM like_record WHERE id=?", (rec[0],))
        cur.execute("UPDATE post SET like_count = like_count -1 WHERE id=?", (pid,))
        msg = "已取消点赞"
    else:
        cur.execute("INSERT INTO like_record(post_id,username) VALUES(?,?)", (pid, user))
        cur.execute("UPDATE post SET like_count = like_count +1 WHERE id=?", (pid,))
        msg = "点赞成功"
    conn.commit()
    conn.close()
    return jsonify({"code": 200, "msg": msg})


@app.route("/api/del_post/<int:pid>", methods=["POST"])
def api_del_post(pid):
    user = get_user()
    if not user:
        return jsonify({"code": 403, "msg": "未登录"})
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT author FROM post WHERE id=?", (pid,))
    row = cur.fetchone()
    if not row or row[0] != user:
        conn.close()
        return jsonify({"code": 403, "msg": "无权删除"})
    cur.execute("DELETE FROM post WHERE id=?", (pid,))
    cur.execute("DELETE FROM comment WHERE post_id=?", (pid,))
    cur.execute("DELETE FROM like_record WHERE post_id=?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({"code": 200, "msg": "删除成功"})


@app.route("/api/add_comment/<int:pid>", methods=["POST"])
def api_add_comment(pid):
    user = get_user()
    if not user:
        return jsonify({"code": 403, "msg": "请登录"})
    content = request.form.get("content", "").strip()
    if not content:
        return jsonify({"code": 400, "msg": "评论不能为空"})
    now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO comment(post_id,author,content,create_time) VALUES(?,?,?,?)",
                (pid, user, content, now_time))
    conn.commit()
    conn.close()
    return jsonify({"code": 200, "msg": "评论成功"})


if __name__ == "__main__":
    app.run(debug=True)
