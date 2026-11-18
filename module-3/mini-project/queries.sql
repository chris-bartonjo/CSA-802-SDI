-- Queries against central.db. Each block starts with "-- name:"; run_queries.py executes them in order.
-- Order value = quantity x current product price (the schema keeps no historical price).

-- name: Q1 Customer details with the products they ordered
SELECT c.customer_id,
       c.first_name || ' ' || c.last_name AS customer,
       o.order_id,
       o.order_date,
       p.name     AS product,
       o.quantity,
       p.price
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN products  p ON p.product_id  = o.product_id
ORDER BY c.customer_id, o.order_date;

-- name: Q2 Total value of orders per customer
SELECT c.customer_id,
       c.first_name || ' ' || c.last_name AS customer,
       COUNT(o.order_id)                  AS orders,
       COALESCE(SUM(o.quantity * p.price), 0) AS total_value
FROM customers c
LEFT JOIN orders   o ON o.customer_id = c.customer_id
LEFT JOIN products p ON p.product_id  = o.product_id
GROUP BY c.customer_id
ORDER BY total_value DESC;

-- name: Q3 Products priced between KES 1,000 and KES 5,000
SELECT product_id, name, price, stock_qty
FROM products
WHERE price BETWEEN 1000 AND 5000
ORDER BY price;

-- name: Q4 Customers with an order worth more than KES 10,000
SELECT c.customer_id,
       c.first_name || ' ' || c.last_name AS customer,
       o.order_id,
       p.name                    AS product,
       o.quantity * p.price      AS order_value
FROM orders o
JOIN customers c ON c.customer_id = o.customer_id
JOIN products  p ON p.product_id  = o.product_id
WHERE o.quantity * p.price > 10000
ORDER BY order_value DESC;

-- name: R1 Report of total orders and revenue per product
SELECT p.product_id,
       p.name,
       COUNT(o.order_id)                    AS total_orders,
       COALESCE(SUM(o.quantity), 0)         AS units_sold,
       COALESCE(SUM(o.quantity * p.price), 0) AS revenue
FROM products p
LEFT JOIN orders o ON o.product_id = p.product_id
GROUP BY p.product_id
ORDER BY revenue DESC;
