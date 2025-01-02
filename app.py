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

        if action == "delete":
            portfolio[chat_id]["holdings"] = [h for h in portfolio[chat_id]["holdings"] if h["symbol"] != symbol]
            save_portfolio(portfolio)
        elif action == "buy":
            if not symbol or quantity <= 0 or price <= 0 or not timestamp:
                return "Invalid input!", 400

            portfolio[chat_id]["holdings"].append({
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "timestamp": timestamp,
                "total_cost": quantity * price
            })
            save_portfolio(portfolio)

        elif action == "sell":
            if not symbol or quantity <= 0 or price <= 0 or not timestamp:
                return "Invalid input!", 400

            for holding in portfolio[chat_id]["holdings"]:
                if holding["symbol"] == symbol:
                    if holding["quantity"] >= quantity:
                        pnl = (price - holding["price"])*quantity
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

    for holding in portfolio_data:
        holding["current_price"] = fetch_current_price(holding["symbol"])
        if holding["current_price"]:
            holding["current_pnl"] = round((holding["current_price"] - holding["price"]) * holding["quantity"], 2)
        else:
            holding["current_pnl"] = 0

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
        </style>
    </head>
    <body>
        <h1 style="text-align:center;">Portfolio Manager</h1>
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
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {% for entry in portfolio %}
                <tr>
                    <td>{{ entry['symbol'] }}</td>
                    <td>{{ entry['quantity'] }}</td>
                    <td>{{ entry['price'] }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                    <td>{{ entry['total_cost'] }}</td>
                    <td>{{ entry['current_price'] }}</td>
                    <td class="{{ 'positive' if entry['current_pnl'] >= 0 else 'negative' }}">{{ entry['current_pnl'] }}</td>
                    <td>
                        <form method="POST">
                            <input type="hidden" name="action" value="delete">
                            <input type="hidden" name="symbol" value="{{ entry['symbol'] }}">
                            <button type="submit">Delete</button>
                        </form>
                    </td>
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
                    <td>{{ entry['quantity'] }}</td>
                    <td>{{ entry['buy_price'] }}</td>
                    <td>{{ entry['sell_price'] }}</td>
                    <td>{{ entry['total_sale'] }}</td>
                    <td>{{ entry['timestamp'] }}</td>
                    <td class="{{ 'positive' if entry['pnl'] >= 0 else 'negative' }}">{{ entry['pnl'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """

    return render_template_string(
        html_template,
        portfolio=portfolio_data,
        transactions=transactions_data
    )

if __name__ == "__main__":
    app.run(debug=True)
