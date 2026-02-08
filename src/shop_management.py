#!/usr/bin/env python3
"""Shop management system backed by SQLite."""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_DB_PATH = Path("shop.db")


@dataclass
class Product:
    id: int
    name: str
    price: float
    stock: int


@dataclass
class Customer:
    id: int
    name: str
    email: str


@dataclass
class OrderLine:
    product_id: int
    quantity: int


def connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )


def add_product(db_path: Path, name: str, price: float, stock: int) -> int:
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
            (name, price, stock),
        )
        return int(cursor.lastrowid)


def list_products(db_path: Path) -> list[Product]:
    with connect(db_path) as connection:
        rows = connection.execute("SELECT id, name, price, stock FROM products").fetchall()
    return [Product(**row) for row in rows]


def update_product_stock(db_path: Path, product_id: int, stock: int) -> None:
    with connect(db_path) as connection:
        connection.execute("UPDATE products SET stock = ? WHERE id = ?", (stock, product_id))


def delete_product(db_path: Path, product_id: int) -> None:
    with connect(db_path) as connection:
        connection.execute("DELETE FROM products WHERE id = ?", (product_id,))


def add_customer(db_path: Path, name: str, email: str) -> int:
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO customers (name, email) VALUES (?, ?)",
            (name, email),
        )
        return int(cursor.lastrowid)


def list_customers(db_path: Path) -> list[Customer]:
    with connect(db_path) as connection:
        rows = connection.execute("SELECT id, name, email FROM customers").fetchall()
    return [Customer(**row) for row in rows]


def _parse_order_lines(raw_lines: Sequence[str]) -> list[OrderLine]:
    parsed: list[OrderLine] = []
    for raw in raw_lines:
        if ":" not in raw:
            raise ValueError(f"Invalid order line '{raw}', expected product_id:quantity")
        product_id_str, quantity_str = raw.split(":", 1)
        parsed.append(OrderLine(product_id=int(product_id_str), quantity=int(quantity_str)))
    if not parsed:
        raise ValueError("At least one order line is required")
    return parsed


def create_order(db_path: Path, customer_id: int, lines: Iterable[OrderLine]) -> int:
    timestamp = dt.datetime.now(tz=dt.timezone.utc).isoformat()
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO orders (customer_id, created_at) VALUES (?, ?)",
            (customer_id, timestamp),
        )
        order_id = int(cursor.lastrowid)
        for line in lines:
            row = connection.execute(
                "SELECT price, stock FROM products WHERE id = ?",
                (line.product_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Product {line.product_id} not found")
            if row["stock"] < line.quantity:
                raise ValueError(
                    f"Insufficient stock for product {line.product_id}: {row['stock']} available"
                )
            connection.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) "
                "VALUES (?, ?, ?, ?)",
                (order_id, line.product_id, line.quantity, row["price"]),
            )
            connection.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ?",
                (line.quantity, line.product_id),
            )
    return order_id


def list_orders(db_path: Path) -> list[sqlite3.Row]:
    with connect(db_path) as connection:
        return connection.execute(
            """
            SELECT
                orders.id,
                orders.created_at,
                customers.name AS customer_name,
                SUM(order_items.quantity * order_items.price) AS total
            FROM orders
            JOIN customers ON customers.id = orders.customer_id
            JOIN order_items ON order_items.order_id = orders.id
            GROUP BY orders.id
            ORDER BY orders.created_at DESC
            """
        ).fetchall()


def format_products(products: Iterable[Product]) -> str:
    lines = ["ID  Name                 Price    Stock", "--  -------------------  -------  -----"]
    for product in products:
        lines.append(f"{product.id:<3} {product.name:<19} {product.price:<7.2f} {product.stock:<5}")
    return "\n".join(lines)


def format_customers(customers: Iterable[Customer]) -> str:
    lines = ["ID  Name                 Email", "--  -------------------  -------------------------"]
    for customer in customers:
        lines.append(f"{customer.id:<3} {customer.name:<19} {customer.email}")
    return "\n".join(lines)


def format_orders(orders: Iterable[sqlite3.Row]) -> str:
    lines = ["ID  Created At                 Customer            Total", "--  -------------------------  ------------------  -------"]
    for order in orders:
        lines.append(
            f"{order['id']:<3} {order['created_at']:<25} {order['customer_name']:<18} {order['total']:<7.2f}"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage shop inventory, customers, and orders.")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database (default: shop.db)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the database schema.")

    add_product_parser = subparsers.add_parser("add-product", help="Add a new product.")
    add_product_parser.add_argument("name")
    add_product_parser.add_argument("price", type=float)
    add_product_parser.add_argument("stock", type=int)

    subparsers.add_parser("list-products", help="List products.")

    update_stock_parser = subparsers.add_parser("update-stock", help="Update product stock.")
    update_stock_parser.add_argument("product_id", type=int)
    update_stock_parser.add_argument("stock", type=int)

    delete_product_parser = subparsers.add_parser("delete-product", help="Delete a product.")
    delete_product_parser.add_argument("product_id", type=int)

    add_customer_parser = subparsers.add_parser("add-customer", help="Add a customer.")
    add_customer_parser.add_argument("name")
    add_customer_parser.add_argument("email")

    subparsers.add_parser("list-customers", help="List customers.")

    create_order_parser = subparsers.add_parser("create-order", help="Create an order.")
    create_order_parser.add_argument("customer_id", type=int)
    create_order_parser.add_argument(
        "lines",
        nargs=argparse.REMAINDER,
        help="Order lines formatted as product_id:quantity",
    )

    subparsers.add_parser("list-orders", help="List orders with totals.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        init_db(args.db)
        print(f"Initialized database at {args.db}")
        return

    if args.command == "add-product":
        product_id = add_product(args.db, args.name, args.price, args.stock)
        print(f"Added product {product_id}")
        return

    if args.command == "list-products":
        print(format_products(list_products(args.db)))
        return

    if args.command == "update-stock":
        update_product_stock(args.db, args.product_id, args.stock)
        print(f"Updated stock for product {args.product_id}")
        return

    if args.command == "delete-product":
        delete_product(args.db, args.product_id)
        print(f"Deleted product {args.product_id}")
        return

    if args.command == "add-customer":
        customer_id = add_customer(args.db, args.name, args.email)
        print(f"Added customer {customer_id}")
        return

    if args.command == "list-customers":
        print(format_customers(list_customers(args.db)))
        return

    if args.command == "create-order":
        lines = _parse_order_lines(args.lines)
        order_id = create_order(args.db, args.customer_id, lines)
        print(f"Created order {order_id}")
        return

    if args.command == "list-orders":
        print(format_orders(list_orders(args.db)))
        return


if __name__ == "__main__":
    main()
