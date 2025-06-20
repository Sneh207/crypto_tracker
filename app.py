from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import requests
import json
from datetime import datetime, timedelta
import os
from contextlib import contextmanager
import logging
import time
from functools import wraps  

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = 'crypto_tracker.db'
COINGECKO_API_BASE = 'https://api.coingecko.com/api/v3'

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiter decorator
def rate_limited(max_per_second=1):
    min_interval = 1.0 / max_per_second
    last_called = [0.0]

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            wait_time = min_interval - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Database context manager
@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Initialize database
def init_db():
    with get_db_connection() as conn:
        # Portfolio table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                coin_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                quantity REAL NOT NULL,
                purchase_price REAL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Watchlist table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                coin_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(coin_id)  -- Prevent duplicate coins
            )
        ''')
        
        # Price cache table for better performance
        conn.execute('''
            CREATE TABLE IF NOT EXISTS price_cache (
                coin_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS coin_cache (
                endpoint TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()

# Helper functions
def fetch_coin_data(coin_ids, vs_currency='usd'):
    """Fetch current price data from CoinGecko API"""
    try:
        if isinstance(coin_ids, list):
            coin_ids = ','.join(coin_ids)
        
        url = f"{COINGECKO_API_BASE}/simple/price"
        params = {
            'ids': coin_ids,
            'vs_currencies': vs_currency,
            'include_24hr_change': 'true',
            'include_market_cap': 'true'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching coin data: {e}")
        return {}

@rate_limited(0.5)  # Maximum 1 request every 2 seconds
def fetch_coins_list(page=1, per_page=50, order='market_cap_desc'):
    """Fetch list of coins from CoinGecko with caching"""
    try:
        cache_key = f"coins_list_{page}_{per_page}_{order}"
        
        # Check cache first
        with get_db_connection() as conn:
            cursor = conn.execute(
                'SELECT data, timestamp FROM coin_cache WHERE endpoint = ?', 
                (cache_key,)
            )
            cache_data = cursor.fetchone()
            
            # Return cached data if it's less than 5 minutes old
            if cache_data:
                data = json.loads(cache_data['data'])
                cache_time = datetime.fromisoformat(cache_data['timestamp'])
                if datetime.now() - cache_time < timedelta(minutes=5):
                    logger.info("Returning cached coin data")
                    return data

        # If no cache or expired, fetch from API
        url = f"{COINGECKO_API_BASE}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': order,
            'per_page': per_page,
            'page': page,
            'sparkline': 'false'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Update cache
        with get_db_connection() as conn:
            conn.execute(
                'INSERT OR REPLACE INTO coin_cache (endpoint, data, timestamp) VALUES (?, ?, ?)',
                (cache_key, json.dumps(data), datetime.now().isoformat())
            )
            conn.commit()

        return data

    except requests.RequestException as e:
        logger.error(f"Error fetching coins list: {e}")
        
        # Return cached data if available, even if expired
        with get_db_connection() as conn:
            cursor = conn.execute(
                'SELECT data FROM coin_cache WHERE endpoint = ?', 
                (cache_key,)
            )
            cache_data = cursor.fetchone()
            if cache_data:
                logger.info("Returning expired cached data due to API error")
                return json.loads(cache_data['data'])
        
        return []

def search_coins(query, limit=10):
    """Search coins by name or symbol"""
    try:
        url = f"{COINGECKO_API_BASE}/search"
        params = {'query': query}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Return limited results
        return data.get('coins', [])[:limit]
    except requests.RequestException as e:
        logger.error(f"Error searching coins: {e}")
        return []

def calculate_portfolio_summary(portfolio_items):
    """Calculate portfolio summary statistics"""
    total_value = 0
    total_cost = 0
    total_holdings = len(portfolio_items)
    
    for item in portfolio_items:
        current_value = item.get('current_value', 0) or 0
        total_value += current_value
        
        if item.get('purchase_price') and item.get('quantity'):
            total_cost += float(item['purchase_price']) * float(item['quantity'])
    
    total_profit_loss = total_value - total_cost if total_cost > 0 else 0
    total_profit_loss_percentage = (total_profit_loss / total_cost * 100) if total_cost > 0 else 0
    
    return {
        'total_value': total_value,
        'total_cost': total_cost,
        'total_profit_loss': total_profit_loss,
        'total_profit_loss_percentage': total_profit_loss_percentage,
        'total_holdings': total_holdings
    }

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

# Portfolio endpoints
@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get user's portfolio with current prices"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM portfolio ORDER BY created_at DESC
            ''')
            portfolio_items = [dict(row) for row in cursor.fetchall()]
        
        if not portfolio_items:
            return jsonify({
                'portfolio': [],
                'summary': calculate_portfolio_summary([])
            })
        
        # Get current prices for all coins in portfolio
        coin_ids = [item['coin_id'] for item in portfolio_items]
        price_data = fetch_coin_data(coin_ids)
        
        # Enrich portfolio items with current market data
        enriched_portfolio = []
        for item in portfolio_items:
            coin_id = item['coin_id']
            market_data = price_data.get(coin_id, {})
            
            current_price = market_data.get('usd', 0)
            change_24h = market_data.get('usd_24h_change', 0)
            market_cap = market_data.get('usd_market_cap', 0)
            
            quantity = float(item['quantity'])
            current_value = current_price * quantity
            
            # Calculate profit/loss if purchase price is available
            profit_loss = None
            profit_loss_percentage = None
            if item['purchase_price']:
                purchase_price = float(item['purchase_price'])
                cost_basis = purchase_price * quantity
                profit_loss = current_value - cost_basis
                profit_loss_percentage = (profit_loss / cost_basis * 100) if cost_basis > 0 else 0
            
            enriched_item = {
                **item,
                'current_price': current_price,
                'current_value': current_value,
                'change_24h': change_24h,
                'market_cap': market_cap,
                'profit_loss': profit_loss,
                'profit_loss_percentage': profit_loss_percentage
            }
            enriched_portfolio.append(enriched_item)
        
        summary = calculate_portfolio_summary(enriched_portfolio)
        
        return jsonify({
            'portfolio': enriched_portfolio,
            'summary': summary
        })
        
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio', methods=['POST'])
def add_to_portfolio():
    """Add a coin to the portfolio"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['coin_id', 'coin_name', 'symbol', 'quantity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO portfolio (coin_id, coin_name, symbol, quantity, purchase_price, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                data['coin_id'],
                data['coin_name'],
                data['symbol'].upper(),
                float(data['quantity']),
                float(data['purchase_price']) if data.get('purchase_price') else None,
                data.get('notes', '')
            ))
            conn.commit()
        
        return jsonify({'message': 'Added to portfolio successfully'}), 201
        
    except ValueError as e:
        return jsonify({'error': 'Invalid number format'}), 400
    except Exception as e:
        logger.error(f"Error adding to portfolio: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio_item(portfolio_id):
    """Delete a portfolio item"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('DELETE FROM portfolio WHERE id = ?', (portfolio_id,))
            if cursor.rowcount == 0:
                return jsonify({'error': 'Portfolio item not found'}), 404
            conn.commit()
        
        return jsonify({'message': 'Portfolio item deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting portfolio item: {e}")
        return jsonify({'error': str(e)}), 500

# Watchlist endpoints
@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get user's watchlist with current prices"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('SELECT * FROM watchlist ORDER BY added_at DESC')
            watchlist_items = [dict(row) for row in cursor.fetchall()]
        
        if not watchlist_items:
            return jsonify({'watchlist': []})
        
        # Get current prices for all coins in watchlist
        coin_ids = [item['coin_id'] for item in watchlist_items]
        
        try:
            # Use simple/price endpoint instead of markets for better reliability
            url = f"{COINGECKO_API_BASE}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd',
                'include_24h_vol': 'true',
                'include_24h_change': 'true',
                'include_market_cap': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            market_data = response.json()
            
            # Enrich watchlist items with current market data
            enriched_watchlist = []
            for item in watchlist_items:
                coin_id = item['coin_id']
                coin_market_data = market_data.get(coin_id, {})
                
                enriched_item = {
                    **item,
                    'current_price': coin_market_data.get('usd', 0),
                    'price_change_24h': coin_market_data.get('usd_24h_change', 0),
                    'market_cap': coin_market_data.get('usd_market_cap', 0)
                }
                enriched_watchlist.append(enriched_item)
            
            return jsonify({
                'success': True,
                'watchlist': enriched_watchlist
            })
            
        except requests.RequestException as e:
            # If API fails, return watchlist without market data
            logger.error(f"Error fetching market data: {e}")
            return jsonify({
                'success': True,
                'watchlist': watchlist_items,
                'warning': 'Market data temporarily unavailable'
            })
        
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
@app.route('/api/watchlist', methods=['POST'])
def add_to_watchlist():
    """Add a coin to the watchlist"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['coin_id', 'coin_name', 'symbol']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        with get_db_connection() as conn:
            try:
                cursor = conn.execute('''
                    INSERT INTO watchlist (coin_id, coin_name, symbol)
                    VALUES (?, ?, ?)
                ''', (
                    data['coin_id'],
                    data['coin_name'],
                    data['symbol'].upper()
                ))
                conn.commit()
                
                # Get the inserted item
                new_id = cursor.lastrowid
                cursor = conn.execute('SELECT * FROM watchlist WHERE id = ?', (new_id,))
                new_item = dict(cursor.fetchone())
                
                return jsonify({
                    'success': True,
                    'data': new_item,
                    'message': 'Added to watchlist successfully'
                }), 201
                
            except sqlite3.IntegrityError:
                return jsonify({
                    'success': False,
                    'error': 'Coin already in watchlist'
                }), 409
        
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/watchlist/<int:watchlist_id>', methods=['DELETE'])
def remove_from_watchlist(watchlist_id):
    """Remove a coin from the watchlist"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('DELETE FROM watchlist WHERE id = ?', (watchlist_id,))
            if cursor.rowcount == 0:
                return jsonify({
                    'success': False,
                    'error': 'Watchlist item not found'
                }), 404
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Removed from watchlist successfully'
        })
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    

# Market data endpoints
@app.route('/api/coins/all', methods=['GET'])
def get_all_coins():
    """Get paginated list of all coins"""
    try:
        page = int(request.args.get('page', 1))
        per_page = min(int(request.args.get('per_page', 50)), 100)  # Limit to 100
        
        coins_data = fetch_coins_list(page=page, per_page=per_page)
        
        # Set fixed total count to prevent glitching
        total_coins = 500
        
        if not coins_data:
            logger.warning("No coin data available")
            return jsonify({
                'coins': [],
                'total': 500,
                'page': page,
                'per_page': per_page,
                'error': 'Data temporarily unavailable'
            })
        
        formatted_coins = []
        for coin in coins_data:
            try:
                formatted_coins.append({
                    'id': coin['id'],
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(),
                    'current_price': coin.get('current_price', 0),
                    'market_cap': coin.get('market_cap', 0),
                    'market_cap_rank': coin.get('market_cap_rank', 0),
                    'price_change_24h': coin.get('price_change_24h', 0),
                    'price_change_percentage_24h': coin.get('price_change_percentage_24h', 0)
                })
            except KeyError:
                continue
        
        return jsonify({
            'coins': formatted_coins,
            'total': total_coins,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"Error in get_all_coins: {str(e)}")
        return jsonify({
            'coins': [],
            'total': 500,
            'page': page,
            'per_page': per_page,
            'error': 'Service temporarily unavailable'
        }), 503
    
    
# --- Add this new endpoint below ---

@app.route('/api/coins/top-growth', methods=['GET'])
def get_top_growth_coins():
    """Get top 10 coins with best growth in the last year"""
    try:
        limit = int(request.args.get('limit', 10))
        # Get top 10 coins by market cap
        url = f"{COINGECKO_API_BASE}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': 10,  # Only top 10
            'page': 1,
            'sparkline': 'false'
        }
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        coins_data = response.json()

        growth_coins = []
        for coin in coins_data:
            coin_id = coin['id']
            # Fetch 1-year historical price data
            hist_url = f"{COINGECKO_API_BASE}/coins/{coin_id}/market_chart"
            hist_params = {'vs_currency': 'usd', 'days': 365}
            hist_resp = requests.get(hist_url, params=hist_params, timeout=15)
            if hist_resp.status_code != 200:
                continue
            hist_data = hist_resp.json()
            prices = hist_data.get('prices', [])
            if not prices or len(prices) < 2:
                continue
            old_price = prices[0][1]
            current_price = prices[-1][1]
            if old_price == 0:
                continue
            growth = ((current_price - old_price) / old_price) * 100
            growth_coins.append({
                'id': coin_id,
                'name': coin['name'],
                'symbol': coin['symbol'].upper(),
                'current_price': current_price,
                'market_cap': coin.get('market_cap', 0),
                'market_cap_rank': coin.get('market_cap_rank', 0),
                'price_change_24h': coin.get('price_change_24h', 0),
                'price_change_percentage_24h': coin.get('price_change_percentage_24h', 0),
                'price_change_percentage_1y': growth
            })
            time.sleep(1.2)  # To avoid CoinGecko rate limits

        # Sort and return top growth coins
        growth_coins.sort(key=lambda x: x['price_change_percentage_1y'], reverse=True)
        top_growth_coins = growth_coins[:limit]
        return jsonify({
            'coins': top_growth_coins,
            'total': len(top_growth_coins),
            'period': '1y'
        })
    except Exception as e:
        logger.error(f"Error fetching top growth coins: {e}")
        return jsonify({
            'coins': [],
            'total': 0,
            'period': '1y',
            'error': str(e)
        })
    

# Analytics endpoints
@app.route('/api/analytics/market-growth', methods=['GET'])
def get_market_growth():
    """Get market growth analytics"""
    try:
        period = request.args.get('period', '1y')
        
        # Fetch top 100 coins for growth analysis
        coins_data = fetch_coins_list(page=1, per_page=100)
        
        if not coins_data:
            return jsonify({'error': 'Unable to fetch market data'}), 500
        
        # Calculate growth metrics
        total_market_cap = sum(coin.get('market_cap', 0) or 0 for coin in coins_data)
        total_24h_change = sum(coin.get('price_change_percentage_24h', 0) or 0 for coin in coins_data)
        average_growth = total_24h_change / len(coins_data) if coins_data else 0
        
        # Find best and worst performers
        sorted_by_performance = sorted(
            coins_data, 
            key=lambda x: x.get('price_change_percentage_24h', 0) or 0, 
            reverse=True
        )
        
        best_performer = None
        if sorted_by_performance:
            best = sorted_by_performance[0]
            best_performer = {
                'id': best['id'],
                'name': best['name'],
                'symbol': best['symbol'].upper(),
                'growth': best.get('price_change_percentage_24h', 0),
                'current_price': best.get('current_price', 0)
            }
        
        # Top 10 performers
        top_performers = []
        for coin in sorted_by_performance[:10]:
            if coin.get('price_change_percentage_24h', 0) > 0:
                top_performers.append({
                    'id': coin['id'],
                    'name': coin['name'],
                    'symbol': coin['symbol'].upper(),
                    'growth': coin.get('price_change_percentage_24h', 0),
                    'current_price': coin.get('current_price', 0)
                })
        
        return jsonify({
            'period': period,
            'total_growth': average_growth,  # Using average as proxy for total growth
            'best_performer': best_performer,
            'average_growth': average_growth,
            'top_performers': top_performers,
            'total_market_cap': total_market_cap
        })
        
    except Exception as e:
        logger.error(f"Error getting market growth: {e}")
        return jsonify({'error': str(e)}), 500

# Export endpoints
@app.route('/api/export/portfolio', methods=['GET'])
def export_portfolio():
    """Export portfolio data"""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        # Get portfolio data
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM portfolio ORDER BY created_at DESC
            ''')
            portfolio_items = [dict(row) for row in cursor.fetchall()]
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_type == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=[
                'coin_id', 'coin_name', 'symbol', 'quantity', 
                'purchase_price', 'notes', 'created_at'
            ])
            writer.writeheader()
            writer.writerows(portfolio_items)
            
            return jsonify({
                'data': output.getvalue(),
                'filename': f'portfolio_export_{timestamp}.csv'
            })
        else:
            return jsonify({
                'data': portfolio_items,
                'filename': f'portfolio_export_{timestamp}.json'
            })
        
    except Exception as e:
        logger.error(f"Error exporting portfolio: {e}")
        return jsonify({'error': str(e)}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Initialize database and run app
if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='127.0.0.1', port=5000)