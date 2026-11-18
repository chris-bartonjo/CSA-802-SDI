-- Customer Data System (the relational source). Loaded into sources/customers_source.db by integrate.py.
-- Rows 6 and 9 contain deliberate problems for the validation step to catch.
CREATE TABLE crm_customers (
    cust_id    INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name  TEXT,
    address    TEXT,
    city       TEXT,
    phone      TEXT,
    email      TEXT
);
INSERT INTO crm_customers VALUES
 (101, 'Amina',  'Wanjiru',  '12 Moi Avenue',      'Nairobi', '0712 345 678',   'amina.wanjiru@example.com'),
 (102, 'Brian',  'Otieno',   '4 Oginga Odinga St', 'Kisumu',  '+254722111222',  'brian.otieno@example.com'),
 (103, 'Cynthia','Mutua',    '88 Nkrumah Road',    'Mombasa', '0733-555-010',   'cynthia.mutua@example.com'),
 (104, 'David',  'Kiprop',   '3 Uganda Road',      'Eldoret', '0700 999 111',   'david.kiprop@example.com'),
 (105, 'Esther', 'Njeri',    '19 Kenyatta Avenue', 'Nakuru',  '0711 222 333',   NULL),
 (106, '  amina','WANJIRU ', '12 Moi Avenue',      'Nairobi', '0712345678',     'Amina.Wanjiru@Example.com'),
 (107, 'Felix',  'Mwangi',   '7 Kimathi Street',   'Nyeri',   '12345',          'felix.mwangi@example.com'),
 (108, 'Grace',  'Achieng',  '21 Ngong Road',      'Nairobi', '0798 765 432',   'grace.achieng@example.com'),
 (109, NULL,     'Unknown',  NULL,                 NULL,      NULL,             'no-name@example.com');
