from flask import Flask, jsonify, request
import requests
import json
from config import ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_API_KEY

app = Flask(__name__)
HEADERS = {"Content-Type": "application/json"}

# Function to send requests to Odoo
def odoo_post(payload):
    print("\n=== ODOO REQUEST ===")
    print(json.dumps(payload, indent=2))

    response = requests.post(
        ODOO_URL,
        json=payload,
        headers=HEADERS,
        timeout=30,
    )

    print("=== HTTP STATUS ===")
    print(response.status_code)
    print("=== RAW ODOO RESPONSE ===")
    print(response.text)

    response.raise_for_status()

    result = response.json()

    print("=== ODOO RESPONSE JSON ===")
    print(json.dumps(result, indent=2))

    # JSON-RPC business error from Odoo
    if "error" in result:
        err = result["error"]
        message = (
            err.get("data", {}).get("message")
            or err.get("message")
            or str(err)
        )
        raise Exception(message)

    if "result" not in result:
        raise Exception("Odoo response missing 'result'")

    return result["result"]

# Login function to authenticate and retrieve UID
def login():
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "common",
            "method": "login",
            "args": [ODOO_DB, ODOO_USERNAME, ODOO_API_KEY],
        },
        "id": 1,
    }

    uid = odoo_post(payload)
    if not uid:
        raise Exception("No UID returned from Odoo login")
    return uid

# Function to execute methods on Odoo models
def execute_kw(uid, model, method, args=None, kwargs=None, request_id=2):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}

    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "service": "object",
            "method": "execute_kw",
            "args": [
                ODOO_DB,
                uid,
                ODOO_API_KEY,
                model,
                method,
                args,
                kwargs,
            ],
        },
        "id": request_id,
    }

    return odoo_post(payload)

# Route to test Odoo connection
@app.route("/test", methods=["GET"])
def test_connection():
    try:
        uid = login()
        return jsonify({"ok": True, "message": "Connected successfully", "uid": uid})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Route to fetch customers
@app.route("/customers", methods=["GET"])
def customers():
    try:
        uid = login()
        result = execute_kw(
            uid,
            "res.partner",
            "search_read",
            args=[[["is_company", "=", True]]],
            kwargs={"fields": ["id", "name", "phone", "email"], "limit": 5},
            request_id=2,
        )
        return jsonify({"ok": True, "customers": result or []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Route to fetch debug info
@app.route("/debug-info", methods=["GET"])
def debug_info():
    try:
        uid = login()

        user_data = execute_kw(
            uid,
            "res.users",
            "read",
            args=[[uid]],
            kwargs={"fields": ["id", "name", "login", "company_id"]},
            request_id=90,
        )

        return jsonify({
            "ok": True,
            "db": ODOO_DB,
            "url": ODOO_URL,
            "uid": uid,
            "user": user_data[0] if user_data else {}
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Search customer by name
@app.route("/find-customer", methods=["GET"])
def find_customer():
    try:
        query = (request.args.get("q") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "Missing query"}), 400

        uid = login()
        result = execute_kw(
            uid,
            "res.partner",
            "search_read",
            args=[[["name", "ilike", query]]],
            kwargs={"fields": ["id", "name", "phone", "email"], "limit": 5},
            request_id=50,
        )

        return jsonify({"ok": True, "customers": result or []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Search product by name
@app.route("/find-product", methods=["GET"])
def find_product():
    try:
        query = (request.args.get("q") or "").strip()
        if not query:
            return jsonify({"ok": False, "error": "Missing query"}), 400

        uid = login()
        result = execute_kw(
            uid,
            "product.product",
            "search_read",
            args=[[["name", "ilike", query]]],
            kwargs={"fields": ["id", "name", "lst_price"], "limit": 5},
            request_id=51,
        )

        return jsonify({"ok": True, "products": result or []})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Route to create a new lead
@app.route("/create-lead", methods=["POST"])
def create_lead():
    try:
        print("\n=== FLASK /create-lead REQUEST ===")
        print("Method:", request.method)
        print("Content-Type:", request.content_type)
        print("Raw body:", request.get_data(as_text=True))

        if not request.is_json:
            return jsonify({"ok": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        print("Parsed JSON:", data)

        name = (data.get("name") or "").strip()
        contact_name = (data.get("contact_name") or "").strip()
        phone = (data.get("phone") or "").strip()
        email = (data.get("email") or "").strip()
        description = (data.get("description") or "").strip()

        if not name:
            return jsonify({"ok": False, "error": "Missing field: name"}), 400

        uid = login()

        lead_vals = {
            "name": name,
            "contact_name": contact_name or False,
            "phone": phone or False,
            "email_from": email or False,
            "description": description or False,
        }

        real_lead_id = execute_kw(
            uid,
            "crm.lead",
            "create",
            args=[lead_vals],
            kwargs={},
            request_id=10,
        )

        if not isinstance(real_lead_id, int):
            return jsonify({
                "ok": False,
                "error": f"Unexpected create result from Odoo: {real_lead_id}"
            }), 500

        lead_data = execute_kw(
            uid,
            "crm.lead",
            "read",
            args=[[real_lead_id]],
            kwargs={"fields": ["id", "name", "contact_name", "phone", "email_from", "description"]},
            request_id=11,
        )

        if not lead_data:
            return jsonify({
                "ok": False,
                "error": f"Odoo returned lead ID {real_lead_id} but the record could not be read back"
            }), 500

        return jsonify({
            "ok": True,
            "lead_id": real_lead_id,
            "lead": lead_data[0],
            "message": "Lead created successfully"
        }), 201

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# Route to create a sale order
@app.route("/create-sale-order", methods=["POST"])
def create_sale_order():
    try:
        print("\n=== FLASK /create-sale-order REQUEST ===")
        print("Method:", request.method)
        print("Content-Type:", request.content_type)
        print("Raw body:", request.get_data(as_text=True))

        if not request.is_json:
            return jsonify({"ok": False, "error": "Request must be JSON"}), 400

        data = request.get_json()
        print("Parsed JSON:", data)

        partner_id = data.get("partner_id")
        lines = data.get("lines", [])

        if partner_id is None:
            return jsonify({"ok": False, "error": "Missing field: partner_id"}), 400

        if not lines or not isinstance(lines, list):
            return jsonify({"ok": False, "error": "Missing or invalid field: lines"}), 400

        order_lines = []
        for line in lines:
            product_id = line.get("product_id")
            qty = line.get("qty")
            price = line.get("price")

            if product_id is None:
                return jsonify({"ok": False, "error": "Missing field: product_id in order line"}), 400
            if qty is None:
                return jsonify({"ok": False, "error": "Missing field: qty in order line"}), 400
            if price is None:
                return jsonify({"ok": False, "error": "Missing field: price in order line"}), 400

            order_lines.append([
                0, 0, {
                    "product_id": int(product_id),
                    "product_uom_qty": float(qty),
                    "price_unit": float(price),
                }
            ])

        uid = login()

        order_vals = {
            "partner_id": int(partner_id),
            "order_line": order_lines
        }

        print("Order values being sent to Odoo:")
        print(json.dumps(order_vals, indent=2))

        real_order_id = execute_kw(
            uid,
            "sale.order",
            "create",
            args=[order_vals],
            kwargs={},
            request_id=20,
        )

        if not isinstance(real_order_id, int):
            return jsonify({
                "ok": False,
                "error": f"Unexpected sale.order create result from Odoo: {real_order_id}"
            }), 500

        order_data = execute_kw(
            uid,
            "sale.order",
            "read",
            args=[[real_order_id]],
            kwargs={"fields": ["id", "name", "partner_id", "state"]},
            request_id=21,
        )

        if not order_data:
            return jsonify({
                "ok": False,
                "error": f"Odoo returned sale order ID {real_order_id} but record not found"
            }), 500

        return jsonify({
            "ok": True,
            "sale_order_id": real_order_id,
            "sale_order": order_data[0],
            "message": "Sale order created successfully"
        }), 201

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
