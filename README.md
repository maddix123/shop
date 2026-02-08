# Shop Management System

A lightweight shop management system for tracking products, customers, and orders using SQLite.

## Features
- Initialize database schema
- Manage products (add, list, update stock, delete)
- Manage customers (add, list)
- Create orders with line items and automatic stock updates
- List orders with totals

## Requirements
- Python 3.10+

## Usage

Initialize the database:

```bash
python src/shop_management.py init-db
```

Add a product:

```bash
python src/shop_management.py add-product "Coffee Beans" 12.50 20
```

List products:

```bash
python src/shop_management.py list-products
```

Add a customer:

```bash
python src/shop_management.py add-customer "Jordan Lee" jordan@example.com
```

Create an order (format is `product_id:quantity`):

```bash
python src/shop_management.py create-order 1 1:2 3:1
```

List orders:

```bash
python src/shop_management.py list-orders
```

## Database
The SQLite database defaults to `shop.db` in the current directory. Override with `--db`.

```bash
python src/shop_management.py --db data/shop.db list-products
```
