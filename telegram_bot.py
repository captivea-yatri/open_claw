import re
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from config import BOT_TOKEN

BASE_URL = "http://127.0.0.1:5000"

# In-memory pending state
pending_orders = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot is working.\n\n"
        "Command mode:\n"
        "/test_odoo\n"
        "/debug_info\n"
        "/customers\n"
        "/create_lead Lead Name | Contact | Phone | Email\n"
        "/create_sale_order CustomerName | ProductName,Qty,Price ; ProductName,Qty,Price\n"
        "/select_customer NUMBER\n"
        "/select_product NUMBER\n\n"
        "Text prompt mode examples:\n"
        "test odoo\n"
        "show customers\n"
        "find customer Acme\n"
        "find product Laptop\n"
        "price Laptop\n"
        "create sale order for Acme | Laptop,2,50000 ; Mouse,3,500"
    )

async def test_odoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/test", timeout=30)
        data = response.json()

        if response.ok and data.get("ok") is True:
            await update.message.reply_text(
                f"Odoo connection successful! UID: {data.get('uid')}"
            )
        else:
            await update.message.reply_text(
                f"Odoo connection failed: {data.get('error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/debug-info", timeout=30)
        data = response.json()

        if response.ok and data.get("ok") is True:
            user = data.get("user", {})
            await update.message.reply_text(
                f"Debug Info:\n"
                f"DB: {data.get('db')}\n"
                f"URL: {data.get('url')}\n"
                f"UID: {data.get('uid')}\n"
                f"User: {user.get('name')}\n"
                f"Login: {user.get('login')}\n"
                f"Company: {user.get('company_id')}"
            )
        else:
            await update.message.reply_text(f"Debug failed: {data.get('error')}")
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def customers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/customers", timeout=30)
        data = response.json()

        if response.ok and data.get("ok") is True:
            rows = data.get("customers", [])
            if not rows:
                await update.message.reply_text("No customers found.")
                return

            lines = []
            for row in rows:
                lines.append(
                    f"- ID:{row.get('id')} | {row.get('name')} | {row.get('phone')} | {row.get('email')}"
                )

            await update.message.reply_text("Top customers:\n" + "\n".join(lines))
        else:
            await update.message.reply_text(
                f"Failed to fetch customers: {data.get('error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def create_lead(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full_text = update.message.text or ""
        prefix = "/create_lead"
        raw = full_text[len(prefix):].strip()

        if not raw:
            await update.message.reply_text(
                "Usage:\n/create_lead Lead Name | Contact Name | Phone | Email"
            )
            return

        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 4:
            await update.message.reply_text(
                "Usage:\n/create_lead Lead Name | Contact Name | Phone | Email"
            )
            return

        payload = {
            "name": parts[0],
            "contact_name": parts[1],
            "phone": parts[2],
            "email": parts[3],
            "description": "Created from Telegram bot",
        }

        response = requests.post(
            f"{BASE_URL}/create-lead",
            json=payload,
            timeout=30
        )
        data = response.json()

        if response.ok and data.get("ok") is True:
            lead = data.get("lead", {})
            await update.message.reply_text(
                f"Lead created successfully!\n"
                f"ID: {data.get('lead_id')}\n"
                f"Name: {lead.get('name')}\n"
                f"Contact: {lead.get('contact_name')}\n"
                f"Phone: {lead.get('phone')}\n"
                f"Email: {lead.get('email_from')}"
            )
        else:
            await update.message.reply_text(
                f"Lead creation failed: {data.get('error')}"
            )

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def search_customer_by_name(customer_name):
    response = requests.get(
        f"{BASE_URL}/find-customer",
        params={"q": customer_name},
        timeout=30
    )
    return response, response.json()

def search_product_by_name(product_name):
    response = requests.get(
        f"{BASE_URL}/find-product",
        params={"q": product_name},
        timeout=30
    )
    return response, response.json()

async def continue_order_flow(chat_id, update):
    state = pending_orders.get(chat_id)
    if not state:
        await update.message.reply_text("No pending order found.")
        return

    partner = state.get("partner")
    raw_lines = state.get("raw_lines", [])
    current_index = state.get("current_index", 0)
    resolved_lines = state.get("resolved_lines", [])

    while current_index < len(raw_lines):
        item = raw_lines[current_index]
        product_name = item["product_name"]

        product_response, product_data = search_product_by_name(product_name)

        if not product_response.ok or not product_data.get("ok"):
            await update.message.reply_text(
                f"Product search failed for '{product_name}': {product_data.get('error')}"
            )
            pending_orders.pop(chat_id, None)
            return

        products = product_data.get("products", [])
        if not products:
            await update.message.reply_text(f"No product found for: {product_name}")
            pending_orders.pop(chat_id, None)
            return

        if len(products) > 1:
            state["stage"] = "select_product"
            state["product_matches"] = products
            state["current_index"] = current_index
            pending_orders[chat_id] = state

            lines = [f"Multiple products found for '{product_name}':"]
            for i, product in enumerate(products, start=1):
                lines.append(
                    f"{i}. {product.get('name')} | ID:{product.get('id')} | Price:{product.get('lst_price')}"
                )
            lines.append("\nReply with:\n/select_product NUMBER")

            await update.message.reply_text("\n".join(lines))
            return

        product = products[0]
        resolved_lines.append({
            "product_id": int(product["id"]),
            "qty": item["qty"],
            "price": item["price"]
        })

        current_index += 1
        state["resolved_lines"] = resolved_lines
        state["current_index"] = current_index
        pending_orders[chat_id] = state

    payload = {
        "partner_id": partner["id"],
        "lines": resolved_lines
    }

    response = requests.post(
        f"{BASE_URL}/create-sale-order",
        json=payload,
        timeout=30
    )
    data = response.json()

    pending_orders.pop(chat_id, None)

    if response.ok and data.get("ok") is True:
        order = data.get("sale_order", {})
        await update.message.reply_text(
            f"Sale order created successfully!\n"
            f"Customer: {partner.get('name')}\n"
            f"ID: {data.get('sale_order_id')}\n"
            f"Order: {order.get('name')}\n"
            f"State: {order.get('state')}\n"
            f"Partner: {order.get('partner_id')}"
        )
    else:
        await update.message.reply_text(
            f"Sale order creation failed: {data.get('error')}"
        )

async def create_sale_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        full_text = update.message.text or ""
        prefix = "/create_sale_order"
        raw = full_text[len(prefix):].strip()

        if not raw:
            await update.message.reply_text(
                "Usage:\n/create_sale_order CustomerName | ProductName,Qty,Price ; ProductName,Qty,Price"
            )
            return

        await process_sale_order_text(raw, chat_id, update)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def process_sale_order_text(raw, chat_id, update):
    main_parts = [p.strip() for p in raw.split("|", 1)]
    if len(main_parts) < 2:
        await update.message.reply_text(
            "Usage:\nCustomerName | ProductName,Qty,Price ; ProductName,Qty,Price"
        )
        return

    customer_name = main_parts[0]
    line_text = main_parts[1]

    customer_response, customer_data = search_customer_by_name(customer_name)

    if not customer_response.ok or not customer_data.get("ok"):
        await update.message.reply_text(
            f"Customer search failed: {customer_data.get('error')}"
        )
        return

    customers = customer_data.get("customers", [])
    if not customers:
        await update.message.reply_text(f"No customer found for: {customer_name}")
        return

    raw_lines = []
    for item in [x.strip() for x in line_text.split(";") if x.strip()]:
        parts = [p.strip() for p in item.split(",")]
        if len(parts) != 3:
            await update.message.reply_text(
                f"Invalid line format: {item}\nUse ProductName,Qty,Price"
            )
            return

        raw_lines.append({
            "product_name": parts[0],
            "qty": float(parts[1]),
            "price": float(parts[2]),
        })

    if len(customers) > 1:
        pending_orders[chat_id] = {
            "stage": "select_customer",
            "customer_matches": customers,
            "raw_lines": raw_lines,
            "resolved_lines": [],
            "current_index": 0,
        }

        lines = [f"Multiple customers found for '{customer_name}':"]
        for i, customer in enumerate(customers, start=1):
            lines.append(
                f"{i}. {customer.get('name')} | ID:{customer.get('id')} | {customer.get('phone')} | {customer.get('email')}"
            )
        lines.append("\nReply with:\n/select_customer NUMBER")

        await update.message.reply_text("\n".join(lines))
        return

    partner = customers[0]

    pending_orders[chat_id] = {
        "stage": "processing_products",
        "partner": partner,
        "raw_lines": raw_lines,
        "resolved_lines": [],
        "current_index": 0,
    }

    await continue_order_flow(chat_id, update)

async def select_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        state = pending_orders.get(chat_id)

        if not state or state.get("stage") != "select_customer":
            await update.message.reply_text("No pending customer selection found.")
            return

        full_text = update.message.text or ""
        prefix = "/select_customer"
        raw = full_text[len(prefix):].strip()

        if not raw.isdigit():
            await update.message.reply_text("Usage:\n/select_customer NUMBER")
            return

        choice = int(raw)
        matches = state.get("customer_matches", [])

        if choice < 1 or choice > len(matches):
            await update.message.reply_text("Invalid selection number.")
            return

        partner = matches[choice - 1]
        state["partner"] = partner
        state["stage"] = "processing_products"
        pending_orders[chat_id] = state

        await update.message.reply_text(f"Selected customer: {partner.get('name')}")
        await continue_order_flow(chat_id, update)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def select_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        state = pending_orders.get(chat_id)

        if not state or state.get("stage") != "select_product":
            await update.message.reply_text("No pending product selection found.")
            return

        full_text = update.message.text or ""
        prefix = "/select_product"
        raw = full_text[len(prefix):].strip()

        if not raw.isdigit():
            await update.message.reply_text("Usage:\n/select_product NUMBER")
            return

        choice = int(raw)
        matches = state.get("product_matches", [])

        if choice < 1 or choice > len(matches):
            await update.message.reply_text("Invalid selection number.")
            return

        selected_product = matches[choice - 1]
        current_index = state["current_index"]
        raw_line = state["raw_lines"][current_index]

        state["resolved_lines"].append({
            "product_id": int(selected_product["id"]),
            "qty": raw_line["qty"],
            "price": raw_line["price"]
        })

        state["current_index"] += 1
        state["stage"] = "processing_products"
        state.pop("product_matches", None)
        pending_orders[chat_id] = state

        await update.message.reply_text(
            f"Selected product: {selected_product.get('name')}"
        )

        await continue_order_flow(chat_id, update)

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

async def text_prompt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = (update.message.text or "").strip()
        lower_text = text.lower()
        chat_id = update.effective_chat.id

        if not text or text.startswith("/"):
            return

        if lower_text in ["test odoo", "test connection", "check odoo"]:
            await test_odoo(update, context)
            return

        if lower_text in ["customers", "show customers", "list customers"]:
            await customers(update, context)
            return

        if lower_text.startswith("find customer "):
            customer_name = text[len("find customer "):].strip()
            response = requests.get(
                f"{BASE_URL}/find-customer",
                params={"q": customer_name},
                timeout=30
            )
            data = response.json()

            if response.ok and data.get("ok"):
                rows = data.get("customers", [])
                if not rows:
                    await update.message.reply_text("No customer found.")
                    return

                lines = [f"Customers found for '{customer_name}':"]
                for row in rows:
                    lines.append(
                        f"- ID:{row.get('id')} | {row.get('name')} | {row.get('phone')} | {row.get('email')}"
                    )
                await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(f"Customer search failed: {data.get('error')}")
            return

        if lower_text.startswith("find product "):
            product_name = text[len("find product "):].strip()
            response = requests.get(
                f"{BASE_URL}/find-product",
                params={"q": product_name},
                timeout=30
            )
            data = response.json()

            if response.ok and data.get("ok"):
                rows = data.get("products", [])
                if not rows:
                    await update.message.reply_text("No product found.")
                    return

                lines = [f"Products found for '{product_name}':"]
                for row in rows:
                    lines.append(
                        f"- ID:{row.get('id')} | {row.get('name')} | Price:{row.get('lst_price')}"
                    )
                await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(f"Product search failed: {data.get('error')}")
            return

        if lower_text.startswith("price "):
            product_name = text[len("price "):].strip()
            response = requests.get(
                f"{BASE_URL}/find-product",
                params={"q": product_name},
                timeout=30
            )
            data = response.json()

            if response.ok and data.get("ok"):
                products = data.get("products", [])
                if not products:
                    await update.message.reply_text("No product found.")
                    return

                if len(products) == 1:
                    p = products[0]
                    await update.message.reply_text(
                        f"Product price:\n"
                        f"ID: {p.get('id')}\n"
                        f"Name: {p.get('name')}\n"
                        f"Price: {p.get('lst_price')}"
                    )
                else:
                    lines = [f"Multiple products found for '{product_name}':"]
                    for row in products:
                        lines.append(
                            f"- ID:{row.get('id')} | {row.get('name')} | Price:{row.get('lst_price')}"
                        )
                    await update.message.reply_text("\n".join(lines))
            else:
                await update.message.reply_text(f"Price lookup failed: {data.get('error')}")
            return

        if lower_text.startswith("create sale order for "):
            raw = text[len("create sale order for "):].strip()
            await process_sale_order_text(raw, chat_id, update)
            return

        if lower_text.startswith("create lead "):
            raw = text[len("create lead "):].strip()
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 4:
                await update.message.reply_text(
                    "Usage:\ncreate lead Lead Name | Contact Name | Phone | Email"
                )
                return

            payload = {
                "name": parts[0],
                "contact_name": parts[1],
                "phone": parts[2],
                "email": parts[3],
                "description": "Created from Telegram bot prompt",
            }

            response = requests.post(
                f"{BASE_URL}/create-lead",
                json=payload,
                timeout=30
            )
            data = response.json()

            if response.ok and data.get("ok"):
                lead = data.get("lead", {})
                await update.message.reply_text(
                    f"Lead created successfully!\n"
                    f"ID: {data.get('lead_id')}\n"
                    f"Name: {lead.get('name')}\n"
                    f"Contact: {lead.get('contact_name')}\n"
                    f"Phone: {lead.get('phone')}\n"
                    f"Email: {lead.get('email_from')}"
                )
            else:
                await update.message.reply_text(f"Lead creation failed: {data.get('error')}")
            return

        await update.message.reply_text(
            "I didn't understand that.\n\n"
            "Try:\n"
            "test odoo\n"
            "show customers\n"
            "find customer Acme\n"
            "find product Laptop\n"
            "price Laptop\n"
            "create sale order for Acme | Laptop,2,50000 ; Mouse,3,500"
        )

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test_odoo", test_odoo))
    app.add_handler(CommandHandler("debug_info", debug_info))
    app.add_handler(CommandHandler("customers", customers))
    app.add_handler(CommandHandler("create_lead", create_lead))
    app.add_handler(CommandHandler("create_sale_order", create_sale_order))
    app.add_handler(CommandHandler("select_customer", select_customer))
    app.add_handler(CommandHandler("select_product", select_product))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_prompt_handler))

    print("Telegram bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
