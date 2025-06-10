# import mysql.connector
# from mysql.connector import Error
# import requests
# import json
# from datetime import datetime, timedelta
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import os
# from functools import wraps
# import time
# from requests.exceptions import Timeout, RequestException, ConnectionError
# import threading
# from collections import defaultdict
# import statistics
# import traceback

# app = Flask(__name__)
# CORS(app, resources={
#     r"/api/*": {
#         "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
#         "methods": ["GET", "POST", "PUT", "DELETE"],
#         "allow_headers": ["Content-Type", "Authorization"]
#     }
# })

# # Database configuration
# from dotenv import load_dotenv

# load_dotenv()

# # Environment variables
# DB_HOST = os.getenv('DB_HOST', 'localhost')
# DB_NAME = os.getenv('DB_NAME', 'crypto_tracker')
# DB_USER = os.getenv('DB_USER', 'root')
# DB_PASSWORD = os.getenv('DB_PASSWORD', 'dpsrnusgnws')
# DB_PORT = int(os.getenv('DB_PORT', '3306'))
# COINGECKO_API_URL = os.getenv('COINGECKO_API_URL', 'https://api.coingecko.com/api/v3')

# from mysql.connector.pooling import MySQLConnectionPool

# # Database configuration
# dbconfig = {
#     "host": DB_HOST,
#     "database": DB_NAME,
#     "user": DB_USER,
#     "password": DB_PASSWORD,
#     "port": DB_PORT,
#     "autocommit": True,
#     "use_unicode": True,
#     "charset": "utf8mb4"
# }

# # Initialize connection pool with better error handling
# connection_pool = None
# try:
#     connection_pool = MySQLConnectionPool(
#         pool_name="crypto_pool",
#         pool_size=5,  # Reduced pool size
#         pool_reset_session=True,
#         **dbconfig
#     )
#     print("✓ Database connection pool created successfully")
# except Error as e:
#     print(f"✗ Error creating connection pool: {e}")
#     print("⚠️ Running in API-only mode without database")
#     connection_pool = None

# # Cache for storing coin data
# coin_cache = {}
# cache_lock = threading.Lock()
# cache_expiry = {}

# # --- CoinGecko API response cache ---
# coingecko_response_cache = {}
# COINGECKO_CACHE_TTL = 300  # seconds

# coin_price_cache = {}
# COIN_PRICE_CACHE_TTL = 300  # seconds

# def get_cached_coingecko_response(key, fetch_func):
#     """Cache CoinGecko API responses in memory for COINGECKO_CACHE_TTL seconds."""
#     now = time.time()
#     cache_entry = coingecko_response_cache.get(key)
#     if cache_entry and now - cache_entry['timestamp'] < COINGECKO_CACHE_TTL:
#         return cache_entry['data']
    
#     try:
#         data = fetch_func()
#         if data is not None:
#             coingecko_response_cache[key] = {'data': data, 'timestamp': now}
#         return data
#     except Exception as e:
#         print(f"Error in cached response fetch: {e}")
#         return cache_entry['data'] if cache_entry else None

# def get_db_connection():
#     """Get database connection from pool with error handling"""
#     if not connection_pool:
#         return None
        
#     try:
#         connection = connection_pool.get_connection()
#         if connection.is_connected():
#             return connection
#         else:
#             print("Database connection failed - not connected")
#             return None
#     except Error as e:
#         print(f"Database connection error: {e}")
#         return None
#     except Exception as e:
#         print(f"Unexpected error while connecting to database: {e}")
#         return None

# def init_database():
#     """Initialize database with enhanced tables"""
#     if not connection_pool:
#         print("⚠️ No database connection pool available")
#         return True  # Continue without database
        
#     connection = get_db_connection()
#     if not connection:
#         return True  # Continue without database
    
#     try:
#         cursor = connection.cursor()
        
#         # Enhanced portfolio table
#         create_portfolio_table = """
#         CREATE TABLE IF NOT EXISTS portfolio (
#             id INT AUTO_INCREMENT PRIMARY KEY,
#             coin_id VARCHAR(100) NOT NULL,
#             coin_name VARCHAR(100) NOT NULL,
#             symbol VARCHAR(20) NOT NULL,
#             quantity DECIMAL(20, 8) NOT NULL,
#             purchase_price DECIMAL(20, 8),
#             purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             notes TEXT,
#             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
#         );
#         """
        
#         # Coin cache table for faster searches
#         create_coin_cache_table = """
#         CREATE TABLE IF NOT EXISTS coin_cache (
#             id VARCHAR(100) PRIMARY KEY,
#             name VARCHAR(200) NOT NULL,
#             symbol VARCHAR(20) NOT NULL,
#             market_cap_rank INT,
#             current_price DECIMAL(20, 8),
#             market_cap BIGINT,
#             price_change_24h DECIMAL(10, 4),
#             price_change_percentage_24h DECIMAL(10, 4),
#             last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
#         );
#         """
        
#         # Watchlist table
#         create_watchlist_table = """
#         CREATE TABLE IF NOT EXISTS watchlist (
#             id INT AUTO_INCREMENT PRIMARY KEY,
#             coin_id VARCHAR(100) NOT NULL,
#             coin_name VARCHAR(100) NOT NULL,
#             symbol VARCHAR(20) NOT NULL,
#             added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#         );
#         """
        
#         cursor.execute(create_portfolio_table)
#         cursor.execute(create_coin_cache_table)
#         cursor.execute(create_watchlist_table)
        
#         print("✓ Database tables initialized successfully")
#         return True
        
#     except Error as e:
#         print(f"✗ Error initializing database: {e}")
#         return True  # Continue without database
#     finally:
#         if connection and connection.is_connected():
#             cursor.close()
#             connection.close()

# def rate_limit(seconds=1):
#     """Enhanced rate limiting decorator"""
#     def decorator(f):
#         last_called = {}
        
#         @wraps(f)
#         def wrapper(*args, **kwargs):
#             now = time.time()
#             key = f.__name__
#             if key in last_called:
#                 elapsed = now - last_called[key]
#                 if elapsed < seconds:
#                     time.sleep(seconds - elapsed)
#             result = f(*args, **kwargs)
#             last_called[key] = time.time()
#             return result
#         return wrapper
#     return decorator

# def make_api_request(url, params=None, timeout=30):  # Increased timeout
#     """Enhanced API request handler with better error handling and retries"""
#     headers = {
#         'User-Agent': 'Mozilla/5.0',  # More standard user agent
#         'Accept': 'application/json',
#         'Content-Type': 'application/json'
#     }
    
#     max_retries = 3
#     for attempt in range(max_retries):
#         try:
#             # Debug logging
#             print(f"Attempting API request ({attempt + 1}/{max_retries}): {url}")
            
#             response = requests.get(
#                 url, 
#                 params=params, 
#                 headers=headers, 
#                 timeout=timeout
#             )
            
#             # Debug logging
#             print(f"Response status: {response.status_code}")
            
#             if response.status_code == 429:
#                 wait_time = min(60 * (2 ** attempt), 300)  # Exponential backoff, max 5 minutes
#                 print(f"Rate limited, waiting {wait_time} seconds...")
#                 time.sleep(wait_time)
#                 continue
                
#             response.raise_for_status()
            
#             data = response.json()
#             if not data:
#                 print("Empty response received")
#                 return None
                
#             return data
            
#         except requests.exceptions.Timeout:
#             print(f"Request timed out (attempt {attempt + 1})")
#             if attempt == max_retries - 1:
#                 break
#             time.sleep(5 * (2 ** attempt))
            
#         except requests.exceptions.ConnectionError:
#             print(f"Connection error (attempt {attempt + 1})")
#             if attempt == max_retries - 1:
#                 break
#             time.sleep(5 * (2 ** attempt))
            
#         except requests.exceptions.RequestException as e:
#             print(f"Request failed (attempt {attempt + 1}): {str(e)}")
#             if attempt == max_retries - 1:
#                 break
#             time.sleep(5 * (2 ** attempt))
            
#         except Exception as e:
#             print(f"Unexpected error: {str(e)}")
#             return None

#     print(f"All {max_retries} attempts failed for URL: {url}")
#     return None


# @rate_limit(1)
# def get_coin_price(coin_id):
#     """Get current price with enhanced data and caching"""
#     now = time.time()
#     # Check cache first
#     cache_entry = coin_price_cache.get(coin_id)
#     if cache_entry and now - cache_entry['timestamp'] < COIN_PRICE_CACHE_TTL:
#         return cache_entry['data']
    
#     try:
#         url = f"{COINGECKO_API_URL}/simple/price"
#         params = {
#             'ids': coin_id,
#             'vs_currencies': 'usd',
#             'include_24hr_change': 'true',
#             'include_24hr_vol': 'true',
#             'include_market_cap': 'true',
#             'include_last_updated_at': 'true'
#         }
#         data = make_api_request(url, params)
#         if data and coin_id in data:
#             coin_data = data[coin_id]
#             result = {
#                 'price': coin_data.get('usd', 0),
#                 'change_24h': coin_data.get('usd_24h_change', 0),
#                 'volume_24h': coin_data.get('usd_24h_vol', 0),
#                 'market_cap': coin_data.get('usd_market_cap', 0),
#                 'last_updated': coin_data.get('last_updated_at', time.time())
#             }
#             # Save to cache
#             coin_price_cache[coin_id] = {'data': result, 'timestamp': now}
#             return result
#         return None
#     except Exception as e:
#         print(f"Error fetching price for {coin_id}: {e}")
#         return None

# @rate_limit(2)
# def get_coin_history(coin_id, days=365):
#     """Get historical price data with more details"""
#     try:
#         url = f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart"
#         params = {
#             'vs_currency': 'usd',
#             'days': days,
#             'interval': 'daily' if days > 90 else 'hourly'
#         }
#         data = make_api_request(url, params)
#         if not data or 'prices' not in data:
#             return []
        
#         prices = []
#         for i, price_data in enumerate(data['prices']):
#             timestamp = price_data[0]
#             price = price_data[1]
#             volume = data.get('total_volumes', [[0, 0]])[i][1] if i < len(data.get('total_volumes', [])) else 0
#             prices.append({
#                 'timestamp': timestamp,
#                 'date': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d'),
#                 'price': price,
#                 'volume': volume
#             })
#         return prices
#     except Exception as e:
#         print(f"Error fetching history for {coin_id}: {e}")
#         return []

# @rate_limit(2)  # Increased rate limit window
# def get_coins_list(page=1, per_page=100):
#     """Get comprehensive list of all coins, with improved error handling"""
#     try:
#         url = f"{COINGECKO_API_URL}/coins/markets"
#         params = {
#             'vs_currency': 'usd',
#             'order': 'market_cap_desc',
#             'per_page': min(per_page, 100),
#             'page': page,
#             'sparkline': 'false',
#             'locale': 'en',
#             'precision': 2
#         }
        
#         # Debug logging
#         print(f"Fetching coins list: page={page}, per_page={per_page}")
        
#         data = make_api_request(url, params)
        
#         if not data:
#             print("No data received from API")
#             return []
            
#         if not isinstance(data, list):
#             print(f"Unexpected API response format: {type(data)}")
#             return []
        
#         # Process and validate each coin
#         coins = []
#         for coin in data:
#             try:
#                 processed_coin = {
#                     'id': coin['id'],
#                     'name': coin['name'],
#                     'symbol': coin['symbol'].upper(),
#                     'current_price': coin.get('current_price', 0),
#                     'market_cap': coin.get('market_cap', 0),
#                     'market_cap_rank': coin.get('market_cap_rank', 0),
#                     'price_change_24h': coin.get('price_change_24h', 0),
#                     'price_change_percentage_24h': coin.get('price_change_percentage_24h', 0),
#                     'image': coin.get('image', '')
#                 }
#                 coins.append(processed_coin)
#             except KeyError as e:
#                 print(f"Missing required field in coin data: {e}")
#                 continue
            
#         return coins
        
#     except Exception as e:
#         print(f"Error in get_coins_list: {str(e)}")
#         traceback.print_exc()
#         return []

# def update_coin_cache(coins):
#     """Update coin cache in database"""
#     connection = get_db_connection()
#     if not connection:
#         return
    
#     try:
#         cursor = connection.cursor()
#         # Clear old cache
#         cursor.execute("DELETE FROM coin_cache WHERE last_updated < DATE_SUB(NOW(), INTERVAL 1 HOUR)")
        
#         # Insert new data
#         insert_query = """
#         INSERT INTO coin_cache (id, name, symbol, market_cap_rank, current_price, 
#                                market_cap, price_change_24h, price_change_percentage_24h)
#         VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
#         ON DUPLICATE KEY UPDATE
#         name = VALUES(name),
#         symbol = VALUES(symbol),
#         market_cap_rank = VALUES(market_cap_rank),
#         current_price = VALUES(current_price),
#         market_cap = VALUES(market_cap),
#         price_change_24h = VALUES(price_change_24h),
#         price_change_percentage_24h = VALUES(price_change_percentage_24h)
#         """
        
#         for coin in coins:
#             values = (
#                 coin['id'], coin['name'], coin['symbol'], coin['market_cap_rank'],
#                 coin['current_price'], coin['market_cap'], coin['price_change_24h'],
#                 coin['price_change_percentage_24h']
#             )
#             cursor.execute(insert_query, values)
            
#     except Error as e:
#         print(f"Error updating coin cache: {e}")
#     finally:
#         if connection and connection.is_connected():
#             cursor.close()
#             connection.close()

# # API Routes

# @app.route('/api/health', methods=['GET'])
# def health_check():
#     """Health check endpoint"""
#     try:
#         # Test database connection
#         db_status = "connected" if get_db_connection() else "disconnected"
        
#         # Test API connection
#         test_url = f"{COINGECKO_API_URL}/ping"
#         api_status = "connected"
#         try:
#             response = requests.get(test_url, timeout=5)
#             if response.status_code != 200:
#                 api_status = "limited"
#         except:
#             api_status = "disconnected"
        
#         return jsonify({
#             'status': 'healthy',
#             'timestamp': datetime.now().isoformat(),
#             'database': db_status,
#             'api': api_status,
#             'cache_entries': len(coin_price_cache)
#         })
#     except Exception as e:
#         return jsonify({
#             'status': 'unhealthy',
#             'error': str(e),
#             'timestamp': datetime.now().isoformat()
#         }), 500

# @app.route('/api/coins/all', methods=['GET'])
# def get_all_coins():
#     """Get all coins with market data"""
#     try:
#         page = request.args.get('page', 1, type=int)
#         per_page = min(request.args.get('per_page', 50, type=int), 100)
        
#         # Try to get from cache first if database is available
#         if connection_pool:
#             connection = get_db_connection()
#             if connection:
#                 try:
#                     cursor = connection.cursor(dictionary=True)
#                     cursor.execute("SELECT COUNT(*) as total FROM coin_cache")
#                     result = cursor.fetchone()
#                     total_count = result['total'] if result else 0
                    
#                     if total_count > 0:
#                         # Get paginated results from cache
#                         offset = (page - 1) * per_page
#                         cursor.execute("""
#                             SELECT * FROM coin_cache 
#                             ORDER BY market_cap_rank 
#                             LIMIT %s OFFSET %s
#                         """, (per_page, offset))
                        
#                         coins = cursor.fetchall()
                        
#                         return jsonify({
#                             'coins': coins,
#                             'total': total_count,
#                             'page': page,
#                             'per_page': per_page,
#                             'source': 'cache'
#                         })
                        
#                 except Exception as e:
#                     print(f"Database query error: {e}")
#                 finally:
#                     if connection and connection.is_connected():
#                         cursor.close()
#                         connection.close()
        
#         # Fallback to direct API call
#         coins = get_coins_list(page, per_page)
#         if coins:
#             # Update cache if database is available
#             if connection_pool:
#                 update_coin_cache(coins)
            
#             return jsonify({
#                 'coins': coins,
#                 'total': len(coins),
#                 'page': page,
#                 'per_page': per_page,
#                 'source': 'api'
#             })
        
#         return jsonify({
#             'error': 'Unable to fetch coins data',
#             'coins': [],
#             'total': 0,
#             'page': page,
#             'per_page': per_page
#         }), 200  # Return 200 instead of 500 to prevent frontend errors
        
#     except Exception as e:
#         print(f"Error in get_all_coins: {str(e)}")
#         traceback.print_exc()
#         return jsonify({
#             'error': f'Failed to fetch coins: {str(e)}',
#             'coins': [],
#             'total': 0,
#             'page': 1,
#             'per_page': 50
#         }), 200

# @app.route('/api/analytics/portfolio', methods=['GET'])
# def get_portfolio_analytics():
#     """Get detailed portfolio analytics"""
#     if not connection_pool:
#         return jsonify({
#             'analytics': {
#                 'total_value': 0,
#                 'total_invested': 0,
#                 'total_profit_loss': 0,
#                 'holdings_count': 0
#             },
#             'holdings': [],
#             'message': 'Database not available'
#         })
    
#     connection = get_db_connection()
#     if not connection:
#         return jsonify({
#             'analytics': {
#                 'total_value': 0,
#                 'total_invested': 0,
#                 'total_profit_loss': 0,
#                 'holdings_count': 0
#             },
#             'holdings': [],
#             'message': 'Database connection failed'
#         })
    
#     try:
#         cursor = connection.cursor(dictionary=True)
#         cursor.execute("""
#             SELECT coin_id, coin_name, symbol, quantity, purchase_price, purchase_date
#             FROM portfolio
#         """)
#         portfolio = cursor.fetchall()
        
#         if not portfolio:
#             return jsonify({
#                 'analytics': {
#                     'total_value': 0,
#                     'total_invested': 0,
#                     'total_profit_loss': 0,
#                     'total_profit_loss_percentage': 0,
#                     'best_performer': None,
#                     'worst_performer': None,
#                     'largest_holding': None,
#                     'allocation': [],
#                     'daily_change': 0,
#                     'holdings_count': 0
#                 },
#                 'holdings': [],
#                 'message': 'No portfolio data found'
#             })
        
#         # Calculate comprehensive analytics
#         analytics = {
#             'total_value': 0,
#             'total_invested': 0,
#             'total_profit_loss': 0,
#             'total_profit_loss_percentage': 0,
#             'best_performer': None,
#             'worst_performer': None,
#             'largest_holding': None,
#             'allocation': [],
#             'daily_change': 0,
#             'holdings_count': len(portfolio)
#         }
        
#         holdings_data = []
#         daily_change_total = 0
        
#         for item in portfolio:
#             price_data = get_coin_price(item['coin_id'])
#             if not price_data:
#                 continue
            
#             current_price = price_data['price']
#             current_value = float(item['quantity']) * current_price
#             change_24h = price_data['change_24h']
            
#             holding_data = {
#                 'coin_id': item['coin_id'],
#                 'coin_name': item['coin_name'], 
#                 'symbol': item['symbol'],
#                 'quantity': float(item['quantity']),
#                 'current_price': current_price,
#                 'current_value': current_value,
#                 'change_24h': change_24h,
#                 'daily_change_value': (current_value * change_24h / 100) if change_24h else 0
#             }
            
#             analytics['total_value'] += current_value
#             daily_change_total += holding_data['daily_change_value']
            
#             if item['purchase_price']:
#                 purchase_price = float(item['purchase_price'])
#                 purchase_value = float(item['quantity']) * purchase_price
#                 profit_loss = current_value - purchase_value
#                 profit_loss_percentage = ((current_price - purchase_price) / purchase_price) * 100
                
#                 holding_data.update({
#                     'purchase_price': purchase_price,
#                     'purchase_value': purchase_value,
#                     'profit_loss': profit_loss,
#                     'profit_loss_percentage': profit_loss_percentage
#                 })
                
#                 analytics['total_invested'] += purchase_value
#                 analytics['total_profit_loss'] += profit_loss
                
#                 # Track best and worst performers
#                 if not analytics['best_performer'] or profit_loss_percentage > analytics['best_performer'].get('profit_loss_percentage', 0):
#                     analytics['best_performer'] = holding_data
#                 if not analytics['worst_performer'] or profit_loss_percentage < analytics['worst_performer'].get('profit_loss_percentage', 0):
#                     analytics['worst_performer'] = holding_data
            
#             holdings_data.append(holding_data)
        
#         # Calculate remaining analytics
#         if analytics['total_invested'] > 0:
#             analytics['total_profit_loss_percentage'] = (analytics['total_profit_loss'] / analytics['total_invested']) * 100
        
#         analytics['daily_change'] = daily_change_total
#         analytics['daily_change_percentage'] = (daily_change_total / analytics['total_value']) * 100 if analytics['total_value'] > 0 else 0
        
#         # Find largest holding by value
#         if holdings_data:
#             analytics['largest_holding'] = max(holdings_data, key=lambda x: x['current_value'])
            
#             # Calculate allocation percentages
#             for holding in holdings_data:
#                 allocation_percentage = (holding['current_value'] / analytics['total_value']) * 100
#                 analytics['allocation'].append({
#                     'coin_id': holding['coin_id'],
#                     'coin_name': holding['coin_name'],
#                     'symbol': holding['symbol'],
#                     'percentage': allocation_percentage,
#                     'value': holding['current_value']
#                 })
            
#             # Sort allocation by percentage
#             analytics['allocation'].sort(key=lambda x: x['percentage'], reverse=True)
        
#         return jsonify({
#             'analytics': analytics,
#             'holdings': holdings_data,
#             'timestamp': datetime.now().isoformat()
#         })
        
#     except Error as e:
#         print(f"Database error in portfolio analytics: {e}")
#         return jsonify({
#             'analytics': {
#                 'total_value': 0,
#                 'total_invested': 0,
#                 'total_profit_loss': 0,
#                 'holdings_count': 0
#             },
#             'holdings': [],
#             'error': f'Database error: {str(e)}'
#         }), 200
        
#     except Exception as e:
#         print(f"Error in portfolio analytics: {e}")
#         traceback.print_exc()
#         return jsonify({
#             'analytics': {
#                 'total_value': 0,
#                 'total_invested': 0,
#                 'total_profit_loss': 0,
#                 'holdings_count': 0
#             },
#             'holdings': [],
#             'error': f'Unexpected error: {str(e)}'
#         }), 200
        
#     finally:
#         if connection and connection.is_connected():
#             cursor.close()
#             connection.close()

# # Error handlers
# @app.errorhandler(404)
# def not_found(error):
#     return jsonify({'error': 'Endpoint not found'}), 404

# @app.errorhandler(500)
# def internal_error(error):
#     print(f"Internal server error: {error}")
#     return jsonify({'error': 'Internal server error'}), 500

# @app.errorhandler(429)
# def rate_limit_error(error):
#     return jsonify({'error': 'Rate limit exceeded', 'message': 'Please try again later'}), 429

# if __name__ == '__main__':
#     print("🚀 Starting Crypto Portfolio Tracker")
    
#     # Initialize database
#     init_database()
    
#     # Start Flask app
#     debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
#     port = int(os.getenv('FLASK_PORT', 5000))
#     host = os.getenv('FLASK_HOST', '127.0.0.1')
    
#     print(f"✓ Server starting on {host}:{port}")
#     print(f"✓ Debug mode: {debug_mode}")
#     print("✓ Available endpoints:")
#     print("  - GET  /api/health")
#     print("  - GET  /api/coins/all")
#     print("  - GET  /api/analytics/portfolio")
#     print()
#     print("🎯 Crypto Portfolio Tracker is ready!")
    
#     app.run(host=host, port=port, debug=debug_mode, threaded=True)



from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import requests
import json
from datetime import datetime, timedelta
import os
from contextlib import contextmanager
import logging

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = 'crypto_tracker.db'
COINGECKO_API_BASE = 'https://api.coingecko.com/api/v3'

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                coin_id TEXT NOT NULL UNIQUE,
                coin_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def fetch_coins_list(page=1, per_page=50, order='market_cap_desc'):
    """Fetch list of coins from CoinGecko"""
    try:
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
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching coins list: {e}")
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
            cursor = conn.execute('''
                SELECT * FROM watchlist ORDER BY added_at DESC
            ''')
            watchlist_items = [dict(row) for row in cursor.fetchall()]
        
        if not watchlist_items:
            return jsonify({'watchlist': []})
        
        # Get current prices for all coins in watchlist
        coin_ids = [item['coin_id'] for item in watchlist_items]
        price_data = fetch_coin_data(coin_ids)
        
        # Enrich watchlist items with current market data
        enriched_watchlist = []
        for item in watchlist_items:
            coin_id = item['coin_id']
            market_data = price_data.get(coin_id, {})
            
            enriched_item = {
                **item,
                'current_price': market_data.get('usd', 0),
                'change_24h': market_data.get('usd_24h_change', 0),
                'market_cap': market_data.get('usd_market_cap', 0)
            }
            enriched_watchlist.append(enriched_item)
        
        return jsonify({'watchlist': enriched_watchlist})
        
    except Exception as e:
        logger.error(f"Error getting watchlist: {e}")
        return jsonify({'error': str(e)}), 500

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
                conn.execute('''
                    INSERT INTO watchlist (coin_id, coin_name, symbol)
                    VALUES (?, ?, ?)
                ''', (
                    data['coin_id'],
                    data['coin_name'],
                    data['symbol'].upper()
                ))
                conn.commit()
            except sqlite3.IntegrityError:
                return jsonify({'error': 'Coin already in watchlist'}), 409
        
        return jsonify({'message': 'Added to watchlist successfully'}), 201
        
    except Exception as e:
        logger.error(f"Error adding to watchlist: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/watchlist/<int:watchlist_id>', methods=['DELETE'])
def remove_from_watchlist(watchlist_id):
    """Remove a coin from the watchlist"""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute('DELETE FROM watchlist WHERE id = ?', (watchlist_id,))
            if cursor.rowcount == 0:
                return jsonify({'error': 'Watchlist item not found'}), 404
            conn.commit()
        
        return jsonify({'message': 'Removed from watchlist successfully'})
        
    except Exception as e:
        logger.error(f"Error removing from watchlist: {e}")
        return jsonify({'error': str(e)}), 500

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
            return jsonify({
                'coins': [],
                'total': total_coins,
                'page': page,
                'per_page': per_page
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
        print(f"Error in get_all_coins: {str(e)}")
        return jsonify({
            'coins': [],
            'total': 500,
            'page': 1,
            'per_page': 50,
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