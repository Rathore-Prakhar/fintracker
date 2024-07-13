import argparse
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import json

class Portfolio:
    def __init__(self):
        self.holdings = {}

    def add_position(self, ticker, shares):
        if ticker in self.holdings:
            self.holdings[ticker] += shares
        else:
            self.holdings[ticker] = shares

    def remove_position(self, ticker, shares):
        if ticker in self.holdings:
            self.holdings[ticker] -= shares
            if self.holdings[ticker] <= 0:
                del self.holdings[ticker]

    def get_current_value(self):
        total_value = 0
        for ticker, shares in self.holdings.items():
            stock = yf.Ticker(ticker)
            current_price = stock.info['regularMarketPrice']
            total_value += current_price * shares
        return total_value

    def plot_portfolio_composition(self):
        values = []
        labels = []
        for ticker, shares in self.holdings.items():
            stock = yf.Ticker(ticker)
            current_price = stock.info['regularMarketPrice']
            value = current_price * shares
            values.append(value)
            labels.append(ticker)

        plt.pie(values, labels=labels, autopct='%1.1f%%')
        plt.title("Portfolio Composition")
        plt.axis('equal')
        plt.savefig('portfolio_composition.png')
        plt.close()

    def save_portfolio(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.holdings, f)

    def load_portfolio(self, filename):
        with open(filename, 'r') as f:
            self.holdings = json.load(f)

def main():
    parser = argparse.ArgumentParser(description="Portfolio Tracker CLI")
    parser.add_argument('action', choices=['add', 'remove', 'value', 'plot', 'save', 'load'])
    parser.add_argument('--ticker', help="Stock ticker symbol")
    parser.add_argument('--shares', type=float, help="Number of shares")
    parser.add_argument('--file', help="Filename for save/load")

    args = parser.parse_args()

    portfolio = Portfolio()

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
