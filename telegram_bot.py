import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = "8487140265:AAFywY99oz-bWtRtDWY719LTOinkeTnNfY0"
BASE_URL = "http://127.0.0.1:5000"


# /start command - displays available commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bot is working.\n"
        "Commands:\n"
        "/test_odoo\n"
        "/debug_info\n"
        "/customers\n"
        "/create_lead Lead Name | Contact | Phone | Email\n"
        "/create_sale_order PartnerID | ProductID | Qty | Price"
    )


# /test_odoo command - tests the connection to the Flask API (which interacts with Odoo)
async def test_odoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/test", timeout=30)
        data = response.json()
        print("Telegram <- /test:", data)

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


# /debug_info command - fetches debug information from the Flask API
async def debug_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/debug-info", timeout=30)
        data = response.json()
        print("Telegram <- /debug-info:", data)

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
            await update.message.reply_text(
                f"Debug failed: {data.get('error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


# /customers command - fetches customer information from the Flask API (Odoo)
async def customers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        response = requests.get(f"{BASE_URL}/customers", timeout=30)
        data = response.json()
        print("Telegram <- /customers:", data)

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


# /create_lead command - creates a new lead in Odoo via the Flask API
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
            "description": "Created from Telegram bot"
        }

        print("Telegram -> /create-lead payload:", payload)

        response = requests.post(
            f"{BASE_URL}/create-lead",
            json=payload,
            timeout=30
        )
        data = response.json()

        print("Telegram <- /create-lead status:", response.status_code)
        print("Telegram <- /create-lead response:", data)

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


# /create_sale_order command - creates a new sale order in Odoo via the Flask API
async def create_sale_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        full_text = update.message.text or ""
        prefix = "/create_sale_order"
        raw = full_text[len(prefix):].strip()

        if not raw:
            await update.message.reply_text(
                "Usage:\n/create_sale_order PartnerID | ProductID | Qty | Price"
            )
            return

        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 4:
            await update.message.reply_text(
                "Usage:\n/create_sale_order PartnerID | ProductID | Qty | Price"
            )
            return

        payload = {
            "partner_id": int(parts[0]),
            "product_id": int(parts[1]),
            "qty": float(parts[2]),
            "price": float(parts[3]),
        }

        print("Telegram -> /create-sale-order payload:", payload)

        response = requests.post(
            f"{BASE_URL}/create-sale-order",
            json=payload,
            timeout=30
        )
        data = response.json()

        print("Telegram <- /create-sale-order status:", response.status_code)
        print("Telegram <- /create-sale-order response:", data)

        if response.ok and data.get("ok") is True:
            order = data.get("sale_order", {})
            await update.message.reply_text(
                f"Sale order created successfully!\n"
                f"ID: {data.get('sale_order_id')}\n"
                f"Order: {order.get('name')}\n"
                f"State: {order.get('state')}\n"
                f"Partner: {order.get('partner_id')}"
            )
        else:
            await update.message.reply_text(
                f"Sale order creation failed: {data.get('error')}"
            )
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")


# Main function to start the bot and handle commands
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Registering the command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test_odoo", test_odoo))
    app.add_handler(CommandHandler("debug_info", debug_info))
    app.add_handler(CommandHandler("customers", customers))
    app.add_handler(CommandHandler("create_lead", create_lead))
    app.add_handler(CommandHandler("create_sale_order", create_sale_order))

    print("Telegram bot is running...")
    app.run_polling()


# Run the bot when the script is executed
if __name__ == "__main__":
    main()