-- Clean up existing tables if they exist
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- 1. Create Customers Table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    join_date TEXT NOT NULL, -- Format: YYYY-MM-DD
    country TEXT NOT NULL
);

-- 2. Create Products Table
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    price REAL NOT NULL,
    stock_quantity INTEGER NOT NULL
);

-- 3. Create Orders Table
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    order_date TEXT NOT NULL, -- Format: YYYY-MM-DD
    quantity INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

-- 4. Seed Customers
INSERT INTO customers (name, email, join_date, country) VALUES 
('Alice Johnson', 'alice@example.com', '2023-01-15', 'USA'),
('Bob Smith', 'bob@example.com', '2023-02-10', 'Canada'),
('Charlie Brown', 'charlie@example.com', '2023-03-05', 'UK'),
('Diana Prince', 'diana@example.com', '2023-05-20', 'USA'),
('Evan Wright', 'evan@example.com', '2023-06-12', 'Germany');

-- 5. Seed Products
INSERT INTO products (name, category, price, stock_quantity) VALUES 
('Wireless Headphones', 'Electronics', 99.99, 50),
('Gaming Mouse', 'Electronics', 49.99, 100),
('Mechanical Keyboard', 'Electronics', 129.50, 30),
('Running Shoes', 'Clothing', 79.00, 25),
('Yoga Mat', 'Fitness', 25.00, 60),
('Coffee Maker', 'Home', 85.00, 15);

-- 6. Seed Orders (Historical Data for Trends)
-- Q1 Orders
INSERT INTO orders (customer_id, product_id, order_date, quantity, total_amount) VALUES 
(1, 1, '2023-01-20', 1, 99.99), -- Alice bought Headphones
(2, 4, '2023-02-15', 2, 158.00), -- Bob bought 2 Shoes
(1, 6, '2023-03-10', 1, 85.00);  -- Alice bought Coffee Maker

-- Q2 Orders
INSERT INTO orders (customer_id, product_id, order_date, quantity, total_amount) VALUES 
(3, 2, '2023-04-05', 1, 49.99),  -- Charlie bought Mouse
(4, 3, '2023-05-25', 1, 129.50), -- Diana bought Keyboard
(5, 5, '2023-06-15', 2, 50.00);  -- Evan bought 2 Yoga Mats

-- Q3 Orders (Recent)
INSERT INTO orders (customer_id, product_id, order_date, quantity, total_amount) VALUES 
(1, 2, '2023-08-10', 1, 49.99), -- Alice bought Mouse
(2, 1, '2023-09-05', 1, 99.99), -- Bob bought Headphones
(4, 5, '2023-09-20', 1, 25.00); -- Diana bought Yoga Mat