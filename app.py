from flask import Flask, render_template, jsonify
import pandas as pd
import json
import os
import glob
from main import main as run_analysis, load_history, summarize_market

app = Flask(__name__)

def get_latest_csv():
    """Find the latest sentiment snapshot CSV file"""
    csv_files = glob.glob("sentiment_snapshot_*.csv")
    if not csv_files:
        return None
    return max(csv_files, key=os.path.getctime)

def get_latest_history():
    """Find the latest history JSON file"""
    history_files = glob.glob("history_*.json")
    if not history_files:
        return None
    return max(history_files, key=os.path.getctime)

@app.route('/')
def index():
    """Main dashboard page"""
    try:
        # Run the analysis to get fresh data
        run_analysis()
        
        # Load the latest CSV data
        latest_csv = get_latest_csv()
        if latest_csv and os.path.exists(latest_csv):
            df = pd.read_csv(latest_csv)
            
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

@app.route('/api/files')
def list_files():
    """API endpoint to list available data files"""
    try:
        csv_files = glob.glob("sentiment_snapshot_*.csv")
        history_files = glob.glob("history_*.json")
        
        csv_info = []
        for f in sorted(csv_files, key=os.path.getctime, reverse=True):
            csv_info.append({
                "filename": f,
                "created": os.path.getctime(f),
                "size": os.path.getsize(f)
            })
        
        history_info = []
        for f in sorted(history_files, key=os.path.getctime, reverse=True):
            history_info.append({
                "filename": f,
                "created": os.path.getctime(f),
                "size": os.path.getsize(f)
            })
        
        return jsonify({
            "csv_files": csv_info,
            "history_files": history_info,
            "latest_csv": get_latest_csv(),
            "latest_history": get_latest_history()
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/api/data')
def get_data():
    """API endpoint to get current data as JSON"""
    try:
        latest_csv = get_latest_csv()
        if latest_csv and os.path.exists(latest_csv):
            df = pd.read_csv(latest_csv)
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
        latest_csv = get_latest_csv()
        if latest_csv and os.path.exists(latest_csv):
            df = pd.read_csv(latest_csv)
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
