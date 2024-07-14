import sqlite3
import yfinance as yf
import datetime
import matplotlib.pyplot as plt
import logging
import os
from datetime import datetime
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from InquirerPy.base.control import Choice
import requests
import numpy as np
import pandas as pd
from scipy.optimize import minimize

if not os.path.exists('logs'):
    os.makedirs('logs')

log_file = f"logs/portfolio_{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=log_file,
    filemode='w'
)

logger = logging.getLogger(__name__)
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(levelname)s: %(message)s')
# console_handler.setFormatter(formatter)
# logger.addHandler(console_handler)


class Portfolio:
    def __init__(self, db_filename='portfolio.db'):
        try:
            self.conn = sqlite3.connect(db_filename)
            self.create_table()
            logger.info(f"Connected to database: {db_filename}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def create_table(self):
        try:
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
            logger.info("Tables created successfully")
        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}")
            raise

    def add_holding(self, ticker, shares):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if 'currentPrice' in info:
                current_price = info['currentPrice']
                with self.conn:
                    self.conn.execute('''
                        INSERT OR REPLACE INTO holdings (ticker, shares, purchase_price)
                        VALUES (?, COALESCE((SELECT shares FROM holdings WHERE ticker = ?) + ?, ?), ?)
                    ''', (ticker, ticker, shares, shares, current_price))
                    self.conn.execute('''
                        INSERT INTO transactions (ticker, shares, purchase_price, date)
                        VALUES (?, ?, ?, ?)
                    ''', (ticker, shares, current_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    self.conn.commit()
                logger.info(f"Added {shares} shares of {ticker} at ${current_price}")
                print(f"Added {shares} shares of {ticker} at current market price ${current_price}")
            else:
                logger.error(f"Error retrieving current price for {ticker}")
                print(f"Error: Could not retrieve current price for {ticker}")
        except Exception as e:
            logger.error(f"Error adding holding: {e}")
            print(f"Error adding holding: {e}")

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
                    ''', (ticker, -shares, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
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
            dates, prices = zip(*[(datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S"), row[2]) for row in data])
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
            ''', (datetime.now().strftime("%Y-%m-%d"), total_value))
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
            ''', (ticker, amount, datetime.now().strftime("%Y-%m-%d")))
            self.conn.commit()

    def view_dividends(self):
        cursor = self.conn.execute('SELECT ticker, amount, date FROM dividends')
        dividends = cursor.fetchall()
        print("Dividends Received:")
        for dividend in dividends:
            print(dividend)

    def get_stock_news(self, ticker):
        ticker = ticker.upper()
        try:
            stock = yf.Ticker(ticker)
            news = stock.news
            with self.conn:
                for item in news[:5]:
                    self.conn.execute('''
                        INSERT INTO news (ticker, headline, date)
                        VALUES (?, ?, ?)
                    ''', (ticker, item['title'], datetime.fromtimestamp(item['providerPublishTime']).strftime("%Y-%m-%d %H:%M:%S")))
                self.conn.commit()
            logger.info(f"Retrieved and stored news for {ticker}")
            return news
        except Exception as e:
            logger.error(f"Error retrieving news for {ticker}: {e}")
            return []

    def calculate_total_return(self):
            try:
                holdings = self.get_holdings()
                total_cost = 0
                total_current_value = 0
                for ticker, details in holdings.items():
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    if 'currentPrice' in info:
                        current_price = info['currentPrice']
                        shares = details['shares']
                        purchase_price = details['purchase_price']
                        total_cost += shares * purchase_price
                        total_current_value += shares * current_price
                if total_cost > 0:
                    total_return = ((total_current_value - total_cost) / total_cost) * 100
                    logger.info(f"Calculated total return: {total_return:.2f}%")
                    return total_return
                else:
                    logger.warning("No holdings found or total cost is zero")
                    return 0
            except Exception as e:
                logger.error(f"Error calculating total return: {e}")
                return 0

    def convert_currency(self, target_currency):
        api_key = "API_KEY"
        base_url = f"https://api.exchangerate-api.com/v4/latest/USD"

        try:
            response = requests.get(base_url)
            data = response.json()
            
            if target_currency not in data['rates']:
                print(f"Error: {target_currency} is not a valid currency code.")
                return

            exchange_rate = data['rates'][target_currency]
            total_value, _, _, _ = self.get_current_value()
            converted_value = total_value * exchange_rate

            print(f"Portfolio value in {target_currency}: {converted_value:.2f}")
        except requests.RequestException as e:
            print(f"Error fetching exchange rates: {e}")

    def screen_stocks(self, criteria):
        results = []
        
        stock_list = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'FB', 'TSLA', 'JPM', 'JNJ', 'V', 'PG']
        
        for ticker in stock_list:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            meets_criteria = True
            for key, (min_val, max_val) in criteria.items():
                value = info.get(key, None)
                if value is None:
                    meets_criteria = False
                    break
                if min_val is not None and value < min_val:
                    meets_criteria = False
                    break
                if max_val is not None and value > max_val:
                    meets_criteria = False
                    break
            
            if meets_criteria:
                results.append({
                    'Ticker': ticker,
                    'Name': info.get('longName', 'N/A'),
                    'Price': info.get('currentPrice', 'N/A'),
                    'P/E': info.get('trailingPE', 'N/A'),
                    'Dividend Yield': info.get('dividendYield', 'N/A'),
                    'Market Cap': info.get('marketCap', 'N/A')
                })
        
        return results

    def optimize_portfolio(self):
        holdings = self.get_holdings()
        tickers = list(holdings.keys())
        
        data = yf.download(tickers, start="2020-01-01", end=datetime.now().strftime("%Y-%m-%d"))['Adj Close']

        returns = data.pct_change()

        mean_returns = returns.mean()
        cov_matrix = returns.cov()
        
        def portfolio_performance(weights, mean_returns, cov_matrix):
            portfolio_return = np.sum(mean_returns * weights) * 252
            portfolio_std_dev = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights))) * np.sqrt(252)
            return portfolio_std_dev, portfolio_return
        
        constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
        
        bounds = tuple((0, 1) for _ in range(len(tickers)))
        
        init_guess = [1/len(tickers)] * len(tickers)
        
        def neg_sharpe_ratio(weights, mean_returns, cov_matrix, risk_free_rate=0.01):
            p_std_dev, p_ret = portfolio_performance(weights, mean_returns, cov_matrix)
            return -(p_ret - risk_free_rate) / p_std_dev
        
        result = minimize(neg_sharpe_ratio, init_guess, args=(mean_returns, cov_matrix),
                            method='SLSQP', bounds=bounds, constraints=constraints)
        
        print("Optimized Portfolio Allocation:")
        for ticker, weight in zip(tickers, result.x):
            print(f"{ticker}: {weight:.2%}")
        
        std_dev, ret = portfolio_performance(result.x, mean_returns, cov_matrix)
        print(f"Expected annual return: {ret:.2%}")
        print(f"Annual volatility: {std_dev:.2%}")
        print(f"Sharpe Ratio: {(ret - 0.01) / std_dev:.2f}")


def main():
    portfolio = Portfolio()

    while True:
        action = inquirer.select(
            message="Choose an action:",
            choices=[
                Choice("add", name="Add holding"),
                Choice("remove", name="Remove holding"),
                Choice("value", name="Get portfolio value"),
                Choice("plot", name="Plot portfolio"),
                Choice("history", name="Plot transaction history"),
                Choice("export", name="Export to CSV"),
                Choice("import", name="Import from CSV"),
                Choice("compare", name="Compare with benchmark"),
                Choice("set_alert", name="Set price alert"),
                Choice("set_percentage_alert", name="Set percentage alert"),
                Choice("check_alerts", name="Check alerts"),
                Choice("track_performance", name="Track performance"),
                Choice("plot_performance", name="Plot performance"),
                Choice("plot_sector", name="Plot sector distribution"),
                Choice("add_dividend", name="Add dividend"),
                Choice("view_dividends", name="View dividends"),
                Choice("get_news", name="Get stock news"),
                Choice("total_return", name="Calculate total return"),
                Choice("convert_currency", name="Convert portfolio value to another currency"),
                Choice("screen_stocks", name="Screen stocks based on criteria"),
                Choice("optimize_portfolio", name="Optimize portfolio allocation"),
                Choice("exit", name="Exit")
            ]
        ).execute()

        try:
            if action == "add":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                shares = inquirer.number(message="Enter number of shares:").execute()
                portfolio.add_holding(ticker, shares)

            elif action == "remove":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                shares = inquirer.number(message="Enter number of shares to remove:").execute()
                portfolio.remove_holding(ticker, shares)

            elif action == "value":
                total_value, holdings, num_stocks, stock_list = portfolio.get_current_value()
                print(f"Total portfolio value: ${total_value:.2f}")
                print(f"Number of different stocks: {num_stocks}")
                print("Stock list:", stock_list)

            elif action == "plot":
                portfolio.plot_portfolio()

            elif action == "history":
                portfolio.plot_history()

            elif action == "export":
                filename = inquirer.text(message="Enter filename for export (e.g., portfolio.csv):", validate=EmptyInputValidator()).execute()
                portfolio.export_to_csv(filename)

            elif action == "import":
                filename = inquirer.text(message="Enter filename for import (e.g., portfolio.csv):", validate=EmptyInputValidator()).execute()
                portfolio.import_from_csv(filename)

            elif action == "compare":
                benchmark = inquirer.text(message="Enter benchmark ticker (e.g., ^GSPC):", validate=EmptyInputValidator()).execute()
                portfolio.compare_with_benchmark(benchmark)

            elif action == "set_alert":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                threshold = inquirer.number(message="Enter price threshold:").execute()
                direction = inquirer.select(message="Alert when price goes:", choices=["above", "below"]).execute()
                portfolio.set_price_alert(ticker, threshold, direction)

            elif action == "set_percentage_alert":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                percentage = inquirer.number(message="Enter percentage change threshold:").execute()
                portfolio.set_percentage_alert(ticker, percentage)

            elif action == "check_alerts":
                portfolio.check_alerts()

            elif action == "track_performance":
                portfolio.track_performance()
                print("Tracked current portfolio performance.")

            elif action == "plot_performance":
                portfolio.plot_performance()

            elif action == "plot_sector":
                portfolio.plot_sector_distribution()

            elif action == "add_dividend":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                amount = inquirer.number(message="Enter dividend amount:").execute()
                portfolio.add_dividend(ticker, amount)

            elif action == "view_dividends":
                portfolio.view_dividends()

            elif action == "get_news":
                ticker = inquirer.text(message="Enter stock ticker:", validate=EmptyInputValidator()).execute()
                news = portfolio.get_stock_news(ticker)
                for item in news[:5]:
                    print(f"{item['title']} - {datetime.fromtimestamp(item['providerPublishTime']).strftime('%Y-%m-%d %H:%M:%S')}")

            elif action == "total_return":
                total_return = portfolio.calculate_total_return()
                print(f"Total portfolio return: {total_return:.2f}%")

            elif action == "convert_currency":
                target_currency = inquirer.text(
                    message="Enter target currency code (e.g., EUR, GBP):",
                    validate=EmptyInputValidator()
                ).execute()
                portfolio.convert_currency(target_currency)

            elif action == "screen_stocks":
                print("Enter screening criteria:")
                pe_max = inquirer.float(message="Maximum P/E ratio:").execute()
                div_yield_min = inquirer.float(message="Minimum Dividend Yield (as decimal):").execute()
                market_cap_min = inquirer.float(message="Minimum Market Cap (in billions):").execute()
                
                criteria = {
                    'trailingPE': (0, pe_max),
                    'dividendYield': (div_yield_min, None),
                    'marketCap': (market_cap_min * 1e9, None)
                }
                
                results = portfolio.screen_stocks(criteria)
                for stock in results:
                    print(f"{stock['Ticker']} - {stock['Name']}")
                    print(f"  Price: ${stock['Price']:.2f}, P/E: {stock['P/E']:.2f}, Dividend Yield: {stock['Dividend Yield']:.2%}, Market Cap: ${stock['Market Cap']:,.0f}")
                print(f"Found {len(results)} stocks matching criteria.")

            elif action == "optimize_portfolio":
                portfolio.optimize_portfolio()

            elif action == "exit":
                print("Exiting the program.")
                break

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
