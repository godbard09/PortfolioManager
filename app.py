from flask import Flask, request, render_template_string
import threading
import os
import json
import ccxt
from datetime import datetime
from collections import defaultdict

PORTFOLIO_FILE = "portfolio.json"

# Load and save portfolio
def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {}

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=4)

portfolio = load_portfolio()
exchange = ccxt.kucoin()

# Fetch symbols dynamically
def fetch_symbols():
    try:
        markets = exchange.load_markets()
        return list(markets.keys())  # Fetch all symbols dynamically from the exchange
    except Exception as e:
        print(f"Error fetching symbols: {e}")
        return []  # Return an empty list if fetching fails

# Fetch current price
def fetch_current_price(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Error fetching current price for {symbol}: {e}")
        return None

# Flask app
app = Flask(__name__)

@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio_default():
    chat_id = "default_user"
    if chat_id not in portfolio:
        portfolio[chat_id] = {"holdings": [], "transactions": []}
        save_portfolio(portfolio)
    return portfolio_web(chat_id)

@app.route('/portfolio/<chat_id>', methods=['GET', 'POST'])
def portfolio_web(chat_id):
    if chat_id not in portfolio:
        portfolio[chat_id] = {"holdings": [], "transactions": []}
        save_portfolio(portfolio)

    if request.method == 'POST':
        action = request.form.get('action')
        symbol = request.form.get('symbol')
        quantity = float(request.form.get('quantity', 0))
        price = float(request.form.get('price', 0))
        timestamp = request.form.get('timestamp')

        if not symbol or quantity <= 0 or price <= 0 or not timestamp:
            return "Invalid input!", 400

        if action == "buy":
            portfolio[chat_id]["holdings"].append({
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
                "total_cost": quantity * price
            })
            save_portfolio(portfolio)

        elif action == "sell":
            for holding in portfolio[chat_id]["holdings"]:
                if holding["symbol"] == symbol:
                    if holding["quantity"] >= quantity:
                        pnl = (price - holding["price"]) * quantity
                        portfolio[chat_id]["transactions"].append({
                            "symbol": symbol,
                            "quantity": quantity,
                            "buy_price": holding["price"],
                            "sell_price": price,
                            "pnl": pnl,
                            "timestamp": timestamp,
                            "total_sale": quantity * price
                        })
                        holding["quantity"] -= quantity
                        if holding["quantity"] == 0:
                            portfolio[chat_id]["holdings"].remove(holding)
                        save_portfolio(portfolio)
                        break
            else:
                return "Not enough holdings to sell!", 400

    portfolio_data = portfolio[chat_id]["holdings"]
    transactions_data = portfolio[chat_id]["transactions"]
    available_symbols = fetch_symbols()

    # Calculate current price and P&L for holdings
    for holding in portfolio_data:
        current_price = fetch_current_price(holding["symbol"])
        holding["current_price"] = current_price
        holding["current_pnl"] = round((current_price - holding["price"]) * holding["quantity"], 2) if current_price else 0

    # Calculate P&L by unit and symbol
    pnl_table = []
    for holding in portfolio_data:
        pnl_table.append({
            "symbol": holding["symbol"],
            "quantity": holding["quantity"],
            "current_pnl": holding["current_pnl"],
            "unit": holding["symbol"].split('/')[1]
        })

    # Render template
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portfolio Manager</title>
        <style>
            table {
                width: 90%;
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
            .positive {
                color: green;
            }
            .negative {
                color: red;
            }
            .summary {
                margin: 20px auto;
                text-align: center;
                font-size: 1.2em;
            }
            form {
                margin: 20px auto;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <h1 style="text-align:center;">Portfolio Manager</h1>
        <h2 style="text-align:center;">Total P&L by Symbol</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Remaining Quantity</th>
                    <th>Current P&L</th>
                </tr>
            </thead>
            <tbody>
                {% for row in pnl_table %}
                <tr>
                    <td>{{ row['symbol'] }}</td>
                    <td>{{ row['quantity'] }} {{ row['symbol'].split('/')[0] }}</td>
                    <td class="{{ 'positive' if row['current_pnl'] >= 0 else 'negative' }}">{{ row['current_pnl'] }} {{ row['unit'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        <h2 style="text-align:center;">Holdings</h2>
        <table>
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Quantity</th>
                    <th>Buy Price</th>
                    <th>Buy Time</th>
                    <th>Total Cost</th>
                    <th>Current Price</th>
                    <th>Current P&L</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in portfolio %}
                <tr>
                    <td>{{ entry['symbol'] }}</td>
                    <td>{{ entry['quantity'] }} {{ entry['symbol'].split('/')[0] }}</td>
                    <td>{{ entry['price'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                    <td>{{ entry['total_cost'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td>{{ entry['current_price'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td class="{{ 'positive' if entry['current_pnl'] >= 0 else 'negative' }}">{{ entry['current_pnl'] }} {{ entry['symbol'].split('/')[1] }}</td>
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
                    <th>Total Sale</th>
                    <th>Sell Time</th>
                    <th>P&L</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in transactions %}
                <tr>
                    <td>{{ entry['symbol'] }}</td>
                    <td>{{ entry['quantity'] }} {{ entry['symbol'].split('/')[0] }}</td>
                    <td>{{ entry['buy_price'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td>{{ entry['sell_price'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td>{{ entry['total_sale'] }} {{ entry['symbol'].split('/')[1] }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                    <td class="{{ 'positive' if entry['pnl'] >= 0 else 'negative' }}">{{ entry['pnl'] }} {{ entry['symbol'].split('/')[1] }}</td>
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
            <label for="timestamp">Time (UTC+7):</label>
            <input type="date" id="timestamp" name="timestamp" required>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(
        html_template,
        portfolio=portfolio_data,
        transactions=transactions_data,
        pnl_table=pnl_table,
        available_symbols=available_symbols
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
