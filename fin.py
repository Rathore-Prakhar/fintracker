import sqlite3
import yfinance as yf
import datetime
import matplotlib.pyplot as plt
from PyInquirer import prompt, Validator, ValidationError


class EmptyInputValidator(Validator):
    def validate(self, document):
        if not document.text.strip():
            raise ValidationError(
                message='Input cannot be empty',
                cursor_position=len(document.text)
            )


class Portfolio:
    def __init__(self, db_filename='portfolio.db'):
        self.conn = sqlite3.connect(db_filename)
        self.create_table()

    def create_table(self):
        with self.conn:
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS holdings (
                    ticker TEXT PRIMARY KEY,
                    shares REAL,
                    purchase_price REAL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    shares REAL,
                    purchase_price REAL,
                    date TEXT
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    threshold REAL,
                    direction TEXT
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    percentage_change REAL,
                    last_checked_price REAL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS performance (
                    date TEXT PRIMARY KEY,
                    value REAL
                )
            ''')
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS dividends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    amount REAL,
                    date TEXT
                )
            ''')

    def add_holding(self, ticker, shares, purchase_price):
        ticker = ticker.upper()
        with self.conn:
            self.conn.execute('''
                INSERT OR REPLACE INTO holdings (ticker, shares, purchase_price)
                VALUES (?, COALESCE((SELECT shares FROM holdings WHERE ticker = ?) + ?, ?), ?)
            ''', (ticker, ticker, shares, shares, purchase_price))
            self.conn.execute('''
                INSERT INTO transactions (ticker, shares, purchase_price, date)
                VALUES (?, ?, ?, ?)
            ''', (ticker, shares, purchase_price, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.conn.commit()

    def remove_holding(self, ticker, shares):
        ticker = ticker.upper()
        with self.conn:
            cursor = self.conn.execute('SELECT shares FROM holdings WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            if row:
                current_shares = row[0]
                if shares > current_shares:
                    print(f"Error: You cannot sell more shares than you own ({current_shares} shares).")
                else:
                    new_shares = current_shares - shares
                    if new_shares == 0:
                        self.conn.execute('DELETE FROM holdings WHERE ticker = ?', (ticker,))
                    else:
                        self.conn.execute('''
                            UPDATE holdings
                            SET shares = ?
                            WHERE ticker = ?
                        ''', (new_shares, ticker))
                    self.conn.execute('''
                        INSERT INTO transactions (ticker, shares, purchase_price, date)
                        VALUES (?, ?, ?, ?)
                    ''', (ticker, -shares, 0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    self.conn.commit()
            else:
                print(f"Error: No holdings found for {ticker}.")

    def get_holdings(self):
        cursor = self.conn.execute('SELECT ticker, shares, purchase_price FROM holdings')
        holdings = {}
        for row in cursor.fetchall():
            ticker, shares, purchase_price = row
            holdings[ticker] = {'shares': shares, 'purchase_price': purchase_price}
        return holdings

    def get_current_value(self):
        holdings = self.get_holdings()
        total_value = 0.0
        for ticker, details in holdings.items():
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    total_value += current_price * details['shares']
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")
        return total_value, holdings, len(holdings), list(holdings.keys())

    def plot_portfolio(self):
        holdings = self.get_holdings()
        labels = []
        sizes = []
        for ticker, details in holdings.items():
            labels.append(ticker)
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    sizes.append(current_price * details['shares'])
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")
        plt.pie(sizes, labels=labels, autopct='%1.1f%%')
        plt.axis('equal')
        plt.title("Portfolio Distribution")
        plt.savefig('portfolio.png')
        plt.close()
        print("Portfolio distribution plot saved as 'portfolio.png'")

    def plot_history(self):
        cursor = self.conn.execute('SELECT ticker, shares, purchase_price, date FROM transactions ORDER BY date')
        data = cursor.fetchall()
        if data:
            dates, prices = zip(*[(datetime.datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S"), row[2]) for row in data])
            plt.plot(dates, prices)
            plt.xlabel('Date')
            plt.ylabel('Price')
            plt.title('Transaction History')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig('transaction_history.png')
            plt.close()
            print("Transaction history plot saved as 'transaction_history.png'")
        else:
            print("No transaction data available.")

    def export_to_csv(self, filename):
        cursor = self.conn.execute('SELECT ticker, shares, purchase_price FROM holdings')
        data = cursor.fetchall()
        if data:
            with open(filename, 'w') as f:
                f.write('ticker,shares,purchase_price\n')
                for row in data:
                    f.write(','.join(map(str, row)) + '\n')
            print(f"Portfolio data exported to {filename}")
        else:
            print("No holdings data available to export.")

    def import_from_csv(self, filename):
        with open(filename, 'r') as f:
            next(f)
            for line in f:
                ticker, shares, purchase_price = line.strip().split(',')
                self.add_holding(ticker, float(shares), float(purchase_price))
        print(f"Portfolio data imported from {filename}")

    def compare_with_benchmark(self, benchmark_ticker):
        portfolio_value, _, _, _ = self.get_current_value()
        benchmark = yf.Ticker(benchmark_ticker)
        try:
            info = benchmark.info
            if 'currentPrice' in info:
                benchmark_price = info['currentPrice']
                print(f"Portfolio value: {portfolio_value}")
                print(f"{benchmark_ticker} current price: {benchmark_price}")
                print(f"Performance ratio: {portfolio_value / benchmark_price}")
            else:
                print(f"Error retrieving data for {benchmark_ticker}.")
        except Exception as e:
            print(f"Error retrieving data for {benchmark_ticker}: {e}")

    def set_price_alert(self, ticker, threshold, direction):
        ticker = ticker.upper()
        with self.conn:
            self.conn.execute('''
                INSERT INTO alerts (ticker, threshold, direction)
                VALUES (?, ?, ?)
            ''', (ticker, threshold, direction))
            self.conn.commit()

    def set_percentage_alert(self, ticker, percentage_change):
        ticker = ticker.upper()
        stock = yf.Ticker(ticker)
        try:
            info = stock.info
            if 'currentPrice' in info:
                current_price = info['currentPrice']
                with self.conn:
                    self.conn.execute('''
                        INSERT INTO price_alerts (ticker, percentage_change, last_checked_price)
                        VALUES (?, ?, ?)
                    ''', (ticker, percentage_change, current_price))
                    self.conn.commit()
        except Exception as e:
            print(f"Error retrieving data for {ticker}: {e}")

    def check_alerts(self):
        cursor = self.conn.execute('SELECT ticker, threshold, direction FROM alerts')
        alerts = cursor.fetchall()
        for alert in alerts:
            ticker, threshold, direction = alert
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    if (direction == 'above' and current_price > threshold) or (direction == 'below' and current_price < threshold):
                        print(f"Alert: {ticker} is {'above' if direction == 'above' else 'below'} the threshold of {threshold} with current price {current_price}")
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")

        cursor = self.conn.execute('SELECT ticker, percentage_change, last_checked_price FROM price_alerts')
        price_alerts = cursor.fetchall()
        for alert in price_alerts:
            ticker, percentage_change, last_checked_price = alert
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    change = ((current_price - last_checked_price) / last_checked_price) * 100
                    if abs(change) >= percentage_change:
                        print(f"Alert: {ticker} has changed by {change:.2f}% (Threshold: {percentage_change}%)")
                        with self.conn:
                            self.conn.execute('''
                                UPDATE price_alerts
                                SET last_checked_price = ?
                                WHERE ticker = ?
                            ''', (current_price, ticker))
                            self.conn.commit()
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")

    def track_performance(self):
        total_value, _, _, _ = self.get_current_value()
        with self.conn:
            self.conn.execute('''
                INSERT INTO performance (date, value)
                VALUES (?, ?)
            ''', (datetime.datetime.now().strftime("%Y-%m-%d"), total_value))
            self.conn.commit()

    def plot_performance(self):
        cursor = self.conn.execute('SELECT date, value FROM performance ORDER BY date')
        data = cursor.fetchall()
        if data:
            dates, values = zip(*data)
            plt.plot(dates, values)
            plt.xlabel('Date')
            plt.ylabel('Portfolio Value')
            plt.title('Portfolio Performance Over Time')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig('portfolio_performance.png')
            plt.close()
            print("Portfolio performance plot saved as 'portfolio_performance.png'")
        else:
            print("No performance data available.")

    def plot_sector_distribution(self):
        sectors = {}
        for ticker, details in self.get_holdings().items():
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                sector = info.get('sector', 'Unknown')
                sectors[sector] = sectors.get(sector, 0) + details['shares']
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")

        labels = list(sectors.keys())
        values = list(sectors.values())

        plt.pie(values, labels=labels, autopct='%1.1f%%')
        plt.title("Sector Distribution")
        plt.axis('equal')
        plt.savefig('sector_distribution.png')
        plt.close()
        print("Sector distribution plot saved as 'sector_distribution.png'")

    def add_dividend(self, ticker, amount):
        ticker = ticker.upper()
        with self.conn:
            self.conn.execute('''
                INSERT INTO dividends (ticker, amount, date)
                VALUES (?, ?, ?)
            ''', (ticker, amount, datetime.datetime.now().strftime("%Y-%m-%d")))
            self.conn.commit()

    def view_dividends(self):
        cursor = self.conn.execute('SELECT ticker, amount, date FROM dividends')
        dividends = cursor.fetchall()
        print("Dividends Received:")
        for dividend in dividends:
            print(dividend)


def main():
    action_prompt = {
        "type": "list",
        "name": "action",
        "message": "Choose an action:",
        "choices": ["add", "remove", "value", "plot", "history", "export", "import", "compare", "set alert", "set percentage alert", "check alerts", "track performance", "plot performance", "plot sector distribution", "add dividend", "view dividends"]
    }

    action_answer = prompt(action_prompt)['action']

    portfolio = Portfolio()

    if action_answer == "add":
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        shares_prompt = {
            "type": "number",
            "name": "shares",
            "message": "Enter number of shares:",
        }
        shares_answer = float(prompt(shares_prompt)['shares'])

        price_prompt = {
            "type": "number",
            "name": "price",
            "message": "Enter purchase price:",
        }
        price_answer = float(prompt(price_prompt)['price'])

        portfolio.add_holding(ticker_answer, shares_answer, price_answer)
        print(f"Added {shares_answer} shares of {ticker_answer} at ${price_answer} each.")

    elif action_answer == "remove":
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        shares_prompt = {
            "type": "number",
            "name": "shares",
            "message": "Enter number of shares to remove:",
        }
        shares_answer = float(prompt(shares_prompt)['shares'])

        portfolio.remove_holding(ticker_answer, shares_answer)
        print(f"Removed {shares_answer} shares of {ticker_answer}.")

    elif action_answer == "value":
        total_value, holdings, num_stocks, stock_list = portfolio.get_current_value()
        print(f"Total portfolio value: ${total_value:.2f}")
        print(f"Number of different stocks: {num_stocks}")
        print("Stock list:", stock_list)

    elif action_answer == "plot":
        portfolio.plot_portfolio()

    elif action_answer == "history":
        portfolio.plot_history()

    elif action_answer == "export":
        filename_prompt = {
            "type": "input",
            "name": "filename",
            "message": "Enter filename for export (e.g., portfolio.csv):",
            "validate": EmptyInputValidator()
        }
        filename_answer = prompt(filename_prompt)['filename']
        portfolio.export_to_csv(filename_answer)

    elif action_answer == "import":
        filename_prompt = {
            "type": "input",
            "name": "filename",
            "message": "Enter filename for import (e.g., portfolio.csv):",
            "validate": EmptyInputValidator()
        }
        filename_answer = prompt(filename_prompt)['filename']
        portfolio.import_from_csv(filename_answer)

    elif action_answer == "compare":
        benchmark_prompt = {
            "type": "input",
            "name": "benchmark",
            "message": "Enter benchmark ticker (e.g., ^GSPC):",
            "validate": EmptyInputValidator()
        }
        benchmark_answer = prompt(benchmark_prompt)['benchmark']
        portfolio.compare_with_benchmark(benchmark_answer)

    elif action_answer == "set alert":
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        threshold_prompt = {
            "type": "number",
            "name": "threshold",
            "message": "Enter price threshold:",
        }
        threshold_answer = float(prompt(threshold_prompt)['threshold'])

        direction_prompt = {
            "type": "list",
            "name": "direction",
            "message": "Alert when price goes:",
            "choices": ["above", "below"]
        }
        direction_answer = prompt(direction_prompt)['direction']

        portfolio.set_price_alert(ticker_answer, threshold_answer, direction_answer)
        print(f"Alert set for {ticker_answer} when price is {direction_answer} ${threshold_answer}.")

    elif action_answer == "set percentage alert":
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        percentage_prompt = {
            "type": "number",
            "name": "percentage",
            "message": "Enter percentage change threshold:",
        }
        percentage_answer = float(prompt(percentage_prompt)['percentage'])

        portfolio.set_percentage_alert(ticker_answer, percentage_answer)
        print(f"Percentage alert set for {ticker_answer} at {percentage_answer}% change.")

    elif action_answer == "check alerts":
        portfolio.check_alerts()

    elif action_answer == "track performance":
        portfolio.track_performance()
        print("Tracked current portfolio performance.")

    elif action_answer == "plot performance":
        portfolio.plot_performance()

    elif action_answer == "plot sector distribution":
        portfolio.plot_sector_distribution()

    elif action_answer == "add dividend":
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        amount_prompt = {
            "type": "number",
            "name": "amount",
            "message": "Enter dividend amount:",
        }
        amount_answer = float(prompt(amount_prompt)['amount'])

        portfolio.add_dividend(ticker_answer, amount_answer)
        print(f"Dividend of ${amount_answer} for {ticker_answer} added.")

    elif action_answer == "view dividends":
        portfolio.view_dividends()


if __name__ == "__main__":
    main()
