from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass

from flask import Flask, redirect, render_template, request, session, url_for


DATABASE_PATH = os.path.join("instance", "shop.db")


@dataclass
class Item:
    id: int
    name: str
    price: float
    quantity: int


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
            """
        )
        existing_shop = connection.execute(
            "SELECT id FROM shops ORDER BY id LIMIT 1"
        ).fetchone()
        if existing_shop is None:
            connection.execute("INSERT INTO shops (name) VALUES (?)", ("Default Shop",))
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'worker'))
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
            """
        )
        item_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(items)").fetchall()
        }
        if "shop_id" not in item_columns:
            connection.execute(
                "ALTER TABLE items ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                total REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(shop_id) REFERENCES shops(id),
                FOREIGN KEY(item_id) REFERENCES items(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        existing_admin = connection.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        if existing_admin is None:
            connection.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                ("admin", "admin123", "admin"),
            )
        connection.commit()


def fetch_items(shop_id: int | None) -> list[Item]:
    if shop_id is None:
        return []
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, price, quantity
            FROM items
            WHERE shop_id = ?
            ORDER BY id DESC
            """,
            (shop_id,),
        ).fetchall()
    return [Item(**row) for row in rows]


def fetch_item(item_id: int, shop_id: int | None = None) -> Item | None:
    with get_connection() as connection:
        if shop_id is None:
            row = connection.execute(
                "SELECT id, name, price, quantity FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT id, name, price, quantity FROM items WHERE id = ? AND shop_id = ?",
                (item_id, shop_id),
            ).fetchone()
    if row is None:
        return None
    return Item(**row)


def create_item(shop_id: int, name: str, price: float, quantity: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO items (shop_id, name, price, quantity) VALUES (?, ?, ?, ?)",
            (shop_id, name, price, quantity),
        )
        connection.commit()


def update_item(item_id: int, name: str, price: float, quantity: int) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE items
            SET name = ?, price = ?, quantity = ?
            WHERE id = ?
            """,
            (name, price, quantity, item_id),
        )
        connection.commit()


def delete_item(item_id: int) -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM items WHERE id = ?", (item_id,))
        connection.commit()


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
init_db()


def get_current_user() -> sqlite3.Row | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    with get_connection() as connection:
        return connection.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()


def require_login() -> sqlite3.Row | None:
    user = get_current_user()
    if user is None:
        return None
    return user


def require_admin(user: sqlite3.Row) -> bool:
    return user["role"] == "admin"


def get_current_shop_id() -> int | None:
    return session.get("shop_id")


def set_current_shop(shop_id: int | None) -> None:
    session["shop_id"] = shop_id


@app.route("/")
def index() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    status = request.args.get("update_status")
    update_ok = request.args.get("update_ok")
    sell_status = request.args.get("sell_status")
    sell_ok = request.args.get("sell_ok")
    shop_id = get_current_shop_id()
    return render_template(
        "index.html",
        items=fetch_items(shop_id),
        user=user,
        shop_id=shop_id,
        update_status=status,
        update_ok=update_ok,
        sell_status=sell_status,
        sell_ok=sell_ok,
    )


def run_updates() -> tuple[bool, str]:
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    git_result = subprocess.run(
        ["git", "-C", repo_dir, "pull", "--ff-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_result.returncode != 0:
        return False, "Git pull failed. Check server logs."
    pip_result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", os.path.join(repo_dir, "requirements.txt")],
        capture_output=True,
        text=True,
        check=False,
    )
    if pip_result.returncode != 0:
        return False, "Dependency install failed. Check server logs."
    return True, "Update completed successfully."


@app.route("/item/new", methods=["GET", "POST"])
def new_item() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = get_current_shop_id()
    if shop_id is None:
        return redirect(url_for("shops"))
    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        create_item(shop_id, name, price, quantity)
        return redirect(url_for("index"))
    return render_template("item_form.html", item=None, user=user, shop_id=shop_id)


@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id: int) -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = get_current_shop_id()
    item = fetch_item(item_id)
    if item is None:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        update_item(item_id, name, price, quantity)
        return redirect(url_for("index"))
    return render_template("item_form.html", item=item, user=user, shop_id=shop_id)


@app.post("/item/<int:item_id>/delete")
def remove_item(item_id: int) -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    delete_item(item_id)
    return redirect(url_for("index"))


@app.post("/update")
def update_app() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    success, message = run_updates()
    return redirect(url_for("index", update_status=message, update_ok=str(success).lower()))


@app.route("/sell", methods=["GET", "POST"])
def sell_item() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = get_current_shop_id()
    if shop_id is None:
        return redirect(url_for("shops"))
    items = fetch_items(shop_id)
    if request.method == "POST":
        try:
            item_id = int(request.form["item_id"])
            quantity = int(request.form["quantity"])
        except (TypeError, ValueError):
            return redirect(
                url_for(
                    "index",
                    sell_status="Please select a valid item and quantity.",
                    sell_ok="false",
                )
            )
        item = fetch_item(item_id, shop_id)
        if item is None:
            return redirect(
                url_for(
                    "index",
                    sell_status="Selected item not found.",
                    sell_ok="false",
                )
            )
        if quantity <= 0:
            return redirect(
                url_for(
                    "index",
                    sell_status="Quantity must be at least 1.",
                    sell_ok="false",
                )
            )
        if quantity > item.quantity:
            return redirect(
                url_for(
                    "index",
                    sell_status="Not enough stock to complete the sale.",
                    sell_ok="false",
                )
            )
        update_item(item.id, item.name, item.price, item.quantity - quantity)
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO sales (shop_id, item_id, user_id, quantity, total)
                VALUES (?, ?, ?, ?, ?)
                """,
                (shop_id, item.id, user["id"], quantity, item.price * quantity),
            )
            connection.commit()
        return redirect(
            url_for(
                "index",
                sell_status="Sale recorded successfully.",
                sell_ok="true",
            )
        )
    return render_template("sell_form.html", items=items, user=user, shop_id=shop_id)


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        with get_connection() as connection:
            user = connection.execute(
                "SELECT id, username, role FROM users WHERE username = ? AND password = ?",
                (username, password),
            ).fetchone()
        if user is None:
            return render_template("login.html", error="Invalid credentials.")
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    return render_template("login.html", error=None)


@app.post("/logout")
def logout() -> str:
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = get_current_shop_id()
    if user["role"] == "admin":
        return render_template("dashboard_admin.html", user=user, shop_id=shop_id)
    return render_template("dashboard_worker.html", user=user, shop_id=shop_id)


@app.route("/shops", methods=["GET", "POST"])
def shops() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            with get_connection() as connection:
                connection.execute("INSERT OR IGNORE INTO shops (name) VALUES (?)", (name,))
                connection.commit()
    with get_connection() as connection:
        shops_list = connection.execute("SELECT id, name FROM shops ORDER BY name").fetchall()
    return render_template(
        "shops.html",
        user=user,
        shop_id=get_current_shop_id(),
        shops=shops_list,
    )


@app.post("/shops/select")
def select_shop() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = request.form.get("shop_id")
    set_current_shop(int(shop_id) if shop_id else None)
    return redirect(url_for("index"))


@app.route("/workers", methods=["GET", "POST"])
def workers() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    if not require_admin(user):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if username and password:
            with get_connection() as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, 'worker')",
                    (username, password),
                )
                connection.commit()
    with get_connection() as connection:
        workers_list = connection.execute(
            "SELECT id, username FROM users WHERE role = 'worker' ORDER BY username"
        ).fetchall()
    return render_template(
        "workers.html",
        user=user,
        shop_id=get_current_shop_id(),
        workers=workers_list,
    )


@app.route("/sales-report")
def sales_report() -> str:
    user = require_login()
    if user is None:
        return redirect(url_for("login"))
    shop_id = get_current_shop_id()
    if shop_id is None:
        return redirect(url_for("shops"))
    with get_connection() as connection:
        sales = connection.execute(
            """
            SELECT sales.id, items.name, sales.quantity, sales.total, sales.created_at, users.username
            FROM sales
            JOIN items ON items.id = sales.item_id
            JOIN users ON users.id = sales.user_id
            WHERE sales.shop_id = ?
            ORDER BY sales.created_at DESC
            """,
            (shop_id,),
        ).fetchall()
    return render_template(
        "sales_report.html",
        user=user,
        shop_id=shop_id,
        sales=sales,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
