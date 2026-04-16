from __future__ import annotations

from datetime import date, datetime, timedelta
import calendar
from pathlib import Path
import base64

import pandas as pd
import streamlit as st

from inventory_db import (
    Product,
    add_category,
    add_product,
    add_transaction,
    authenticate_user,
    backend_label,
    change_password,
    delete_category,
    delete_product,
    connect,
    create_order,
    create_user,
    delete_user,
    fetch_categories,
    fetch_inventory,
    fetch_orders,
    fetch_purchase_transactions,
    fetch_reduction_transactions,
    fetch_products,
    fetch_transactions,
    fetch_users,
    init_db,
    rename_category,
    update_user_role_and_status,
    update_product,
    get_recovery_question,
    recover_password,
    set_recovery_details,
    update_purchase_transaction,
    update_reduction_transaction,
    update_order,
)


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "inventory.sqlite3"
LOGO_PATH = APP_DIR / "icon" / "Opal Logo.png"
RECOVERY_QUESTION_OPTIONS = [
    "What was the name of your first school?",
    "What is your mother's maiden name?",
    "What was your childhood nickname?",
    "What is the name of your first pet?",
    "What city were you born in?",
    "What was the model of your first vehicle?",
    "What is your favorite teacher's last name?",
    "Custom question...",
]


def get_theme_css() -> str:
    return """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@600&family=Space+Grotesk&family=Inter&display=swap');

          /* Hide Streamlit Header, GitHub Icon, Main Menu, and App Management */
          header[data-testid="stHeader"], 
          #MainMenu, 
          div[data-testid="stStatusWidget"],
          div[data-testid="stToolbar"],
          div[data-testid="stDecoration"],
          div[class^="st-emotion-cache-mq0m0e"],
          div[class*="stAppDeployButton"],
          button[title="Manage app"],
          footer {
              visibility: hidden;
              display: none !important;
          }

          /* Desktop: keep the original wide look, just add comfortable padding */
          .main .block-container {
            padding-top: 1.1rem;
            padding-bottom: 4rem !important;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
          }

          /* Larger base typography */
          html, body, [class*="css"]  {
            font-size: 18px !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Titles / headers */
          h1, h2, h3 {
            font-size: 2.0rem !important;
            font-weight: 600 !important;
            font-family: 'Manrope', sans-serif !important;
          }
          h2 { font-size: 1.6rem !important; }
          h3 { font-size: 1.25rem !important; }

          /* Subheaders */
          h4, h5, h6 {
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Widget labels */
          label, .stSelectbox label, .stNumberInput label, .stTextInput label {
            font-size: 1.05rem !important;
            font-weight: 650 !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Inputs */
          .stSelectbox div[data-baseweb="select"] > div,
          .stNumberInput input,
          .stTextInput input {
            font-size: 1.05rem !important;
            min-height: 44px !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Buttons */
          .stButton button {
            font-size: 1.05rem !important;
            font-weight: 700 !important;
            padding: 0.65rem 1.1rem !important;
            font-family: 'Inter', sans-serif !important;
          }
          .stButton button:hover {
            background-color: #B0171C !important;
          }

          /* Tabs */
          button[data-baseweb="tab"] {
            font-size: 1.05rem !important;
            font-weight: 650 !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Dataframe readability */
          .stDataFrame, .stDataFrame * {
            font-size: 0.98rem !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Keep tables usable on small screens */
          .stDataFrame {
            overflow-x: auto !important;
          }

          /* Reduce washed-out caption text */
          .stCaption, .stCaption * {
            opacity: 0.95 !important;
            font-family: 'Space Grotesk', sans-serif !important;
          }

          /* Mobile responsiveness */
          @media (max-width: 768px) {
            .main .block-container {
              max-width: 100% !important;
              padding-left: 0.75rem !important;
              padding-right: 0.75rem !important;
            }

            html, body, [class*="css"] {
              font-size: 16px !important;
            }

            h1 { font-size: 1.55rem !important; }
            h2 { font-size: 1.35rem !important; }
            h3 { font-size: 1.15rem !important; }

            .stButton button {
              width: 100% !important;
              min-height: 44px !important;
            }

            .stTabs [data-baseweb="tab-list"] {
              overflow-x: auto !important;
              overflow-y: hidden !important;
              flex-wrap: nowrap !important;
              scrollbar-width: thin;
            }

            button[data-baseweb="tab"] {
              font-size: 0.85rem !important;
              white-space: nowrap !important;
              line-height: 1.1 !important;
              padding: 0.45rem 0.75rem !important;
              min-width: max-content !important;
              flex: 0 0 auto !important;
            }

            .stDataFrame, .stDataFrame > div, .stDataFrame table {
              overflow-x: auto !important;
            }
          }

          .footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            background: transparent;
            padding: 0;
            color: #E31E24 !important;
            text-align: center;
            font-size: 0.9rem;
            z-index: 999;
            font-family: 'Space Grotesk', sans-serif !important;
          }
        </style>
    """
@st.cache_resource
def get_conn(schema_version: int = 5):
    conn = connect(DB_PATH)
    init_db(conn)
    return conn


def ordered_categories(products: list[Product]) -> list[str]:
    seen: set[str] = set()
    categories: list[str] = []
    for p in products:
        if p.category not in seen:
            seen.add(p.category)
            categories.append(p.category)
    return categories


def ordered_names(products: list[Product], category: str) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for p in products:
        if p.category == category and p.name not in seen:
            seen.add(p.name)
            names.append(p.name)
    return names


def product_picker(products: list[Product], *, key_prefix: str) -> Product | None:
    if not products:
        return None
    categories = ordered_categories(products)
    cat = st.selectbox("Category", categories, key=f"{key_prefix}_category")
    names = ordered_names(products, cat)
    name = st.selectbox("Product", names, key=f"{key_prefix}_product")
    return Product(category=cat, name=name)


def render_logo(*, width: int = 180) -> None:
    if not LOGO_PATH.exists():
        return
    with open(LOGO_PATH, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; align-items: center; margin-top: 2rem;">
            <img src="data:image/png;base64,{data}" width="{width}" 
                 style="pointer-events: none; -webkit-user-drag: none; user-select: none; image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;">
        </div>
        """,
        unsafe_allow_html=True,
    )


def login_view(conn) -> None:
    login_tab, forgot_tab = st.tabs(["Login", "Forgot Password"])

    with login_tab:
        st.subheader("User Login")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submit = st.form_submit_button("Login", type="primary")
        if submit:
            user = authenticate_user(conn, username=username, password=password)
            if user:
                st.session_state["auth_user"] = user
                st.rerun()
            else:
                st.error("Invalid username/password or inactive account.")

    with forgot_tab:
        st.subheader("Recover Password")
        with st.form("recover_form", clear_on_submit=False):
            r_username = st.text_input("Username", key="recover_username").strip().lower()
            question = get_recovery_question(conn, username=r_username) if r_username else ""
            if question:
                st.info(f"Recovery question: {question}")
            else:
                st.caption("Enter username to load recovery question.")
            r_answer = st.text_input("Recovery answer", key="recover_answer")
            r_new = st.text_input("New password", type="password", key="recover_new_password")
            r_new_confirm = st.text_input("Confirm new password", type="password", key="recover_new_password_confirm")
            recover_submit = st.form_submit_button("Reset Password", type="primary")
        if recover_submit:
            if not r_username:
                st.error("Enter username.")
            elif not r_new or r_new != r_new_confirm:
                st.error("New passwords do not match.")
            else:
                ok = recover_password(
                    conn,
                    username=r_username,
                    recovery_answer=r_answer,
                    new_password=r_new,
                )
                if ok:
                    st.success("Password reset successful. You can login now.")
                else:
                    st.error("Recovery failed. Check username, recovery answer, or setup recovery details first.")

    st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
    render_logo(width=170)


def main() -> None:
    st.set_page_config(page_title="Inventory System", layout="wide")
    st.title("Inventory System")

    conn = get_conn(schema_version=5)

    auth_user = st.session_state.get("auth_user")
    if not auth_user:
        login_view(conn)
        st.stop()

    current_username = str(auth_user["username"])
    current_role = str(auth_user["role"])
    is_admin = current_role == "admin"

    with st.sidebar:
        st.markdown(f"**Logged in as:** `{current_username}`")
        st.markdown(f"**Role:** `{current_role}`")
        st.caption(f"Active database: {backend_label()}")
        st.caption("Catalog source: Database")
        st.markdown("---")
        if st.button("Logout", key="logout_btn"):
            st.session_state.pop("auth_user", None)
            st.rerun()

    st.markdown(get_theme_css(), unsafe_allow_html=True)

    category_list = fetch_categories(conn)
    all_products = fetch_products(conn)

    st.metric("No. of Products", len(all_products))

    tab_names = [
        "Inventory",
        "Purchase",
        "Reduction",
        "Replacement",
        "Orders",
        "Products",
        "Transactions",
        "Account",
    ]
    if is_admin:
        tab_names.append("Users")
    tabs = st.tabs(tab_names)
    tab_map = dict(zip(tab_names, tabs))

    with tab_map["Purchase"]:
        st.subheader("Manual Purchase (Add Stock)")
        p = product_picker(all_products, key_prefix="purchase")
        qty = st.number_input("Quantity to add", min_value=0.0, value=1.0, step=1.0, key="purchase_qty")
        note = st.text_input("Note (optional)", "", key="purchase_note")
        if st.button("Save Purchase", type="primary", disabled=(p is None or qty <= 0)):
            add_transaction(
                conn,
                tx_type="purchase",
                product=p,
                qty=float(qty),
                created_by=current_username,
                note=note.strip() or None,
            )
            st.success("Purchase saved.")
            st.rerun()

    with tab_map["Reduction"]:
        st.subheader("Manual Reduction (Remove Stock)")
        p = product_picker(all_products, key_prefix="reduction")
        qty = st.number_input("Quantity to remove", min_value=0.0, value=1.0, step=1.0, key="reduction_qty")
        note = st.text_input("Note (optional)", "", key="reduction_note")
        if st.button("Save Reduction", type="primary", disabled=(p is None or qty <= 0)):
            add_transaction(
                conn,
                tx_type="reduction",
                product=p,
                qty=float(qty),
                created_by=current_username,
                note=note.strip() or None,
            )
            st.success("Reduction saved.")
            st.rerun()

    with tab_map["Replacement"]:
        replacement_tab, replaced_tab = st.tabs(["Materials used", "Materials replaced"])

        with replacement_tab:
            st.subheader("Replacement")
            st.caption("Record materials used during replacement work.")
            p = product_picker(all_products, key_prefix="replacement_used")
            qty = st.number_input("Quantity used", min_value=0.0, value=1.0, step=1.0, key="replacement_used_qty")
            warranty = st.text_input("Warranty Status", "", key="replacement_used_warranty")
            if st.button("Save Usage", type="primary", disabled=(p is None or qty <= 0), key="save_replacement_usage_btn"):
                add_transaction(
                    conn,
                    tx_type="reduction",
                    product=p,
                    qty=float(qty),
                    created_by=current_username,
                    note=(f"Replacement usage - Warranty: {warranty.strip()}" if warranty.strip() else "Replacement usage"),
                )
                st.success("Usage saved.")
                st.rerun()

        with replaced_tab:
            st.subheader("Materials replaced")
            st.caption("Record materials replaced during replacement work.")
            p = product_picker(all_products, key_prefix="replacement_replaced")
            qty = st.number_input("Quantity used", min_value=0.0, value=1.0, step=1.0, key="replacement_replaced_qty")
            warranty = st.text_input("Warranty Status", "", key="replacement_replaced_warranty")
            if st.button("Save Replacement", type="primary", disabled=(p is None or qty <= 0), key="save_materials_replaced_btn"):
                add_transaction(
                    conn,
                    tx_type="reduction",
                    product=p,
                    qty=float(qty),
                    created_by=current_username,
                    note=(f"Replacement replaced - Warranty: {warranty.strip()}" if warranty.strip() else "Replacement replaced"),
                )
                st.success("Replacement saved.")
                st.rerun()

    with tab_map["Products"]:
        st.subheader("Manage Products")
        st.caption("Manage categories and products directly in the database.")

        manage_categories_tab, add_product_tab, edit_product_tab = st.tabs(
            ["Categories", "Add Product", "Edit / Delete Product"]
        )

        with manage_categories_tab:
            st.markdown("### Categories")
            new_category_name = st.text_input("New category", key="category_add_name").strip()
            if st.button("Add Category", type="primary", disabled=not new_category_name, key="add_category_btn"):
                created = add_category(conn, new_category_name)
                if created:
                    st.success("Category added successfully.")
                else:
                    st.warning("That category already exists or is invalid.")
                st.rerun()

            if category_list:
                selected_category = st.selectbox("Existing category", category_list, key="manage_existing_category")
                renamed_category = st.text_input("Rename category to", value=selected_category, key="rename_category_value").strip()
                if st.button("Rename Category", key="rename_category_btn"):
                    ok, message = rename_category(conn, old_name=selected_category, new_name=renamed_category)
                    (st.success if ok else st.error)(message)
                    if ok:
                        st.rerun()

                confirm_delete_category = st.checkbox(
                    f"Confirm delete category '{selected_category}'",
                    key="confirm_delete_category",
                )
                if st.button(
                    "Delete Category",
                    disabled=not confirm_delete_category,
                    key="delete_category_btn",
                ):
                    ok, message = delete_category(conn, name=selected_category)
                    (st.success if ok else st.error)(message)
                    if ok:
                        st.rerun()
            else:
                st.info("No categories available yet.")

        with add_product_tab:
            category_mode = st.radio(
                "Category option",
                ["Use existing category", "Create new category"],
                horizontal=True,
                key="product_category_mode",
            )
            if category_mode == "Use existing category":
                if category_list:
                    category = st.selectbox("Select category", category_list, key="new_product_existing_category")
                else:
                    st.info("No categories available yet. Create a new category first.")
                    category = ""
            else:
                category = st.text_input("New category name", key="new_product_category_text").strip()

            new_name = st.text_input("New product name", key="new_product_name").strip()
            can_save = bool(category and new_name)
            if st.button("Add Product", type="primary", disabled=not can_save, key="add_product_btn"):
                inserted = add_product(conn, Product(category=category, name=new_name))
                if inserted:
                    st.success("Product added successfully.")
                else:
                    st.warning("This product already exists in that category.")
                st.rerun()

        with edit_product_tab:
            if not all_products:
                st.info("No products available yet.")
            else:
                product_map = {
                    f"{p.category} - {p.name}": p
                    for p in all_products
                }
                selected_product_label = st.selectbox(
                    "Select product",
                    list(product_map.keys()),
                    key="edit_product_selected",
                )
                selected_product = product_map[selected_product_label]
                edit_category_mode = st.radio(
                    "Updated category option",
                    ["Use existing category", "Create new category"],
                    horizontal=True,
                    key="edit_product_category_mode",
                )
                if edit_category_mode == "Use existing category":
                    edit_category = st.selectbox(
                        "Category",
                        category_list or [selected_product.category],
                        index=(category_list.index(selected_product.category) if selected_product.category in category_list else 0),
                        key="edit_product_category",
                    )
                else:
                    edit_category = st.text_input(
                        "New category name",
                        value=selected_product.category,
                        key="edit_product_category_text",
                    ).strip()
                edit_name = st.text_input("Product name", value=selected_product.name, key="edit_product_name").strip()
                if st.button("Update Product", type="primary", key="update_product_btn"):
                    ok, message = update_product(
                        conn,
                        old_category=selected_product.category,
                        old_name=selected_product.name,
                        new_category=edit_category,
                        new_name=edit_name,
                    )
                    (st.success if ok else st.error)(message)
                    if ok:
                        st.rerun()

                confirm_delete_product = st.checkbox(
                    f"Confirm delete product '{selected_product.name}'",
                    key="confirm_delete_product",
                )
                if st.button(
                    "Delete Product",
                    disabled=not confirm_delete_product,
                    key="delete_product_btn",
                ):
                    ok, message = delete_product(conn, category=selected_product.category, name=selected_product.name)
                    (st.success if ok else st.error)(message)
                    if ok:
                        st.rerun()

    with tab_map["Orders"]:
        submit_order_tab, edit_order_tab, order_list_tab = st.tabs(["Submit Order", "Edit Existing Order", "Order List"])

        with submit_order_tab:
            st.subheader("Order Submission")
            st.caption("Select product and place an order request.")
            order_product = product_picker(all_products, key_prefix="order")
            order_qty = st.number_input("Order quantity", min_value=0.01, value=1.0, step=1.0, key="order_qty")
            order_note = st.text_input("Remarks (optional)", "", key="order_note")
            if st.button("Place Order", type="primary", disabled=(order_product is None or order_qty <= 0), key="place_order_btn"):
                ok = create_order(
                    conn,
                    category=order_product.category,
                    name=order_product.name,
                    qty=float(order_qty),
                    note=order_note.strip() or None,
                    created_by=current_username,
                )
                if ok:
                    st.success("Order submitted successfully.")
                else:
                    st.error("Could not submit order.")
                st.rerun()

        with edit_order_tab:
            st.subheader("Edit Existing Order")
            st.caption("Update an existing order (admin: all orders, user: own orders).")
            edit_order_limit = st.number_input(
                "Rows to scan",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
                key="edit_orders_limit",
            )
            edit_orders = fetch_orders(
                conn,
                limit=int(edit_order_limit),
                created_by=None if is_admin else current_username,
            )
            if not edit_orders:
                st.info("No orders available to edit.")
            else:
                order_map = {
                    f"ID {int(r[0])} | {str(r[1])} | {str(r[2])} - {str(r[3])} | Qty {float(r[4])} | {str(r[6])} | By {str(r[7])}": r
                    for r in edit_orders
                }
                selected_order_label = st.selectbox(
                    "Select order",
                    list(order_map.keys()),
                    key="edit_order_selected",
                )
                selected_order = order_map[selected_order_label]
                selected_order_id = int(selected_order[0])
                selected_order_category = str(selected_order[2])
                selected_order_name = str(selected_order[3])
                selected_order_qty = float(selected_order[4])
                selected_order_note = str(selected_order[5])
                selected_order_status = str(selected_order[6])

                order_categories = ordered_categories(all_products)
                edit_order_category = st.selectbox(
                    "Category",
                    order_categories,
                    index=order_categories.index(selected_order_category) if selected_order_category in order_categories else 0,
                    key=f"edit_order_category_{selected_order_id}",
                )
                order_names = ordered_names(all_products, edit_order_category)
                order_name_index = order_names.index(selected_order_name) if selected_order_name in order_names else 0
                edit_order_name = st.selectbox(
                    "Product",
                    order_names,
                    index=order_name_index,
                    key=f"edit_order_name_{selected_order_id}",
                )
                edit_order_qty = st.number_input(
                    "Quantity",
                    min_value=0.01,
                    value=max(0.01, selected_order_qty),
                    step=1.0,
                    key=f"edit_order_qty_{selected_order_id}",
                )
                edit_order_note = st.text_input(
                    "Remarks (optional)",
                    value=selected_order_note,
                    key=f"edit_order_note_{selected_order_id}",
                )
                status_options = ["pending", "approved", "rejected", "received"]
                status_idx = status_options.index(selected_order_status) if selected_order_status in status_options else 0
                if is_admin:
                    edit_order_status = st.selectbox(
                        "Status",
                        status_options,
                        index=status_idx,
                        key=f"edit_order_status_{selected_order_id}",
                    )
                else:
                    edit_order_status = selected_order_status
                    st.caption(f"Current status: {selected_order_status}")

                if st.button("Update Order", type="primary", key=f"edit_order_btn_{selected_order_id}"):
                    updated = update_order(
                        conn,
                        order_id=selected_order_id,
                        category=edit_order_category,
                        name=edit_order_name,
                        qty=float(edit_order_qty),
                        note=edit_order_note.strip() or None,
                        status=edit_order_status,
                        updated_by=current_username,
                        is_admin=is_admin,
                    )
                    if updated:
                        st.success("Order updated.")
                    else:
                        st.error("Could not update order.")
                    st.rerun()

        with order_list_tab:
            st.subheader("Order List")
            order_limit = st.number_input("Rows", min_value=50, max_value=5000, value=500, step=50, key="orders_limit")
            orders = fetch_orders(
                conn,
                limit=int(order_limit),
                created_by=None if is_admin else current_username,
            )
            orders_df = pd.DataFrame(
                orders,
                columns=["ID", "Created (UTC)", "Category", "Product", "Qty", "Remarks", "Status", "Requested By"],
            )
            st.dataframe(orders_df, width="stretch", hide_index=True)

    with tab_map["Account"]:
        st.subheader("My Account")

        st.markdown("### Change Password")
        with st.form("change_password_form", clear_on_submit=True):
            old_pw = st.text_input("Current password", type="password", key="change_old_pw")
            new_pw = st.text_input("New password", type="password", key="change_new_pw")
            new_pw2 = st.text_input("Confirm new password", type="password", key="change_new_pw2")
            change_pw_btn = st.form_submit_button("Update Password", type="primary")
        if change_pw_btn:
            if not new_pw or new_pw != new_pw2:
                st.error("New passwords do not match.")
            else:
                ok = change_password(
                    conn,
                    username=current_username,
                    current_password=old_pw,
                    new_password=new_pw,
                )
                if ok:
                    st.success("Password updated successfully.")
                else:
                    st.error("Current password is incorrect.")

        st.markdown("---")
        st.markdown("### Recovery Setup")
        st.caption("Set recovery question/answer so you can reset password if forgotten.")
        with st.form("recovery_setup_form", clear_on_submit=True):
            current_pw_for_recovery = st.text_input("Current password", type="password", key="recovery_current_pw")
            selected_recovery_q = st.selectbox(
                "Recovery question",
                RECOVERY_QUESTION_OPTIONS,
                key="recovery_question_select",
            )
            custom_recovery_q = ""
            if selected_recovery_q == "Custom question...":
                custom_recovery_q = st.text_input("Custom recovery question", key="recovery_question_custom")
            recovery_question = custom_recovery_q.strip() if selected_recovery_q == "Custom question..." else selected_recovery_q
            recovery_answer = st.text_input("Recovery answer", type="password", key="recovery_answer")
            recovery_btn = st.form_submit_button("Save Recovery Details", type="primary")
        if recovery_btn:
            ok = set_recovery_details(
                conn,
                username=current_username,
                current_password=current_pw_for_recovery,
                recovery_question=recovery_question,
                recovery_answer=recovery_answer,
            )
            if ok:
                st.success("Recovery details saved.")
            else:
                st.error("Could not save recovery details. Check current password and required fields.")

    with tab_map["Inventory"]:
        st.subheader("On-hand Inventory")

        date_filter_mode = st.selectbox(
            "Filter period",
            ["All time", "Date range", "Month"],
            index=0,
            help="Filter inventory totals by date range or by a specific month.",
        )

        start_date = None
        end_date = None

        if date_filter_mode == "Date range":
            range_values = st.date_input(
                "Date range",
                [date.today() - timedelta(days=30), date.today()],
                key="inventory_date_range",
            )
            if isinstance(range_values, (list, tuple)) and len(range_values) == 2:
                start_date, end_date = range_values
            else:
                start_date = range_values
                end_date = range_values

        elif date_filter_mode == "Month":
            month_names = [
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ]
            current_year = date.today().year
            year_options = [current_year - i for i in range(0, 6)]
            month_name = st.selectbox("Month", month_names, index=date.today().month - 1, key="inventory_month_name")
            year = st.selectbox("Year", year_options, index=0, key="inventory_month_year")
            month_number = month_names.index(month_name) + 1
            start_date = date(year, month_number, 1)
            _, last_day = calendar.monthrange(year, month_number)
            end_date = date(year, month_number, last_day)

        rows = fetch_inventory(conn, start_date=start_date, end_date=end_date)
        inv = pd.DataFrame(rows, columns=["Category", "Product", "Purchased", "Reduced", "On Hand"])

        left, right = st.columns([2, 1])
        with left:
            cats = ["(All)"] + inv["Category"].unique().tolist()
            cat_filter = st.selectbox("Filter by category", cats)
            if date_filter_mode != "All time":
                st.markdown(
                    f"Showing transactions from **{start_date.isoformat()}** to **{end_date.isoformat()}**"
                )
        with right:
            only_negative = st.checkbox("Show only negative on-hand", value=False)

        view = inv
        if cat_filter != "(All)":
            view = view[view["Category"] == cat_filter]
        if only_negative:
            view = view[view["On Hand"] < 0]

        st.dataframe(view, width="stretch", hide_index=True)

    with tab_map["Transactions"]:
        st.subheader("Recent Transactions")
        limit = st.number_input("Rows", min_value=50, max_value=5000, value=500, step=50)
        tx = fetch_transactions(conn, limit=int(limit))
        df = pd.DataFrame(
            tx,
            columns=["ID", "Created (UTC)", "Type", "Category", "Product", "Qty", "Performed By", "Note"],
        )
        st.dataframe(df, width="stretch", hide_index=True)

        st.markdown("---")
        edit_purchase_tab, edit_reduction_tab = st.tabs(["Edit Purchase", "Edit Reduction"])

        with edit_purchase_tab:
            st.subheader("Edit Saved Purchase")
            st.caption("Correct a saved purchase if there was an entry mistake.")
            purchase_limit = st.number_input(
                "Rows to scan",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
                key="edit_purchase_limit",
            )
            purchase_rows = fetch_purchase_transactions(
                conn,
                limit=int(purchase_limit),
                created_by=None if is_admin else current_username,
            )
            if not purchase_rows:
                st.info("No purchase records available to edit.")
            else:
                purchase_map = {
                    f"ID {int(r[0])} | {str(r[1])} | {str(r[3])} - {str(r[4])} | Qty {float(r[5])} | By {str(r[6])}": r
                    for r in purchase_rows
                }
                selected_label = st.selectbox(
                    "Select purchase transaction",
                    list(purchase_map.keys()),
                    key="edit_purchase_selected",
                )
                selected = purchase_map[selected_label]
                selected_id = int(selected[0])
                selected_category = str(selected[3])
                selected_name = str(selected[4])
                selected_qty = float(selected[5])
                selected_note = str(selected[7])

                categories = ordered_categories(all_products)
                edit_category = st.selectbox(
                    "Category",
                    categories,
                    index=categories.index(selected_category) if selected_category in categories else 0,
                    key=f"edit_purchase_category_{selected_id}",
                )
                names = ordered_names(all_products, edit_category)
                default_name_index = names.index(selected_name) if selected_name in names else 0
                edit_name = st.selectbox(
                    "Product",
                    names,
                    index=default_name_index,
                    key=f"edit_purchase_name_{selected_id}",
                )
                edit_qty = st.number_input(
                    "Quantity",
                    min_value=0.01,
                    value=max(0.01, selected_qty),
                    step=1.0,
                    key=f"edit_purchase_qty_{selected_id}",
                )
                edit_note = st.text_input(
                    "Note (optional)",
                    value=selected_note,
                    key=f"edit_purchase_note_{selected_id}",
                )
                if st.button("Update Purchase", type="primary", key=f"edit_purchase_btn_{selected_id}"):
                    updated = update_purchase_transaction(
                        conn,
                        tx_id=selected_id,
                        category=edit_category,
                        name=edit_name,
                        qty=float(edit_qty),
                        note=edit_note.strip() or None,
                    )
                    if updated:
                        st.success("Purchase transaction updated.")
                    else:
                        st.error("Could not update this purchase transaction.")
                    st.rerun()

        with edit_reduction_tab:
            st.subheader("Edit Saved Reduction")
            st.caption("Correct a saved reduction if there was an entry mistake.")
            reduction_limit = st.number_input(
                "Rows to scan",
                min_value=50,
                max_value=5000,
                value=500,
                step=50,
                key="edit_reduction_limit",
            )
            reduction_rows = fetch_reduction_transactions(
                conn,
                limit=int(reduction_limit),
                created_by=None if is_admin else current_username,
            )
            if not reduction_rows:
                st.info("No reduction records available to edit.")
            else:
                reduction_map = {
                    f"ID {int(r[0])} | {str(r[1])} | {str(r[3])} - {str(r[4])} | Qty {float(r[5])} | By {str(r[6])}": r
                    for r in reduction_rows
                }
                selected_red_label = st.selectbox(
                    "Select reduction transaction",
                    list(reduction_map.keys()),
                    key="edit_reduction_selected",
                )
                selected_red = reduction_map[selected_red_label]
                selected_red_id = int(selected_red[0])
                selected_red_category = str(selected_red[3])
                selected_red_name = str(selected_red[4])
                selected_red_qty = float(selected_red[5])
                selected_red_note = str(selected_red[7])

                red_categories = ordered_categories(all_products)
                edit_red_category = st.selectbox(
                    "Category",
                    red_categories,
                    index=red_categories.index(selected_red_category) if selected_red_category in red_categories else 0,
                    key=f"edit_reduction_category_{selected_red_id}",
                )
                red_names = ordered_names(all_products, edit_red_category)
                red_default_name_index = red_names.index(selected_red_name) if selected_red_name in red_names else 0
                edit_red_name = st.selectbox(
                    "Product",
                    red_names,
                    index=red_default_name_index,
                    key=f"edit_reduction_name_{selected_red_id}",
                )
                edit_red_qty = st.number_input(
                    "Quantity",
                    min_value=0.01,
                    value=max(0.01, selected_red_qty),
                    step=1.0,
                    key=f"edit_reduction_qty_{selected_red_id}",
                )
                edit_red_note = st.text_input(
                    "Note (optional)",
                    value=selected_red_note,
                    key=f"edit_reduction_note_{selected_red_id}",
                )
                if st.button("Update Reduction", type="primary", key=f"edit_reduction_btn_{selected_red_id}"):
                    updated = update_reduction_transaction(
                        conn,
                        tx_id=selected_red_id,
                        category=edit_red_category,
                        name=edit_red_name,
                        qty=float(edit_red_qty),
                        note=edit_red_note.strip() or None,
                    )
                    if updated:
                        st.success("Reduction transaction updated.")
                    else:
                        st.error("Could not update this reduction transaction.")
                    st.rerun()

    if is_admin:
        with tab_map["Users"]:
            st.subheader("Manage Users (Admin only)")
            st.caption("Create users and control role/access.")

            with st.form("create_user_form", clear_on_submit=True):
                new_username = st.text_input("New username").strip().lower()
                new_password = st.text_input("New password", type="password")
                new_role = st.selectbox("Role", ["user", "admin"], key="new_user_role")
                admin_recovery_options = ["(None)"] + RECOVERY_QUESTION_OPTIONS
                new_user_recovery_q_select = st.selectbox(
                    "Recovery question (optional)",
                    admin_recovery_options,
                    key="new_user_recovery_q_select",
                )
                new_user_recovery_q_custom = ""
                if new_user_recovery_q_select == "Custom question...":
                    new_user_recovery_q_custom = st.text_input("Custom recovery question (optional)")
                if new_user_recovery_q_select == "(None)":
                    new_user_recovery_q = ""
                elif new_user_recovery_q_select == "Custom question...":
                    new_user_recovery_q = new_user_recovery_q_custom.strip()
                else:
                    new_user_recovery_q = new_user_recovery_q_select
                new_user_recovery_a = st.text_input("Recovery answer (optional)", type="password")
                create_btn = st.form_submit_button("Create User", type="primary")
            if create_btn:
                created = create_user(
                    conn,
                    username=new_username,
                    password=new_password,
                    role=new_role,
                    is_active=True,
                    recovery_question=new_user_recovery_q,
                    recovery_answer=new_user_recovery_a,
                )
                if created:
                    st.success("User created.")
                else:
                    st.error("Could not create user. Username may already exist or fields are empty.")
                st.rerun()

            users = fetch_users(conn)
            users_df = pd.DataFrame(users, columns=["ID", "Username", "Role", "Active", "Created (UTC)", "Recovery Setup"])
            users_df["Active"] = users_df["Active"].apply(lambda v: "Yes" if int(v) == 1 else "No")
            users_df["Recovery Setup"] = users_df["Recovery Setup"].apply(lambda v: "Yes" if str(v).strip() else "No")
            st.dataframe(users_df, width="stretch", hide_index=True)

            username_options = [str(u[1]) for u in users]
            selected_username = st.selectbox("Select user to update", username_options, key="selected_user_update")
            selected_row = next(u for u in users if str(u[1]) == selected_username)
            selected_id = int(selected_row[0])
            selected_is_self = selected_username == current_username
            target_role = st.selectbox(
                "Role",
                ["user", "admin"],
                index=0 if str(selected_row[2]) == "user" else 1,
                key="update_role",
            )
            target_active = st.checkbox("Active", value=(int(selected_row[3]) == 1), key="update_active")

            if selected_is_self:
                st.info("You cannot change your own role/status here.")
            if st.button("Update User", type="primary", disabled=selected_is_self, key="update_user_btn"):
                update_user_role_and_status(conn, user_id=selected_id, role=target_role, is_active=target_active)
                st.success("User updated.")
                st.rerun()

            st.markdown("---")
            st.subheader("Delete User")
            st.caption("Deletion is permanent.")
            if selected_is_self:
                st.info("You cannot delete your own account while logged in.")
            confirm_delete = st.checkbox(
                f"Confirm delete user '{selected_username}'",
                value=False,
                key="confirm_delete_user",
            )
            if st.button(
                "Delete User",
                type="secondary",
                disabled=(selected_is_self or not confirm_delete),
                key="delete_user_btn",
            ):
                deleted = delete_user(conn, user_id=selected_id)
                if deleted:
                    st.success("User deleted.")
                else:
                    st.error("User could not be deleted.")
                st.rerun()

    st.markdown('<div class="footer">© 2026 OPAL Inventory System</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()

