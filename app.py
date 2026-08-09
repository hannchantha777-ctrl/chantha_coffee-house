# -*- coding: utf-8 -*-
"""
Coffee Chantha — Streamlit + Supabase (PostgreSQL Standard)
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from sqlalchemy import create_engine, text

try:
    import qrcode
    from PIL import Image
    HAS_QR = True
except ImportError:
    HAS_QR = False

# ==================== PAGE CONFIG (MUST BE FIRST) ====================
st.set_page_config(
    page_title="Coffee Chantha",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== PATH & CONSTANTS ====================
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Exchange rate
USD_TO_KHR = 4100

QR_FILES = {
    "ABA": "aba_qr.png",
    "Wing": "wing_qr.png",
    "ACLEDA": "acleda_qr.png",
    "Canadia": "canadia_qr.png",
    "Other": "other_qr.png",
}

BANK_LOGOS = {
    "ABA": "🏦 ABA",
    "Wing": "🪽 Wing",
    "ACLEDA": "🏛️ ACLEDA",
    "Canadia": "🍁 Canadia",
    "Cash": "💵 Cash",
    "Other": "💳 Other",
}

PRODUCT_ICONS = {
    "Espresso": "☕",
    "Cappuccino": "☕",
    "Latte": "🥛",
    "Americano": "☕",
    "Green Tea": "🍵",
    "Chocolate": "🍫",
    "Coffee": "☕",
    "Tea": "🍵",
    "Other": "🧁",
}

def get_product_icon(name, category):
    if name in PRODUCT_ICONS:
        return PRODUCT_ICONS[name]
    return PRODUCT_ICONS.get(category, "☕")

# ==================== POSTGRESQL / SUPABASE DATABASE ====================
@st.cache_resource
def get_db_engine():
    """បង្កើត Connection Engine ទៅកាន់ Supabase PostgreSQL"""
    try:
        db_url = st.secrets["postgres"]["url"]
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 15}
        )
        # សាកល្បងភ្ជាប់ភ្លាម
        with engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        return engine
    except KeyError as e:
        st.error("❌ មិនឃើញ key ក្នុង secrets.toml")
        st.code('''[postgres]
url = "postgresql://postgres:Chantha%4003031991@db.oniprrzdrodlfloddoce.supabase.co:5432/postgres"''')
        st.stop()
    except Exception as e:
        st.error(f"❌ មិនអាចតភ្ជាប់ Database បានទេ:\n\n{type(e).__name__}: {e}")
        st.info("ពិនិត្យ៖ Password, Internet, និង Supabase project status")
        st.stop()


def init_db():
    """បង្កើត Table ប្រសិនបើមិនទាន់មាន"""
    engine = get_db_engine()          # ← ត្រូវយក engine មកសិន
    with engine.begin() as conn:      # ← ត្រូវ .begin() មិនមែន with engine ផ្ទាល់
        # បង្កើត Table Products
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                name_kh VARCHAR(255),
                category VARCHAR(100),
                price NUMERIC(10, 2),
                stock INT,
                unit VARCHAR(50),
                active VARCHAR(10) DEFAULT 'Yes'
            );
        """))
        
        # បង្កើត Table Orders
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                order_id INT,
                date VARCHAR(20),
                time VARCHAR(20),
                product_id INT,
                product_name VARCHAR(255),
                qty INT,
                unit_price NUMERIC(10, 2),
                total NUMERIC(10, 2),
                payment VARCHAR(50),
                staff VARCHAR(100)
            );
        """))
        
        # បញ្ចូលទិន្នន័យគំរូប្រសិនបើ Table នៅទទេ
        result = conn.execute(text("SELECT COUNT(*) FROM products;")).fetchone()
        if result[0] == 0:
            sample = [
                {"id": 1, "name": "Espresso", "name_kh": "អេស្ព្រេសូ", "category": "Coffee", "price": 1.50, "stock": 100, "unit": "cup", "active": "Yes"},
                {"id": 2, "name": "Cappuccino", "name_kh": "កាពុចីណូ", "category": "Coffee", "price": 2.00, "stock": 80, "unit": "cup", "active": "Yes"},
                {"id": 3, "name": "Latte", "name_kh": "ឡាតេ", "category": "Coffee", "price": 2.25, "stock": 90, "unit": "cup", "active": "Yes"},
                {"id": 4, "name": "Americano", "name_kh": "អាមេរិកាណូ", "category": "Coffee", "price": 1.75, "stock": 70, "unit": "cup", "active": "Yes"},
                {"id": 5, "name": "Green Tea", "name_kh": "តែបៃតង", "category": "Tea", "price": 1.50, "stock": 60, "unit": "cup", "active": "Yes"},
                {"id": 6, "name": "Chocolate", "name_kh": "សូកូឡា", "category": "Other", "price": 2.50, "stock": 50, "unit": "cup", "active": "Yes"},
            ]
            for p in sample:
                conn.execute(text("""
                    INSERT INTO products (id, name, name_kh, category, price, stock, unit, active)
                    VALUES (:id, :name, :name_kh, :category, :price, :stock, :unit, :active)
                """), p)
def load_products(include_inactive=False):
    engine = get_db_engine()
    q = "SELECT * FROM products ORDER BY id" if include_inactive else "SELECT * FROM products WHERE active = 'Yes' ORDER BY id"
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
        return df.to_dict(orient="records")

def load_orders():
    engine = get_db_engine()
    q = "SELECT * FROM orders ORDER BY order_id DESC, id DESC"
    with engine.connect() as conn:
        df = pd.read_sql(q, conn)
        return df.to_dict(orient="records")

def get_next_order_id():
    engine = get_db_engine()
    with engine.connect() as conn:
        res = conn.execute(text("SELECT MAX(order_id) FROM orders;")).fetchone()[0]
        return (res or 1000) + 1

def save_order(lines):
    engine = get_db_engine()
    with engine.begin() as conn:
        for line in lines:
            conn.execute(text("""
                INSERT INTO orders (order_id, date, time, product_id, product_name, qty, unit_price, total, payment, staff)
                VALUES (:order_id, :date, :time, :product_id, :product_name, :qty, :unit_price, :total, :payment, :staff)
            """), {
                "order_id": line[0], "date": line[1], "time": line[2],
                "product_id": line[3], "product_name": line[4], "qty": line[5],
                "unit_price": line[6], "total": line[7], "payment": line[8], "staff": line[9]
            })
            conn.execute(text("""
                UPDATE products SET stock = GREATEST(0, stock - :qty) WHERE id = :id
            """), {"qty": line[5], "id": line[3]})

def update_product(product_id, name, name_kh, category, price, stock, unit):
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE products SET name=:name, name_kh=:name_kh, category=:category, price=:price, stock=:stock, unit=:unit WHERE id=:id
        """), {"name": name, "name_kh": name_kh, "category": category, "price": price, "stock": stock, "unit": unit, "id": product_id})

def soft_delete_product(product_id):
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET active = 'No' WHERE id = :id"), {"id": product_id})

def restore_product(product_id):
    engine = get_db_engine()
    with engine.begin() as conn:
        conn.execute(text("UPDATE products SET active = 'Yes' WHERE id = :id"), {"id": product_id})

def add_product(name, name_kh, category, price, stock, unit):
    engine = get_db_engine()
    with engine.begin() as conn:
        res = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM products;")).fetchone()[0]
        conn.execute(text("""
            INSERT INTO products (id, name, name_kh, category, price, stock, unit, active)
            VALUES (:id, :name, :name_kh, :category, :price, :stock, :unit, 'Yes')
        """), {"id": res, "name": name, "name_kh": name_kh, "category": category, "price": price, "stock": stock, "unit": unit})
        return res

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

# ==================== INIT ====================
init_db()

if "cart" not in st.session_state:
    st.session_state.cart = {}
if "last_receipt" not in st.session_state:
    st.session_state.last_receipt = None
if "confirm_action" not in st.session_state:
    st.session_state.confirm_action = None

# ==================== CSS ====================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Khmer:wght@400;500;600;700&family=Poppins:wght@400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Poppins', 'Noto Sans Khmer', sans-serif !important;
}
.stApp { background: linear-gradient(160deg, #faf6f1 0%, #f0e6d8 100%); }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #3c2a1e 0%, #2a1d14 100%) !important;
}
[data-testid="stSidebar"] * { color: #f5efe6 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-size: 1.12rem !important;
    padding: 12px 14px !important;
    margin: 4px 0 !important;
    border-radius: 12px !important;
    transition: all 0.2s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.12) !important;
}

/* Metrics */
div[data-testid="stMetric"] {
    background: white;
    border-radius: 18px;
    padding: 18px;
    border: 1px solid #e8dfd4;
    box-shadow: 0 4px 14px rgba(74,55,40,0.07);
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #6F4E37, #5a3e2b) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    transition: all 0.2s;
}
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(111,78,55,0.3) !important;
}

/* Product Card */
.product-card {
    background: white;
    border-radius: 18px;
    padding: 18px 14px;
    border: 1px solid #e8dfd4;
    text-align: center;
    box-shadow: 0 4px 12px rgba(74,55,40,0.06);
    transition: all 0.25s;
    height: 100%;
}
.product-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 24px rgba(74,55,40,0.12);
}
.product-icon {
    font-size: 2.8rem;
    line-height: 1.2;
    margin-bottom: 6px;
}

/* Receipt */
.receipt-box {
    background: #fffef8;
    border: 2px dashed #6F4E37;
    border-radius: 14px;
    padding: 18px 16px;
    max-width: 340px;
    margin: 0 auto;
    font-family: 'Courier New', monospace;
    font-size: 0.92rem;
    line-height: 1.45;
    white-space: pre;
    overflow-x: auto;
    box-shadow: 0 8px 24px rgba(74,55,40,0.12);
}

/* Low stock */
.low-stock {
    background: #fff5eb;
    border-left: 5px solid #e67e22;
    padding: 12px 16px;
    border-radius: 10px;
    margin: 8px 0;
    font-weight: 500;
}

/* Slideshow card */
.slide-card {
    background: white;
    border-radius: 20px;
    padding: 24px;
    text-align: center;
    border: 1px solid #e8dfd4;
    box-shadow: 0 6px 18px rgba(74,55,40,0.08);
}
</style>
""", unsafe_allow_html=True)

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 10px 0 6px 0;">
        <div style="font-size: 2.8rem;">☕</div>
        <div style="font-size:1.35rem; font-weight:700; color:#fff;">Coffee Chantha</div>
        <div style="font-size:0.85rem; opacity:0.85;">រីករាយ ទំនុកចិត្ត រសជាតឆ្ងាញ់</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    menu = st.radio(
        "ម៉ឺនុយ",
        [
            "🏠 ទំព័រដើម",
            "🛒 លក់ថ្មី",
            "📦 ផលិតផល",
            "📋 ប្រវត្តិលក់",
            "📊 របាយការណ៍",
            "💱 អត្រាប្ដូរប្រាក់",
            "📞 ទំនាក់ទំនង",
            "⚙️ QR Code",
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("© Coffee Chantha • Supabase Cloud DB")

# ==================== PAGES ====================

# ---------- DASHBOARD ----------
if menu == "🏠 ទំព័រដើម":
    st.markdown("## 🏠 ទំព័រដើម")

    products = load_products()
    orders = load_orders()
    today = date.today().strftime("%Y-%m-%d")
    today_orders = [o for o in orders if o["date"] == today]
    revenue = sum(float(o["total"]) for o in today_orders)
    order_ids = set(o["order_id"] for o in today_orders)
    low = [p for p in products if p["stock"] <= 20]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 ចំណូលថ្ងៃនេះ", f"${revenue:.2f}")
    c2.metric("🧾 Order ថ្ងៃនេះ", len(order_ids))
    c3.metric("📦 ផលិតផល", len(products))
    c4.metric("⚠️ ស្តុកទាប", len(low))

    st.markdown("### ✨ ម៉ឺនុយផលិតផលថ្មីៗ")
    if products:
        cols = st.columns(3)
        for i, p in enumerate(products[:6]):
            with cols[i % 3]:
                icon = get_product_icon(p["name"], p["category"])
                st.markdown(f"""
                <div class="slide-card">
                    <div class="product-icon">{icon}</div>
                    <div style="font-weight:700; font-size:1.15rem; color:#4a3728;">{p['name']}</div>
                    <div style="color:#8b7355; font-size:0.9rem;">{p['name_kh']}</div>
                    <div style="margin-top:8px; font-size:1.3rem; font-weight:700; color:#6F4E37;">${float(p['price']):.2f}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("មិនទាន់មានផលិតផល")

    st.markdown("### ⚠️ ផលិតផលស្តុកទាប")
    if low:
        for p in low:
            st.markdown(
                f"<div class='low-stock'>⚠️ <b>{p['name']}</b> ({p['name_kh']}) — "
                f"ស្តុកនៅសល់តែ <b style='color:#e67e22'>{p['stock']} {p['unit']}</b></div>",
                unsafe_allow_html=True
            )
    else:
        st.success("✅ ស្តុកគ្រប់គ្រាន់ទាំងអស់")

# ---------- ORDER ----------
elif menu == "🛒 លក់ថ្មី":
    st.markdown("## 🛒 លក់ថ្មី")

    if st.session_state.last_receipt:
        rec = st.session_state.last_receipt
        lines = []
        lines.append("=" * 34)
        lines.append("   COFFEE CHANTHA កាហ្វេ ចន្ថា")
        lines.append("   *** RECEIPT / វិក័យប័ត្រ ***")
        lines.append("=" * 34)
        lines.append(f"Order # : {rec['order_id']}")
        lines.append(f"Date    : {rec['date_time']}")
        lines.append(f"Staff   : {rec['staff']}")
        lines.append(f"Payment : {rec['payment']}")
        lines.append("-" * 34)
        for it in rec["items"]:
            lines.append(f"{it['name']}")
            lines.append(f"  {it['qty']} x ${it['price']:.2f} = ${it['subtotal']:.2f}")
        lines.append("-" * 34)
        lines.append(f"TOTAL          ${rec['total']:.2f}")
        lines.append(f"≈ {int(rec['total'] * USD_TO_KHR):,} ៛")
        lines.append("=" * 34)
        lines.append("   សូមអរគុណ! Thank you!")
        lines.append("=" * 34)
        receipt_text = "\n".join(lines)

        col_r, col_q = st.columns([1.3, 1])
        with col_r:
            st.markdown("### 🧾 វិក័យប័ត្រ")
            st.markdown(f"<div class='receipt-box'>{receipt_text}</div>", unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            with c1:
                st.download_button("💾 ទាញយក", receipt_text, f"receipt_{rec['order_id']}.txt", use_container_width=True)
            with c2:
                st.markdown(f"""
                <a href="javascript:void(0)" onclick="window.print()" style="
                    display:block; text-align:center; background:linear-gradient(135deg,#6F4E37,#5a3e2b);
                    color:white; padding:0.6rem; border-radius:12px; text-decoration:none; font-weight:600;">
                    🖨️ ព្រីន
                </a>
                """, unsafe_allow_html=True)
            with c3:
                if st.button("បិទ", use_container_width=True, type="primary"):
                    st.session_state.last_receipt = None
                    st.rerun()

        with col_q:
            bank_label = BANK_LOGOS.get(rec["payment"], rec["payment"])
            st.markdown(f"### {bank_label}")
            qr = get_qr_image(rec["order_id"], rec["total"], rec["payment"])
            if qr is not None:
                st.image(qr, width=210)
            st.caption(f"Order #{rec['order_id']} • ${rec['total']:.2f}")

        st.success(f"✅ លក់ជោគជ័យ! Order #{rec['order_id']} | ${rec['total']:.2f}")
        st.markdown("---")

    products = load_products()
    left, right = st.columns([1.65, 1])

    with left:
        st.subheader("ជ្រើសរើសផលិតផល")
        search = st.text_input("🔍 ស្វែងរកផលិតផល", placeholder="វាយឈ្មោះ...")
        cats = ["ទាំងអស់"] + sorted({p["category"] for p in products})
        selected_cat = st.selectbox("ប្រភេទ", cats)

        filtered = products
        if selected_cat != "ទាំងអស់":
            filtered = [p for p in filtered if p["category"] == selected_cat]
        if search.strip():
            q = search.strip().lower()
            filtered = [p for p in filtered if q in p["name"].lower() or (p["name_kh"] and q in p["name_kh"].lower())]

        cols = st.columns(3)
        for i, p in enumerate(filtered):
            with cols[i % 3]:
                icon = get_product_icon(p["name"], p["category"])
                st.markdown(f"""
                <div class="product-card">
                    <div class="product-icon">{icon}</div>
                    <div style="font-weight:700; color:#4a3728;">{p['name']}</div>
                    <div style="color:#8b7355; font-size:0.88rem;">{p['name_kh']}</div>
                    <div style="margin:6px 0; font-size:1.25rem; font-weight:700; color:#6F4E37;">${float(p['price']):.2f}</div>
                    <div style="font-size:0.82rem; color:#888;">ស្តុក: {p['stock']} {p['unit']}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("➕ បន្ថែម", key=f"add_{p['id']}", use_container_width=True):
                    if p["stock"] <= 0:
                        st.warning("អស់ស្តុក")
                    else:
                        if p["id"] in st.session_state.cart:
                            st.session_state.cart[p["id"]]["qty"] += 1
                        else:
                            st.session_state.cart[p["id"]] = {"name": p["name"], "price": float(p["price"]), "qty": 1}
                        st.rerun()

    with right:
        st.subheader("🛒 កន្ត្រក់")
        if not st.session_state.cart:
            st.info("កន្ត្រក់ទទេ")
        else:
            total = 0.0
            for pid, item in st.session_state.cart.items():
                sub = item["price"] * item["qty"]
                total += sub
                c1, c2, c3 = st.columns([3, 1, 1])
                c1.write(f"**{item['name']}**")
                c2.write(f"x{item['qty']}")
                c3.write(f"${sub:.2f}")

            st.markdown(f"### សរុប: **${total:.2f}**")
            st.caption(f"≈ {int(total * USD_TO_KHR):,} ៛")

            payment = st.selectbox("វិធីបង់ប្រាក់", ["Cash", "ABA", "Wing", "ACLEDA", "Canadia", "Other"])
            staff = st.selectbox("បុគ្គលិក", ["Chantha", "Hong", "Ram", "Phearom", "Ranin", "Other"])

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
                            "order_id": order_id,
                            "date_time": now.strftime("%Y-%m-%d %H:%M"),
                            "staff": staff,
                            "payment": payment,
                            "total": total,
                            "items": items
                        }
                        st.session_state.cart = {}
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with b2:
                if st.button("🗑️ សម្អាត", use_container_width=True):
                    st.session_state.cart = {}
                    st.rerun()

# ---------- PRODUCTS ----------
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
                save_btn = b1.form_submit_button("💾 រក្សាទុក", use_container_width=True)
                del_btn = b2.form_submit_button("🗑️ លុប", use_container_width=True)

                if save_btn:
                    update_product(selected["id"], name, name_kh, category, price, stock, unit)
                    st.success("✅ បានកែប្រែជោគជ័យ!")
                    st.balloons()
                    st.rerun()
                if del_btn:
                    soft_delete_product(selected["id"])
                    st.success(f"✅ បានលុប «{selected['name']}» ជោគជ័យ!")
                    st.rerun()

        if inactive:
            st.markdown("---")
            st.subheader("♻️ ផលិតផលដែលបានលុប")
            for p in inactive:
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{p['name']}** ({p['name_kh']})")
                if c2.button("ស្តារ", key=f"res_{p['id']}"):
                    restore_product(p["id"])
                    st.success(f"✅ បានស្តារ «{p['name']}»")
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
            if st.form_submit_button("➕ បន្ថែមផលិតផល", use_container_width=True):
                if name.strip():
                    add_product(name.strip(), name_kh.strip(), category or "Other", price, stock, unit or "cup")
                    st.success("✅ បានបន្ថែមផលិតផលជោគជ័យ!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("ត្រូវការឈ្មោះ")

# ---------- HISTORY ----------
elif menu == "📋 ប្រវត្តិលក់":
    st.markdown("## 📋 ប្រវត្តិការលក់")
    orders = load_orders()
    if not orders:
        st.info("មិនទាន់មានទិន្នន័យ")
    else:
        df = pd.DataFrame(orders)[["order_id", "date", "time", "product_name", "qty", "total", "payment", "staff"]]
        df["total"] = df["total"].astype(float)
        st.dataframe(df.style.format({"total": "${:.2f}"}), use_container_width=True, hide_index=True)
        st.markdown(f"**សរុប: ${df['total'].sum():.2f}** | ចំនួន: {len(df)}")

# ---------- REPORT ----------
elif menu == "📊 របាយការណ៍":
    st.markdown("## 📊 របាយការណ៍")
    orders = load_orders()
    if not orders:
        st.info("មិនទាន់មានទិន្នន័យ")
    else:
        daily = {}
        for o in orders:
            tot = float(o["total"])
            daily[o["date"]] = daily.get(o["date"], 0) + tot
        daily_df = pd.DataFrame([{"Date": k, "Revenue": v} for k, v in sorted(daily.items(), reverse=True)])
        st.subheader("💰 ចំណូលប្រចាំថ្ងៃ")
        st.dataframe(daily_df.style.format({"Revenue": "${:.2f}"}), use_container_width=True, hide_index=True)
        st.bar_chart(daily_df.set_index("Date")["Revenue"])

        prod = {}
        for o in orders:
            pname = o["product_name"]
            tot = float(o["total"])
            if pname not in prod:
                prod[pname] = {"qty": 0, "rev": 0}
            prod[pname]["qty"] += o["qty"]
            prod[pname]["rev"] += tot
        prod_df = pd.DataFrame([
            {"Product": k, "Qty": v["qty"], "Revenue": v["rev"]}
            for k, v in sorted(prod.items(), key=lambda x: -x[1]["qty"])
        ])
        st.subheader("🏆 ផលិតផលលក់ដាច់")
        st.dataframe(prod_df.style.format({"Revenue": "${:.2f}"}), use_container_width=True, hide_index=True)

# ---------- EXCHANGE RATE ----------
elif menu == "💱 អត្រាប្ដូរប្រាក់":
    st.markdown("## 💱 អត្រាប្ដូរប្រាក់")
    st.info(f"អត្រាបច្ចុប្បន្ន: **1 USD = {USD_TO_KHR:,} ៛**")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("ដុល្លា → រៀល")
        usd = st.number_input("ចំនួនដុល្លា ($)", min_value=0.0, value=1.0, step=0.5)
        st.success(f"**{usd:.2f} $ = {int(usd * USD_TO_KHR):,} ៛**")

    with col2:
        st.subheader("រៀល → ដុល្លា")
        khr = st.number_input("ចំនួនរៀល (៛)", min_value=0, value=4100, step=100)
        st.success(f"**{khr:,} ៛ = ${khr / USD_TO_KHR:.2f}**")

# ---------- CONTACT ----------
elif menu == "📞 ទំនាក់ទំនង":
    st.markdown("## 📞 ទំនាក់ទំនង")
    st.markdown("""
    <div style="background:white; border-radius:18px; padding:28px; border:1px solid #e8dfd4; max-width:520px;">
        <h3 style="color:#4a3728; margin-top:0;">☕ Coffee Chantha</h3>
        <p style="font-size:1.05rem; line-height:1.9;">
            📱 <b>ទូរសព្ទ</b>: 093 495 903<br>
            📲 <b>Telegram</b>: @CoffeeChanthaKH<br>
            📘 <b>Facebook Page</b>: facebook.com/CoffeeChanthaKH<br>
            🎵 <b>TikTok</b>: @coffeechantha.kh<br>
            📧 <b>Email</b>: hello@coffeechantha.kh<br>
            📍 <b>អាសយដ្ឋាន</b>: ភ្នំពេញ, កម្ពុជា
        </p>
        <p style="color:#8b7355; margin-bottom:0;">បើករាល់ថ្ងៃ 7:00 AM – 9:00 PM</p>
    </div>
    """, unsafe_allow_html=True)

# ---------- QR CODE ----------
elif menu == "⚙️ QR Code":
    st.markdown("## ⚙️ គ្រប់គ្រង QR Code")
    st.info("ដាក់ file QR ក្នុង folder `data/` (aba_qr.png, wing_qr.png, acleda_qr.png...)")

    avail = {}
    for pay, fname in QR_FILES.items():
        avail[pay] = any((f / fname).exists() for f in [DATA_DIR, APP_DIR])

    data = [{"ធនាគារ": BANK_LOGOS.get(k, k), "ឯកសារ": v, "ស្ថានភាព": "✅ មាន" if avail[k] else "❌ មិនមាន"} 
            for k, v in QR_FILES.items()]
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)

    cols = st.columns(3)
    i = 0
    for pay, fname in QR_FILES.items():
        for folder in [DATA_DIR, APP_DIR]:
            path = folder / fname
            if path.exists():
                with cols[i % 3]:
                    st.markdown(f"**{BANK_LOGOS.get(pay, pay)}**")
                    st.image(str(path), width=160)
                i += 1
                break