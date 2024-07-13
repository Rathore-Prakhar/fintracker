import argparse
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import json
import sqlite3

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
                    shares REAL
                )
            ''')

    def add_position(self, ticker, shares):
        with self.conn:
            self.conn.execute('''
                INSERT INTO holdings (ticker, shares)
                VALUES (?, ?)
                ON CONFLICT(ticker) DO UPDATE SET shares = shares + excluded.shares
            ''', (ticker, shares))

    def remove_position(self, ticker, shares):
        with self.conn:
            self.conn.execute('''
                UPDATE holdings SET shares = shares - ?
                WHERE ticker = ?
            ''', (shares, ticker))
            self.conn.execute('''
                DELETE FROM holdings WHERE shares <= 0
            ''')

    def get_current_value(self):
        total_value = 0
        for ticker, shares in self.get_holdings().items():
            stock = yf.Ticker(ticker)
            current_price = stock.info['currentPrice']
            total_value += current_price * shares
        return total_value

    def plot_portfolio_composition(self):
        values = []
        labels = []
        for ticker, shares in self.get_holdings().items():
            stock = yf.Ticker(ticker)
            current_price = stock.info['currentPrice']
            value = current_price * shares
            values.append(value)
            labels.append(ticker)

        plt.pie(values, labels=labels, autopct='%1.1f%%')
        plt.title("Portfolio Composition")
        plt.axis('equal')
        plt.savefig('portfolio_composition.png')
        plt.close()

    def get_holdings(self):
        cursor = self.conn.execute('SELECT ticker, shares FROM holdings')
        return {row[0]: row[1] for row in cursor}

    def save_portfolio(self, filename):
        holdings = self.get_holdings()
        with open(filename, 'w') as f:
            json.dump(holdings, f)

    def load_portfolio(self, filename):
        with open(filename, 'r') as f:
            holdings = json.load(f)
        with self.conn:
            self.conn.execute('DELETE FROM holdings')
            for ticker, shares in holdings.items():
                self.add_position(ticker, shares)

def main():
    parser = argparse.ArgumentParser(description="Portfolio Tracker CLI")
    parser.add_argument('action', choices=['add', 'remove', 'value', 'plot', 'save', 'load'])
    parser.add_argument('--ticker', help="Stock ticker symbol")
    parser.add_argument('--shares', type=float, help="Number of shares")
    parser.add_argument('--file', help="Filename for save/load")
    parser.add_argument('--db', default='portfolio.db', help="Database file")

    args = parser.parse_args()

    portfolio = Portfolio(args.db)

    if args.action == 'add':
        portfolio.add_position(args.ticker, args.shares)
        print(f"Added {args.shares} shares of {args.ticker}")
    elif args.action == 'remove':
        portfolio.remove_position(args.ticker, args.shares)
        print(f"Removed {args.shares} shares of {args.ticker}")
    elif args.action == 'value':
        print(f"Current portfolio value: ${portfolio.get_current_value():.2f}")
    elif args.action == 'plot':
        portfolio.plot_portfolio_composition()
        print("Portfolio composition plot saved as 'portfolio_composition.png'")
    elif args.action == 'save':
        portfolio.save_portfolio(args.file)
        print(f"Portfolio saved to {args.file}")
    elif args.action == 'load':
        portfolio.load_portfolio(args.file)
        print(f"Portfolio loaded from {args.file}")

if __name__ == "__main__":
    main()
