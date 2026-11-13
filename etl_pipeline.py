import pandas as pd
import sqlite3

file1_path = 'test.csv'
file2_path = 'test2.csv'
db_path = 'etl.db'

# Extract
raw = pd.read_csv(file1_path)
customers = pd.read_csv(file2_path)
print(f'строк в выгрузке1: {len(raw)}')
print(f'строк в выгрузке2: {len(customers)}')

# Transform
df = raw.copy()
df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
salary_med = df['amount'].median()
df['amount'] = df['amount'].fillna(salary_med).astype(float)

df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(1).astype(int)
df['order_date'] = pd.to_datetime(df['order_date'], format="%Y-%m-%d", errors='coerce')

customers['customer_id'] = customers['customer_id'].str.strip().str.lower()
df['customer_id'] = df['customer_id'].str.strip().str.lower()

before = len(df)
df = df.dropna(subset=['order_date', 'customer_id'])
customers = customers.dropna(subset=['customer_id'])
print(f'дропнуто строк: без даты/идентификатора {before - len(df)}')

df['full_name'] = df['full_name'].fillna('No name info').str.strip().str.title()
df['product'] = df['product'].fillna('No product info').str.strip().str.lower()

before_dup_drops = len(df)
df = df.drop_duplicates(subset=['order_id'], keep='last')
customers = customers.drop_duplicates(subset=['customer_id'])
print(f'дропнуто дублей: {before_dup_drops - len(df)}')

df['revenue'] = df['amount'] * df['quantity']
df['month'] = df['order_date'].dt.to_period('M').astype(str)

# на всякий случай вторая проверка
b4_merge = len(df)
df = pd.merge(df, customers, on='customer_id', how='left')
assert len(df) == b4_merge, f'Ошибка! Мердж размножил строки: {b4_merge} стало {len(df)}'
print('Проверка успешна!')

df['region'] = df['region'].fillna('Unknown')

# Load
with sqlite3.connect(db_path) as conn:
    df.to_sql('cleaned_orders', conn, if_exists='replace', index=False)
    print('Очищенные данные загружены.')

with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS mart_monthly_sales")
    cursor.execute("DROP TABLE IF EXISTS mart_top_customers")
    cursor.execute("DROP TABLE IF EXISTS mart_products")

    cursor.execute("""
    CREATE TABLE mart_monthly_sales AS
    SELECT month, region,
    COUNT(DISTINCT order_id) AS orders,
    SUM(revenue) AS total_revenue
    FROM cleaned_orders
    GROUP BY month, region;""")

    cursor.execute("""
    CREATE TABLE mart_top_customers AS
    SELECT customer_id, full_name,
    SUM(revenue) AS total_spent,
    COUNT(DISTINCT order_id) AS order_count
    FROM cleaned_orders
    GROUP BY customer_id
    ORDER BY total_spent DESC
    LIMIT 5;""")

    cursor.execute("""
    CREATE TABLE mart_products AS
    SELECT product,
    SUM(revenue) AS total_revenue_by_product,
    SUM(quantity) AS total_quantity_sold
    FROM cleaned_orders
    GROUP BY product;""")

    conn.commit()
    print("SQL-витрины успешно созданы!")

with sqlite3.connect(db_path) as conn:
    query = "SELECT * FROM mart_monthly_sales ORDER BY month"
    check_df = pd.read_sql(query, conn)
    print("Данные из SQL-витрины(mart_monthly_sales)")
    print(check_df)