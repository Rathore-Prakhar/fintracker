import yfinance as yf
import matplotlib.pyplot as plt
import sqlite3
from InquirerPy import prompt
from InquirerPy.validator import EmptyInputValidator

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

def main():
    action_prompt = {
        "type": "list",
        "name": "action",
        "message": "Choose an action:",
        "choices": ["add", "remove", "value", "plot"]
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

if __name__ == "__main__":
    main()
