# -*- coding: utf-8 -*-
"""
Coffee House POS — Streamlit + SQLite
"""

import sqlite3
import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date

try:
    import qrcode
    from PIL import Image
    HAS_QR = True
except ImportError:
    HAS_QR = False

# ==================== PATH ====================
APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "coffee_shop.db"
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

QR_FILES = {
    "ABA": "aba_qr.png",
    "Wing": "wing_qr.png",
    "ACLEDA": "acleda_qr.png",
    "Canadia": "canadia_qr.png",
    "Other": "other_qr.png",
}

# ==================== DATABASE ====================
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """បង្កើតតារាងប្រសិនបើមិនទាន់មាន"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            name_kh TEXT,
            category TEXT,
            price REAL,
            stock INTEGER,
            unit TEXT,
            active TEXT DEFAULT 'Yes'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            date TEXT,
            time TEXT,
            product_id INTEGER,
            product_name TEXT,
            qty INTEGER,
            unit_price REAL,
            total REAL,
            payment TEXT,
            staff TEXT
        )
    """)

    # បញ្ចូលទិន្នន័យគំរូប្រសិនបើតារាងទទេ
    cur.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        sample_products = [
            (1, "Espresso", "អេស្ព្រេសូ", "Coffee", 1.50, 100, "cup", "Yes"),
            (2, "Cappuccino", "កាពុចីណូ", "Coffee", 2.00, 80, "cup", "Yes"),
            (3, "Latte", "ឡាតេ", "Coffee", 2.25, 90, "cup", "Yes"),
            (4, "Americano", "អាមេរិកាណូ", "Coffee", 1.75, 70, "cup", "Yes"),
            (5, "Green Tea", "តែបៃតង", "Tea", 1.50, 60, "cup", "Yes"),
            (6, "Chocolate", "សូកូឡា", "Other", 2.50, 50, "cup", "Yes"),
        ]
        cur.executemany(
            "INSERT INTO products (id, name, name_kh, category, price, stock, unit, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            sample_products
        )

    conn.commit()
    conn.close()

# ==================== DATA FUNCTIONS ====================
def load_products(include_inactive=False):
    conn = get_connection()
    if include_inactive:
        rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    else:
        rows = conn.execute("SELECT * FROM products WHERE active = 'Yes' ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def load_orders():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM orders ORDER BY order_id DESC, id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_next_order_id():
    conn = get_connection()
    result = conn.execute("SELECT MAX(order_id) FROM orders").fetchone()[0]
    conn.close()
    return (result or 1000) + 1

def save_order(lines):
    """lines = list of tuples/lists matching order columns"""
    conn = get_connection()
    cur = conn.cursor()

    for line in lines:
        cur.execute("""
            INSERT INTO orders (order_id, date, time, product_id, product_name, qty, unit_price, total, payment, staff)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, line)

        # បន្ថយស្តុក
        pid, qty = line[3], line[5]
        cur.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?", (qty, pid))

    conn.commit()
    conn.close()

def update_stock(product_id, new_stock):
    conn = get_connection()
    conn.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))
    conn.commit()
    conn.close()

def add_product(name, name_kh, category, price, stock, unit):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(id) FROM products")
    max_id = cur.fetchone()[0] or 0
    new_id = max_id + 1
    cur.execute("""
        INSERT INTO products (id, name, name_kh, category, price, stock, unit, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Yes')
    """, (new_id, name, name_kh, category, price, stock, unit))
    conn.commit()
    conn.close()
    return new_id

def update_product(product_id, name, name_kh, category, price, stock, unit):
    conn = get_connection()
    conn.execute("""
        UPDATE products
        SET name=?, name_kh=?, category=?, price=?, stock=?, unit=?
        WHERE id=?
    """, (name, name_kh, category, price, stock, unit, product_id))
    conn.commit()
    conn.close()

def soft_delete_product(product_id):
    conn = get_connection()
    conn.execute("UPDATE products SET active = 'No' WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def restore_product(product_id):
    conn = get_connection()
    conn.execute("UPDATE products SET active = 'Yes' WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def generate_qr(data: str, size=200):
    if not HAS_QR:
        return None
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1a1a6c", back_color="white")
    return img.resize((size, size))

def get_qr_image(order_id, total, payment):
    filename = QR_FILES.get(payment)
    if filename:
        for folder in [DATA_DIR, APP_DIR]:
            path = folder / filename
            if path.exists():
                return str(path)
    data = f"COFFEE HOUSE\nOrder #{order_id}\nTotal: ${total:.2f}\nPayment: {payment}"
    return generate_qr(data)

def check_available_qrs():
    available = {}
    for pay, fname in QR_FILES.items():
        found = any((folder / fname).exists() for folder in [DATA_DIR, APP_DIR])
        available[pay] = found
    return available

# ==================== INIT ====================
init_db()  # បង្កើត DB + ទិន្នន័យគំរូ

# ==================== SESSION STATE ====================
if "cart" not in st.session_state:
    st.session_state.cart = {}
if "last_receipt" not in st.session_state:
    st.session_state.last_receipt = None

# ==================== PAGE CONFIG + CSS ====================
st.set_page_config(page_title="Coffee House POS", page_icon="☕", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Khmer:wght@400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap');
    html, body, [class*="css"], .stApp { font-family: 'Poppins', 'Noto Sans Khmer', sans-serif !important; }
    .stApp { background: linear-gradient(135deg, #faf6f1 0%, #f5efe6 100%); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #4a3728 0%, #3a2a1f 100%) !important; }
    [data-testid="stSidebar"] * { color: #f5efe6 !important; }
    [data-testid="stSidebar"] .stRadio label { font-size: 1.15rem !important; padding: 10px 8px !important; }
    div[data-testid="stMetric"] { background: white; border-radius: 16px; padding: 16px; border: 1px solid #e8dfd4; }
    .stButton > button { background: linear-gradient(135deg, #6F4E37, #5a3e2b) !important; color: white !important; border-radius: 12px !important; border: none !important; }
    .product-card { background: white; border-radius: 14px; padding: 14px; border: 1px solid #e8dfd4; margin-bottom: 10px; }
    .low-stock { background: #fff8f0; border-left: 5px solid #d35400; padding: 10px 14px; border-radius: 8px; margin: 6px 0; }
    .receipt-overlay { background: white; border: 2px dashed #6F4E37; border-radius: 14px; padding: 20px; font-family: 'Courier New', monospace; }
</style>
""", unsafe_allow_html=True)

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("### ☕ Coffee House")
    st.caption("POS System (SQLite)")
    st.markdown("---")
    menu = st.radio("ម៉ឺនុយ", [
        "🏠 ទំព័រដើម",
        "🛒 លក់ថ្មី",
        "📦 ផលិតផល",
        "📋 ប្រវត្តិលក់",
        "📊 របាយការណ៍",
        "⚙️ QR Code",
    ], label_visibility="collapsed")

# ==================== PAGES ====================

if menu == "🏠 ទំព័រដើម":
    st.markdown("## 🏠 ទំព័រដើម")
    products = load_products()
    orders = load_orders()
    today = date.today().strftime("%Y-%m-%d")
    today_orders = [o for o in orders if o["date"] == today]
    revenue = sum(o["total"] for o in today_orders)
    order_ids = set(o["order_id"] for o in today_orders)
    low = [p for p in products if p["stock"] <= 20]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 ចំណូលថ្ងៃនេះ", f"${revenue:.2f}")
    c2.metric("🧾 Order ថ្ងៃនេះ", len(order_ids))
    c3.metric("📦 ផលិតផល", len(products))
    c4.metric("⚠️ ស្តុកទាប", len(low))

    st.markdown("### ⚠️ ផលិតផលស្តុកទាប")
    if low:
        for p in low:
            st.markdown(f"<div class='low-stock'><b>{p['name']}</b> ({p['name_kh']}) — ស្តុក: <b style='color:#e67e22'>{p['stock']} {p['unit']}</b></div>", unsafe_allow_html=True)
    else:
        st.success("ស្តុកគ្រប់គ្រាន់ ✅")

elif menu == "🛒 លក់ថ្មី":
    st.markdown("## 🛒 លក់ថ្មី")

    if st.session_state.last_receipt:
        rec = st.session_state.last_receipt
        items_text = ""
        for it in rec["items"]:
            items_text += f"{it['name']}\n  {it['qty']} x ${it['price']:.2f} = ${it['subtotal']:.2f}\n"
        receipt_text = f"""====================================
     COFFEE HOUSE កាហ្វេហោស
        *** RECEIPT / វិក័យប័ត្រ ***
====================================
Order # : {rec['order_id']}
Date    : {rec['date_time']}
Staff   : {rec['staff']}
Payment : {rec['payment']}
------------------------------------
{items_text}------------------------------------
TOTAL              ${rec['total']:.2f}
====================================
     សូមអរគុណ!  Thank you!
===================================="""

        col1, col2 = st.columns([1.4, 1])
        with col1:
            st.markdown("### 🧾 វិក័យប័ត្រ")
            st.markdown(f"<div class='receipt-overlay'><pre>{receipt_text}</pre></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"### QR — {rec['payment']}")
            qr = get_qr_image(rec["order_id"], rec["total"], rec["payment"])
            if qr:
                st.image(qr, width=220)
            st.download_button("💾 ទាញយកវិក័យប័ត្រ", receipt_text, f"receipt_{rec['order_id']}.txt")
            if st.button("បិទ / បន្តលក់", type="primary"):
                st.session_state.last_receipt = None
                st.rerun()
        st.success(f"✅ លក់ជោគជ័យ! Order #{rec['order_id']} | ${rec['total']:.2f}")
        st.markdown("---")

    products = load_products()
    left, right = st.columns([1.6, 1])

    with left:
        st.subheader("ជ្រើសរើសផលិតផល")
        cats = ["ទាំងអស់"] + sorted({p["category"] for p in products})
        selected_cat = st.selectbox("ប្រភេទ", cats)
        filtered = products if selected_cat == "ទាំងអស់" else [p for p in products if p["category"] == selected_cat]

        cols = st.columns(3)
        for i, p in enumerate(filtered):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="product-card">
                    <b>{p['name']}</b><br>
                    <small style="color:#8b7355">{p['name_kh']}</small><br>
                    <span style="color:#6F4E37; font-size:1.2rem; font-weight:700">${p['price']:.2f}</span><br>
                    <small>ស្តុក: {p['stock']} {p['unit']}</small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("➕ បន្ថែម", key=f"add_{p['id']}", use_container_width=True):
                    if p["stock"] <= 0:
                        st.warning("អស់ស្តុក")
                    else:
                        if p["id"] in st.session_state.cart:
                            st.session_state.cart[p["id"]]["qty"] += 1
                        else:
                            st.session_state.cart[p["id"]] = {"name": p["name"], "price": p["price"], "qty": 1}
                        st.rerun()

    with right:
        st.subheader("🛒 កន្ត្រក់")
        if not st.session_state.cart:
            st.info("កន្ត្រក់ទទេ")
        else:
            total = 0
            for pid, item in st.session_state.cart.items():
                sub = item["price"] * item["qty"]
                total += sub
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['name']}**")
                c2.write(f"x{item['qty']}")
                c3.write(f"${sub:.2f}")

            st.markdown(f"### សរុប: **${total:.2f}**")
            payment = st.selectbox("វិធីបង់ប្រាក់", ["Cash", "ABA", "Wing", "ACLEDA", "Canadia", "Other"])
            staff = st.selectbox("បុគ្គលិក", ["Sokha", "Dara", "Pisey", "Other"])

            b1, b2 = st.columns(2)
            with b1:
                if st.button("✅ បញ្ជាក់ការលក់", type="primary", use_container_width=True):
                    now = datetime.now()
                    order_id = get_next_order_id()
                    lines = []
                    items = []
                    total = 0.0
                    for pid, item in st.session_state.cart.items():
                        sub = round(item["price"] * item["qty"], 2)
                        total += sub
                        lines.append((
                            order_id, now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
                            pid, item["name"], item["qty"], item["price"], sub, payment, staff
                        ))
                        items.append({"name": item["name"], "qty": item["qty"], "price": item["price"], "subtotal": sub})
                    try:
                        save_order(lines)
                        st.session_state.last_receipt = {
                            "order_id": order_id, "date_time": now.strftime("%Y-%m-%d %H:%M"),
                            "staff": staff, "payment": payment, "total": total, "items": items
                        }
                        st.session_state.cart = {}
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with b2:
                if st.button("🗑️ សម្អាត", use_container_width=True):
                    st.session_state.cart = {}
                    st.rerun()

elif menu == "📦 ផលិតផល":
    st.markdown("## 📦 គ្រប់គ្រងផលិតផល")
    tab1, tab2, tab3 = st.tabs(["📋 បញ្ជី", "✏️ កែប្រែ / លុប", "➕ បន្ថែមថ្មី"])

    with tab1:
        products = load_products()
        if products:
            df = pd.DataFrame(products)[["id", "name", "name_kh", "category", "price", "stock", "unit"]]
            st.dataframe(df.style.format({"price": "${:.2f}"}), use_container_width=True, hide_index=True)
        else:
            st.info("មិនមានផលិតផល")

    with tab2:
        products = load_products()
        inactive = [p for p in load_products(include_inactive=True) if p["active"] != "Yes"]

        if products:
            options = {f"{p['id']} - {p['name']}": p for p in products}
            selected = options[st.selectbox("ជ្រើសរើសផលិតផល", list(options.keys()))]

            with st.form("edit_form"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Name", value=selected["name"])
                name_kh = c1.text_input("ឈ្មោះខ្មែរ", value=selected["name_kh"])
                category = c1.text_input("Category", value=selected["category"])
                price = c2.number_input("Price", value=float(selected["price"]), step=0.25)
                stock = c2.number_input("Stock", value=int(selected["stock"]), step=1)
                unit = c2.text_input("Unit", value=selected["unit"])

                b1, b2 = st.columns(2)
                if b1.form_submit_button("💾 រក្សាទុក", use_container_width=True):
                    update_product(selected["id"], name, name_kh, category, price, stock, unit)
                    st.success("បានកែប្រែ!")
                    st.rerun()
                if b2.form_submit_button("🗑️ លុប", use_container_width=True):
                    soft_delete_product(selected["id"])
                    st.success("បានលុប!")
                    st.rerun()

        if inactive:
            st.markdown("---")
            st.subheader("♻️ ផលិតផលដែលបានលុប")
            for p in inactive:
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{p['name']}** ({p['name_kh']})")
                if c2.button("ស្តារ", key=f"res_{p['id']}"):
                    restore_product(p["id"])
                    st.rerun()

    with tab3:
        with st.form("add_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name (EN)*")
            name_kh = c1.text_input("ឈ្មោះខ្មែរ")
            category = c1.text_input("Category", value="Coffee")
            price = c2.number_input("Price", value=1.5, step=0.25)
            stock = c2.number_input("Stock", value=50, step=1)
            unit = c2.text_input("Unit", value="cup")
            if st.form_submit_button("រក្សាទុក", use_container_width=True):
                if name.strip():
                    add_product(name.strip(), name_kh.strip(), category or "Other", price, stock, unit or "cup")
                    st.success("បានបន្ថែម!")
                    st.rerun()
                else:
                    st.error("ត្រូវការឈ្មោះ")

elif menu == "📋 ប្រវត្តិលក់":
    st.markdown("## 📋 ប្រវត្តិការលក់")
    orders = load_orders()
    if not orders:
        st.info("មិនទាន់មានទិន្នន័យ")
    else:
        df = pd.DataFrame(orders)[["order_id", "date", "time", "product_name", "qty", "total", "payment", "staff"]]
        st.dataframe(df.style.format({"total": "${:.2f}"}), use_container_width=True, hide_index=True)
        st.markdown(f"**សរុប: ${sum(o['total'] for o in orders):.2f}** | ចំនួន: {len(orders)}")

elif menu == "📊 របាយការណ៍":
    st.markdown("## 📊 របាយការណ៍")
    orders = load_orders()
    if not orders:
        st.info("មិនទាន់មានទិន្នន័យ")
    else:
        daily = {}
        for o in orders:
            daily[o["date"]] = daily.get(o["date"], 0) + o["total"]
        daily_df = pd.DataFrame([{"Date": k, "Revenue": v} for k, v in sorted(daily.items(), reverse=True)])
        st.subheader("💰 ចំណូលប្រចាំថ្ងៃ")
        st.dataframe(daily_df.style.format({"Revenue": "${:.2f}"}), use_container_width=True, hide_index=True)
        st.bar_chart(daily_df.set_index("Date")["Revenue"])

        prod = {}
        for o in orders:
            if o["product_name"] not in prod:
                prod[o["product_name"]] = {"qty": 0, "rev": 0}
            prod[o["product_name"]]["qty"] += o["qty"]
            prod[o["product_name"]]["rev"] += o["total"]
        prod_df = pd.DataFrame([{"Product": k, "Qty": v["qty"], "Revenue": v["rev"]} for k, v in sorted(prod.items(), key=lambda x: -x[1]["qty"])])
        st.subheader("🏆 ផលិតផលលក់ដាច់")
        st.dataframe(prod_df.style.format({"Revenue": "${:.2f}"}), use_container_width=True, hide_index=True)

elif menu == "⚙️ QR Code":
    st.markdown("## ⚙️ គ្រប់គ្រង QR Code")
    st.info("ដាក់ file QR (aba_qr.png, wing_qr.png...) ក្នុង folder `data/` ឬ root")
    avail = check_available_qrs()
    data = [{"វិធីបង់ប្រាក់": k, "ឯកសារ": v, "ស្ថានភាព": "✅ មាន" if avail[k] else "❌ មិនមាន"} for k, v in QR_FILES.items()]
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    cols = st.columns(3)
    i = 0
    for pay, fname in QR_FILES.items():
        for folder in [DATA_DIR, APP_DIR]:
            path = folder / fname
            if path.exists():
                with cols[i % 3]:
                    st.markdown(f"**{pay}**")
                    st.image(str(path), width=160)
                i += 1
                break