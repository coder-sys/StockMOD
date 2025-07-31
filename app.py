from flask import Flask, render_template, jsonify
import pandas as pd
import json
import os
from main import main as run_analysis, load_history, summarize_market

app = Flask(__name__)

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Run the analysis to get fresh data
        run_analysis()
        
        # Load the CSV data
        if os.path.exists('sentiment_snapshot.csv'):
            df = pd.read_csv('sentiment_snapshot.csv')
            
            # Clean the data - remove rows that might be part of the summary
            df = df.dropna(subset=['Ticker'])
            
            # Get market summary
            summary = summarize_market(df)
            
            # Convert dataframe to list of dictionaries for Jinja2
            data = df.head(50).to_dict('records')
            
            return render_template('index.html', 
                                 data=data, 
                                 summary=summary,
                                 total_tickers=len(df))
        else:
            return render_template('index.html', 
                                 data=[], 
                                 summary={},
                                 total_tickers=0)
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/api/refresh')
def refresh_data():
    """API endpoint to refresh data"""
    try:
        run_analysis()
        return jsonify({"status": "success", "message": "Data refreshed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/data')
def get_data():
    """API endpoint to get current data as JSON"""
    try:
        if os.path.exists('sentiment_snapshot.csv'):
            df = pd.read_csv('sentiment_snapshot.csv')
            df = df.dropna(subset=['Ticker'])
            summary = summarize_market(df)
            
            return jsonify({
                "data": df.head(50).to_dict('records'),
                "summary": summary,
                "total_tickers": len(df)
            })
        else:
            return jsonify({"data": [], "summary": {}, "total_tickers": 0})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/ticker/<ticker>')
def ticker_detail(ticker):
    """Detail page for a specific ticker"""
    try:
        if os.path.exists('sentiment_snapshot.csv'):
            df = pd.read_csv('sentiment_snapshot.csv')
            ticker_data = df[df['Ticker'] == f'${ticker.upper()}']
            
            if not ticker_data.empty:
                ticker_info = ticker_data.iloc[0].to_dict()
                return render_template('ticker_detail.html', 
                                     ticker=ticker.upper(), 
                                     data=ticker_info)
            else:
                return render_template('error.html', 
                                     error=f"No data found for ticker ${ticker.upper()}")
        else:
            return render_template('error.html', 
                                 error="No data available")
    except Exception as e:
        return render_template('error.html', error=str(e))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
