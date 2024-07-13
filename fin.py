import yfinance as yf
import matplotlib.pyplot as plt
import sqlite3
from InquirerPy import prompt
from InquirerPy.validator import EmptyInputValidator
import pandas as pd
import datetime
import numpy as np

class Portfolio:
    def __init__(self, db_file='portfolio.db'):
        self.db_file = db_file
        self.conn = sqlite3.connect(self.db_file)
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

    def add_position(self, ticker, shares, purchase_price):
        ticker = ticker.upper()
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute('SELECT shares FROM holdings WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            if row:
                current_shares = row[0]
                cursor.execute('''
                    UPDATE holdings SET shares = ?, purchase_price = ?
                    WHERE ticker = ?
                ''', (current_shares + shares, purchase_price, ticker))
            else:
                cursor.execute('''
                    INSERT INTO holdings (ticker, shares, purchase_price)
                    VALUES (?, ?, ?)
                ''', (ticker, shares, purchase_price))
            cursor.execute('''
                INSERT INTO transactions (ticker, shares, purchase_price, date)
                VALUES (?, ?, ?, ?)
            ''', (ticker, shares, purchase_price, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.conn.commit()

    def remove_position(self, ticker, shares):
        ticker = ticker.upper()
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute('SELECT shares FROM holdings WHERE ticker = ?', (ticker,))
            row = cursor.fetchone()
            if row:
                current_shares = row[0]
                new_shares = current_shares - shares
                if new_shares > 0:
                    cursor.execute('''
                        UPDATE holdings SET shares = ?
                        WHERE ticker = ?
                    ''', (new_shares, ticker))
                else:
                    cursor.execute('DELETE FROM holdings WHERE ticker = ?', (ticker,))
                cursor.execute('''
                    INSERT INTO transactions (ticker, shares, purchase_price, date)
                    VALUES (?, ?, ?, ?)
                ''', (ticker, -shares, row[1], datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                self.conn.commit()

    def get_current_value(self):
        total_value = 0
        total_purchase_value = 0
        holdings = self.get_holdings()
        for ticker, details in holdings.items():
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    total_value += current_price * details['shares']
                    total_purchase_value += details['purchase_price'] * details['shares']
                else:
                    print(f"Warning: Could not retrieve market price for {ticker}")
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")
        total_change_value = total_value - total_purchase_value
        total_change_percentage = (total_change_value / total_purchase_value) * 100 if total_purchase_value != 0 else 0
        return total_value, total_change_value, total_change_percentage, holdings

    def get_holdings(self):
        cursor = self.conn.execute('SELECT ticker, shares, purchase_price FROM holdings')
        return {row[0]: {'shares': row[1], 'purchase_price': row[2]} for row in cursor}

    def plot_portfolio_composition(self):
        values = []
        labels = []
        for ticker, details in self.get_holdings().items():
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    value = current_price * details['shares']
                    values.append(value)
                    labels.append(ticker)
                else:
                    print(f"Warning: Could not retrieve market price for {ticker}")
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")

        plt.pie(values, labels=labels, autopct='%1.1f%%')
        plt.title("Portfolio Composition")
        plt.axis('equal')
        plt.savefig('portfolio_composition.png')
        plt.close()

    def view_transaction_history(self):
        cursor = self.conn.execute('SELECT ticker, shares, purchase_price, date FROM transactions')
        transactions = cursor.fetchall()
        print("Transaction History:")
        for transaction in transactions:
            print(transaction)

    def export_portfolio(self, filename):
        cursor = self.conn.execute('SELECT * FROM holdings')
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['Ticker', 'Shares', 'Purchase Price'])
        df.to_csv(filename, index=False)
        print(f"Portfolio exported to {filename}")

    def import_portfolio(self, filename):
        df = pd.read_csv(filename)
        with self.conn:
            self.conn.execute('DELETE FROM holdings')
            for _, row in df.iterrows():
                self.conn.execute('''
                    INSERT INTO holdings (ticker, shares, purchase_price)
                    VALUES (?, ?, ?)
                ''', (row['Ticker'], row['Shares'], row['Purchase Price']))
            self.conn.commit()
        print(f"Portfolio imported from {filename}")

    def compare_with_index(self, index_ticker):
        _, _, _, holdings = self.get_current_value()
        tickers = list(holdings.keys())
        tickers.append(index_ticker)
        
        # Calculate the date range for the last month
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=30)
        
        prices = yf.download(tickers, start=start_date, end=end_date)['Adj Close']

        index_prices = prices[index_ticker]
        portfolio_prices = prices.drop(columns=index_ticker)
        index_start_price = index_prices.iloc[0]
        index_end_price = index_prices.iloc[-1]
        index_return = (index_end_price - index_start_price) / index_start_price * 100

        portfolio_start_value = (portfolio_prices.iloc[0] * [holdings[ticker]['shares'] for ticker in portfolio_prices.columns]).sum()
        portfolio_end_value = (portfolio_prices.iloc[-1] * [holdings[ticker]['shares'] for ticker in portfolio_prices.columns]).sum()
        portfolio_return = (portfolio_end_value - portfolio_start_value) / portfolio_start_value * 100

        print(f"Portfolio return over the last month: {portfolio_return:.2f}%")
        print(f"Index ({index_ticker}) return over the last month: {index_return:.2f}%")

        plt.figure(figsize=(10, 6))
        plt.plot((portfolio_prices * [holdings[ticker]['shares'] for ticker in portfolio_prices.columns]).sum(axis=1) / portfolio_start_value, label='Portfolio')
        plt.plot(index_prices / index_start_price, label=index_ticker)
        plt.legend()
        plt.title('Portfolio vs. Index (Last Month)')
        plt.xlabel('Date')
        plt.ylabel('Normalized Value')
        plt.savefig('portfolio_vs_index.png')
        plt.close()
        print("Portfolio comparison with index plot saved as 'portfolio_vs_index.png'")

def main():
    action_prompt = {
        "type": "list",
        "name": "action",
        "message": "Choose an action:",
        "choices": ["add", "remove", "value", "plot", "history", "export", "import", "compare"]
    }

    action_answer = prompt(action_prompt)['action']

    portfolio = Portfolio()

    if action_answer in ["add", "remove"]:
        ticker_prompt = {
            "type": "input",
            "name": "ticker",
            "message": "Enter stock ticker:",
            "validate": EmptyInputValidator()
        }
        ticker_answer = prompt(ticker_prompt)['ticker'].upper()

        stock = yf.Ticker(ticker_answer)
        try:
            info = stock.info
            if info.get('currentPrice') is not None:
                company_name = info.get('shortName')
                current_price = info['currentPrice']
                print(f"Company: {company_name}")
                print(f"Current Price: ${current_price:.2f}")

                confirm_prompt = {
                    "type": "confirm",
                    "name": "confirm",
                    "message": "Do you want to proceed with this transaction?",
                    "default": True
                }
                confirm_answer = prompt(confirm_prompt)['confirm']

                if not confirm_answer:
                    print("Transaction cancelled.")
                    return

                shares_prompt = {
                    "type": "number",
                    "name": "shares",
                    "message": "Enter number of shares:",
                    "validate": lambda result: float(result) > 0
                }
                shares_answer = float(prompt(shares_prompt)['shares'])

                if action_answer == "add":
                    portfolio.add_position(ticker_answer, shares_answer, current_price)
                    print(f"Added {shares_answer} shares of {ticker_answer} worth ${shares_answer * current_price:.2f}")
                elif action_answer == "remove":
                    portfolio.remove_position(ticker_answer, shares_answer)
                    print(f"Removed {shares_answer} shares of {ticker_answer}")
            else:
                print(f"Invalid ticker or could not retrieve data for {ticker_answer}")
        except Exception as e:
            print(f"Error retrieving data for {ticker_answer}: {e}")

    elif action_answer == "value":
        total_value, total_change_value, total_change_percentage, holdings = portfolio.get_current_value()
        print(f"Current portfolio value: ${total_value:.2f}")
        print(f"Total change in value: ${total_change_value:.2f}")
        print(f"Total percentage change: {total_change_percentage:.2f}%")
        print("Holdings breakdown:")
        for ticker, details in holdings.items():
            stock = yf.Ticker(ticker)
            try:
                info = stock.info
                if 'currentPrice' in info:
                    current_price = info['currentPrice']
                    change = (current_price - details['purchase_price']) / details['purchase_price'] * 100
                    print(f"{ticker}: {details['shares']} shares, Current Price: ${current_price:.2f}, Purchase Price: ${details['purchase_price']:.2f}, Change: {change:.2f}%")
                else:
                    print(f"Warning: Could not retrieve market price for {ticker}")
            except Exception as e:
                print(f"Error retrieving data for {ticker}: {e}")

    elif action_answer == "plot":
        portfolio.plot_portfolio_composition()
        print("Portfolio composition plot saved as 'portfolio_composition.png'")

    elif action_answer == "history":
        portfolio.view_transaction_history()

    elif action_answer == "export":
        filename_prompt = {
            "type": "input",
            "name": "filename",
            "message": "Enter filename to export to (e.g., portfolio.csv):",
            "validate": EmptyInputValidator()
        }
        filename_answer = prompt(filename_prompt)['filename']
        portfolio.export_portfolio(filename_answer)

    elif action_answer == "import":
        filename_prompt = {
            "type": "input",
            "name": "filename",
            "message": "Enter filename to import from (e.g., portfolio.csv):",
            "validate": EmptyInputValidator()
        }
        filename_answer = prompt(filename_prompt)['filename']
        portfolio.import_portfolio(filename_answer)

    elif action_answer == "compare":
        index_prompt = {
            "type": "input",
            "name": "index_ticker",
            "message": "Enter index ticker (e.g., ^GSPC for S&P 500):",
            "validate": EmptyInputValidator()
        }
        index_answer = prompt(index_prompt)['index_ticker'].upper()
        portfolio.compare_with_index(index_answer)

if __name__ == "__main__":
    main()
