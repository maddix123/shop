from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass

from flask import Flask, redirect, render_template, request, url_for


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
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER NOT NULL
            )
            """
        )


def fetch_items() -> list[Item]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, price, quantity FROM items ORDER BY id DESC"
        ).fetchall()
    return [Item(**row) for row in rows]


def fetch_item(item_id: int) -> Item | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, price, quantity FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
    if row is None:
        return None
    return Item(**row)


def create_item(name: str, price: float, quantity: int) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO items (name, price, quantity) VALUES (?, ?, ?)",
            (name, price, quantity),
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
init_db()


@app.route("/")
def index() -> str:
    return render_template("index.html", items=fetch_items())


@app.route("/item/new", methods=["GET", "POST"])
def new_item() -> str:
    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        create_item(name, price, quantity)
        return redirect(url_for("index"))
    return render_template("item_form.html", item=None)


@app.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
def edit_item(item_id: int) -> str:
    item = fetch_item(item_id)
    if item is None:
        return redirect(url_for("index"))
    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"])
        quantity = int(request.form["quantity"])
        update_item(item_id, name, price, quantity)
        return redirect(url_for("index"))
    return render_template("item_form.html", item=item)


@app.post("/item/<int:item_id>/delete")
def remove_item(item_id: int) -> str:
    delete_item(item_id)
    return redirect(url_for("index"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
