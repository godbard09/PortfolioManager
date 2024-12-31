from flask import Flask, request, jsonify, render_template_string
import threading
import os
import json
import ccxt
from datetime import datetime

# Tệp lưu trữ danh mục đầu tư
PORTFOLIO_FILE = "portfolio.json"

# Tải và lưu danh mục đầu tư
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {}

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=4)

# Danh mục đầu tư
portfolio = load_portfolio()

# Sàn giao dịch KuCoin
exchange = ccxt.kucoin()

# Lấy danh sách các cặp giao dịch
def fetch_symbols():
    try:
        markets = exchange.load_markets()
        return list(markets.keys())
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []

# Flask App
app = Flask(__name__)

@app.route('/portfolio/<chat_id>', methods=['GET', 'POST'])
def portfolio_web(chat_id):
    # Tải danh mục đầu tư cho người dùng
    if chat_id not in portfolio:
        portfolio[chat_id] = {"holdings": [], "transactions": []}
        save_portfolio(portfolio)

    if request.method == 'POST':
        # Xử lý thêm hoặc chỉnh sửa giao dịch
        action = request.form.get('action')
        symbol = request.form.get('symbol')
        quantity = float(request.form.get('quantity', 0))
        price = float(request.form.get('price', 0))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not symbol or quantity <= 0 or price <= 0:
            return "Invalid input!", 400

        if action == "buy":
            # Thêm giao dịch mua
            portfolio[chat_id]["holdings"].append({"symbol": symbol, "quantity": quantity, "price": price, "timestamp": timestamp})
            save_portfolio(portfolio)

        elif action == "sell":
            # Tìm giao dịch tương ứng để tính lãi/lỗ
            for holding in portfolio[chat_id]["holdings"]:
                if holding["symbol"] == symbol:
                    if holding["quantity"] >= quantity:
                        # Tính toán lãi/lỗ
                        pnl = (price - holding["price"]) * quantity
                        portfolio[chat_id]["transactions"].append({
                            "symbol": symbol,
                            "quantity": quantity,
                            "buy_price": holding["price"],
                            "sell_price": price,
                            "pnl": pnl,
                            "timestamp": timestamp
                        })
                        # Cập nhật số lượng còn lại
                        holding["quantity"] -= quantity
                        if holding["quantity"] == 0:
                            portfolio[chat_id]["holdings"].remove(holding)
                        save_portfolio(portfolio)
                        break
            else:
                return "Not enough holdings to sell!", 400

    # Tính toán tổng P&L từ tất cả giao dịch
    total_pnl = sum(t["pnl"] for t in portfolio[chat_id]["transactions"])

    # Hiển thị danh mục hiện tại
    portfolio_data = portfolio[chat_id]["holdings"]
    transactions_data = portfolio[chat_id]["transactions"]

    # Lấy danh sách các cặp giao dịch
    available_symbols = fetch_symbols()

    # Giao diện HTML
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Manager</title>
        <style>
            table {
                width: 80%;
                margin: 20px auto;
                border-collapse: collapse;
            }
            th, td {
                border: 1px solid black;
                padding: 10px;
                text-align: center;
            }
            th {
                background-color: #f2f2f2;
            }
            form {
                margin: 20px auto;
                text-align: center;
            }
            .summary {
                margin: 20px auto;
                text-align: center;
                font-size: 1.2em;
            }
        </style>
    </head>
    <body>
        <h1 style="text-align:center;">Portfolio Manager</h1>
        <div class="summary">
            <p><b>Total P&L:</b> {{ total_pnl | round(2) }} USD</p>
        </div>
        <h2 style="text-align:center;">Holdings</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Buy Price</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in portfolio %}
                <tr>
                    <td>{{ entry['symbol'] }}</td>
                    <td>{{ entry['quantity'] }}</td>
                    <td>{{ entry['price'] }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <h2 style="text-align:center;">Transactions</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Buy Price</th>
                    <th>Sell Price</th>
                    <th>P&L</th>
                    <th>Timestamp</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in transactions %}
                <tr>
                    <td>{{ entry['symbol'] }}</td>
                    <td>{{ entry['quantity'] }}</td>
                    <td>{{ entry['buy_price'] }}</td>
                    <td>{{ entry['sell_price'] }}</td>
                    <td>{{ entry['pnl'] | round(2) }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <form method="POST">
            <h3>Buy or Sell</h3>
            <label for="action">Action:</label>
            <select id="action" name="action">
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
            </select>
            <label for="symbol">Symbol:</label>
            <select id="symbol" name="symbol" required>
                {% for symbol in available_symbols %}
                <option value="{{ symbol }}">{{ symbol }}</option>
                {% endfor %}
            </select>
            <label for="quantity">Quantity:</label>
            <input type="number" id="quantity" name="quantity" step="0.01" required>
            <label for="price">Price:</label>
            <input type="number" id="price" name="price" step="0.01" required>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(
        html_template,
        portfolio=portfolio_data,
        transactions=transactions_data,
        available_symbols=available_symbols,
        total_pnl=total_pnl
    )

def run_flask():
    """Chạy Flask server trên luồng riêng."""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# Chạy Flask server trong luồng riêng
threading.Thread(target=run_flask).start()
