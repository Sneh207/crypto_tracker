import mysql.connector
from mysql.connector import Error
import requests
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from functools import wraps
import time
from requests.exceptions import Timeout, RequestException
import threading
from collections import defaultdict
import statistics

app = Flask(__name__)
CORS(app)

# Database configuration
from dotenv import load_dotenv

load_dotenv()

# Environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'crypto_tracker')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'your_password')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
COINGECKO_API_URL = os.getenv('COINGECKO_API_URL', 'https://api.coingecko.com/api/v3')

from mysql.connector.pooling import MySQLConnectionPool

# Database configuration
dbconfig = {
    "host": DB_HOST,
    "database": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "port": DB_PORT,
    "autocommit": True,
    "use_unicode": True,
    "charset": "utf8mb4"
}

try:
    connection_pool = MySQLConnectionPool(
        pool_name="crypto_pool",
        pool_size=10,
        pool_reset_session=True,
        **dbconfig
    )
    print("✓ Database connection pool created successfully")
except Error as e:
    print(f"✗ Error creating connection pool: {e}")
    exit(1)

# Cache for storing coin data
coin_cache = {}
cache_lock = threading.Lock()
cache_expiry = {}

# --- CoinGecko API response cache ---
coingecko_response_cache = {}
COINGECKO_CACHE_TTL = 300  # seconds (was 60)

coin_price_cache = {}
COIN_PRICE_CACHE_TTL = 300  # seconds (was 60)

def get_cached_coingecko_response(key, fetch_func):
    """Cache CoinGecko API responses in memory for COINGECKO_CACHE_TTL seconds."""
    now = time.time()
    cache_entry = coingecko_response_cache.get(key)
    if cache_entry and now - cache_entry['timestamp'] < COINGECKO_CACHE_TTL:
        return cache_entry['data']
    data = fetch_func()
    if data is not None:
        coingecko_response_cache[key] = {'data': data, 'timestamp': now}
    return data

def get_db_connection():
    """Get database connection from pool"""
    try:
        return connection_pool.get_connection()
    except Error as e:
        print(f"Error getting connection from pool: {e}")
        return None

def init_database():
    """Initialize database with enhanced tables"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        # Enhanced portfolio table
        create_portfolio_table = """
        CREATE TABLE IF NOT EXISTS portfolio (
            id INT AUTO_INCREMENT PRIMARY KEY,
            coin_id VARCHAR(100) NOT NULL,
            coin_name VARCHAR(100) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            purchase_price DECIMAL(20, 8),
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_coin_id (coin_id),
            INDEX idx_symbol (symbol)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        
        # Coin cache table for faster searches
        create_coin_cache_table = """
        CREATE TABLE IF NOT EXISTS coin_cache (
            id VARCHAR(100) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            market_cap_rank INT,
            current_price DECIMAL(20, 8),
            market_cap BIGINT,
            price_change_24h DECIMAL(10, 4),
            price_change_percentage_24h DECIMAL(10, 4),
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_name (name),
            INDEX idx_symbol (symbol),
            INDEX idx_rank (market_cap_rank)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        
        # Watchlist table
        create_watchlist_table = """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INT AUTO_INCREMENT PRIMARY KEY,
            coin_id VARCHAR(100) NOT NULL,
            coin_name VARCHAR(100) NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_coin (coin_id),
            INDEX idx_coin_id (coin_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        
        cursor.execute(create_portfolio_table)
        cursor.execute(create_coin_cache_table)
        cursor.execute(create_watchlist_table)
        
        print("✓ Database tables initialized successfully")
        return True
        
    except Error as e:
        print(f"✗ Error initializing database: {e}")
        return False
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def rate_limit(seconds=1):
    """Enhanced rate limiting decorator"""
    def decorator(f):
        last_called = {}
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            now = time.time()
            key = f.__name__
            if key in last_called:
                elapsed = now - last_called[key]
                if elapsed < seconds:
                    time.sleep(seconds - elapsed)
            result = f(*args, **kwargs)
            last_called[key] = time.time()
            return result
        return wrapper
    return decorator

def make_api_request(url, params=None, timeout=15):
    """Enhanced API request handler"""
    headers = {
        'User-Agent': 'CryptoPortfolioTracker/1.0',
        'Accept': 'application/json'
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except Timeout:
        print(f"Request timed out: {url}")
        return None
    except RequestException as e:
        print(f"API request failed: {e}")
        return None

@rate_limit(1)
def get_coin_price(coin_id):
    """Get current price with enhanced data and caching"""
    now = time.time()
    # Check cache first
    cache_entry = coin_price_cache.get(coin_id)
    if cache_entry and now - cache_entry['timestamp'] < COIN_PRICE_CACHE_TTL:
        return cache_entry['data']
    try:
        url = f"{COINGECKO_API_URL}/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_24hr_vol': 'true',
            'include_market_cap': 'true',
            'include_last_updated_at': 'true'
        }
        data = make_api_request(url, params)
        if data and coin_id in data:
            coin_data = data[coin_id]
            result = {
                'price': coin_data.get('usd', 0),
                'change_24h': coin_data.get('usd_24h_change', 0),
                'volume_24h': coin_data.get('usd_24h_vol', 0),
                'market_cap': coin_data.get('usd_market_cap', 0),
                'last_updated': coin_data.get('last_updated_at', time.time())
            }
            # Save to cache
            coin_price_cache[coin_id] = {'data': result, 'timestamp': now}
            return result
        return None
    except Exception as e:
        print(f"Error fetching price for {coin_id}: {e}")
        return None

@rate_limit(2)
def get_coin_history(coin_id, days=365):
    """Get historical price data with more details"""
    try:
        url = f"{COINGECKO_API_URL}/coins/{coin_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': 'daily' if days > 90 else 'hourly'
        }
        data = make_api_request(url, params)
        if not data or 'prices' not in data:
            return []
        prices = []
        for i, price_data in enumerate(data['prices']):
            timestamp = price_data[0]
            price = price_data[1]
            volume = data.get('total_volumes', [[0, 0]])[i][1] if i < len(data.get('total_volumes', [])) else 0
            prices.append({
                'timestamp': timestamp,
                'date': datetime.fromtimestamp(timestamp / 1000).strftime('%Y-%m-%d'),
                'price': price,
                'volume': volume
            })
        return prices
    except Exception as e:
        print(f"Error fetching history for {coin_id}: {e}")
        return []

# --- MODIFIED: get_coins_list now uses cache ---
@rate_limit(1)
def get_coins_list(page=1, per_page=250):
    """Get comprehensive list of all coins, with caching"""
    def fetch():
        url = f"{COINGECKO_API_URL}/coins/markets"
        params = {
            'vs_currency': 'usd',
            'order': 'market_cap_desc',
            'per_page': per_page,
            'page': page,
            'sparkline': 'false',
            'price_change_percentage': '24h'
        }
        data = make_api_request(url, params)
        if not data:
            return []
        coins = []
        for  coin in data:
            coins.append({
                'id': coin['id'],
                'name': coin['name'],
                'symbol': coin['symbol'].upper(),
                'current_price': coin['current_price'],
                'market_cap': coin['market_cap'],
                'market_cap_rank': coin['market_cap_rank'],
                'price_change_24h': coin['price_change_24h'],
                'price_change_percentage_24h': coin['price_change_percentage_24h'],
                'image': coin['image']
            })
        # Cache the results in DB as well
        update_coin_cache(coins)
        return coins

    cache_key = f"coins_list_{page}_{per_page}"
    return get_cached_coingecko_response(cache_key, fetch)

def update_coin_cache(coins):
    """Update coin cache in database"""
    connection = get_db_connection()
    if not connection:
        return
    try:
        cursor = connection.cursor()
        # Clear old cache
        cursor.execute("DELETE FROM coin_cache WHERE last_updated < DATE_SUB(NOW(), INTERVAL 1 HOUR)")
        # Insert new data
        insert_query = """
        INSERT INTO coin_cache (id, name, symbol, market_cap_rank, current_price, 
                               market_cap, price_change_24h, price_change_percentage_24h)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
        name = VALUES(name),
        symbol = VALUES(symbol),
        market_cap_rank = VALUES(market_cap_rank),
        current_price = VALUES(current_price),
        market_cap = VALUES(market_cap),
        price_change_24h = VALUES(price_change_24h),
        price_change_percentage_24h = VALUES(price_change_percentage_24h)
        """
        for coin in coins:
            values = (
                coin['id'], coin['name'], coin['symbol'], coin['market_cap_rank'],
                coin['current_price'], coin['market_cap'], coin['price_change_24h'],
                coin['price_change_percentage_24h']
            )
            cursor.execute(insert_query, values)
    except Error as e:
        print(f"Error updating coin cache: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def search_coins_in_cache(query, limit=50):
    """Search coins in local cache"""
    connection = get_db_connection()
    if not connection:
        return []
    try:
        cursor = connection.cursor(dictionary=True)
        # Search by name or symbol
        search_query = """
        SELECT * FROM coin_cache 
        WHERE name LIKE %s OR symbol LIKE %s 
        ORDER BY market_cap_rank ASC 
        LIMIT %s
        """
        search_term = f"%{query}%"
        cursor.execute(search_query, (search_term, search_term, limit))
        return cursor.fetchall()
    except Error as e:
        print(f"Error searching coins in cache: {e}")
        return []
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

# API Routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

@app.route('/api/coins/all', methods=['GET'])
def get_all_coins():
    """Get all coins with market data"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 100, type=int), 250)
    # Try to get from cache first
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            offset = (page - 1) * per_page
            cursor.execute("""
                SELECT * FROM coin_cache 
                WHERE last_updated > DATE_SUB(NOW(), INTERVAL 1 HOUR)
                ORDER BY market_cap_rank ASC 
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            cached_coins = cursor.fetchall()
            if cached_coins:
                return jsonify({
                    'coins': cached_coins,
                    'page': page,
                    'per_page': per_page,
                    'source': 'cache'
                })
        except Error as e:
            print(f"Error fetching from cache: {e}")
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    # Fetch fresh data if cache is empty or old
    coins = get_coins_list(page, per_page)
    return jsonify({
        'coins': coins,
        'page': page,
        'per_page': per_page,
        'total': len(coins),
        'source': 'api'
    })

@app.route('/api/coins/search', methods=['GET'])
def search_coins():
    """Enhanced search for coins"""
    query = request.args.get('q', '').strip()
    limit = min(request.args.get('limit', 50, type=int), 100)
    if not query:
        return jsonify({'error': 'Search query is required'}), 400
    if len(query) < 1:
        return jsonify({'results': []})
    # Search in cache first
    cached_results = search_coins_in_cache(query, limit)
    if cached_results:
        return jsonify({
            'results': cached_results,
            'source': 'cache',
            'query': query
        })
    # Fallback to API search
    try:
        url = f"{COINGECKO_API_URL}/search"
        params = {'query': query}
        data = make_api_request(url, params)
        if not data or 'coins' not in data:
            return jsonify({'results': []})
        results = []
        for coin in data['coins'][:limit]:
            results.append({
                'id': coin['id'],
                'name': coin['name'],
                'symbol': coin['symbol'].upper(),
                'market_cap_rank': coin.get('market_cap_rank'),
                'thumb': coin.get('thumb')
            })
        return jsonify({
            'results': results,
            'source': 'api',
            'query': query
        })
    except Exception as e:
        print(f"Error in coin search: {e}")
        return jsonify({'error': 'Search failed'}), 500

@app.route('/api/coins/<coin_id>/price', methods=['GET'])
def get_coin_current_price(coin_id):
    """Get current price and market data for any coin"""
    price_data = get_coin_price(coin_id)
    if price_data:
        return jsonify({
            'coin_id': coin_id,
            'current_price': price_data['price'],
            'price_change_24h': price_data['change_24h'],
            'volume_24h': price_data['volume_24h'],
            'market_cap': price_data['market_cap'],
            'last_updated': price_data['last_updated'],
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({'error': 'Unable to fetch price data'}), 404

@app.route('/api/coins/<coin_id>/history', methods=['GET'])
def get_coin_price_history(coin_id):
    """Get price history for any coin"""
    days = request.args.get('days', 365, type=int)
    # Validate days parameter
    if days > 365:
        days = 365
    elif days < 1:
        days = 1
    history = get_coin_history(coin_id, days)
    if history:
        # Calculate additional metrics
        if len(history) >= 2:
            latest_price = history[-1]['price']
            oldest_price = history[0]['price']
            total_change = ((latest_price - oldest_price) / oldest_price) * 100
            # Find highest and lowest prices
            prices = [item['price'] for item in history]
            highest_price = max(prices)
            lowest_price = min(prices)
        else:
            total_change = 0
            highest_price = history[0]['price'] if history else 0
            lowest_price = history[0]['price'] if history else 0
        return jsonify({
            'coin_id': coin_id,
            'days': days,
            'data': history,
            'summary': {
                'total_change_percentage': total_change,
                'highest_price': highest_price,
                'lowest_price': lowest_price,
                'data_points': len(history)
            }
        })
    else:
        return jsonify({'error': 'Unable to fetch price history'}), 404

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get portfolio with enhanced analytics"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, coin_id, coin_name, symbol, quantity, 
                   purchase_price, purchase_date, notes,
                   created_at, updated_at
            FROM portfolio
            ORDER BY created_at DESC
        """)
        portfolio = cursor.fetchall()
        # Calculate portfolio metrics
        total_value = 0
        total_invested = 0
        total_profit_loss = 0
        for item in portfolio:
            price_data = get_coin_price(item['coin_id'])
            if price_data:
                current_price = price_data['price']
                item['current_price'] = current_price
                item['current_value'] = float(item['quantity']) * current_price
                item['change_24h'] = price_data['change_24h']
                item['volume_24h'] = price_data['volume_24h']
                item['market_cap'] = price_data['market_cap']
                total_value += item['current_value']
                if item['purchase_price']:
                    purchase_value = float(item['quantity']) * float(item['purchase_price'])
                    item['purchase_value'] = purchase_value
                    item['profit_loss'] = item['current_value'] - purchase_value
                    item['profit_loss_percentage'] = ((current_price - float(item['purchase_price'])) / float(item['purchase_price'])) * 100
                    total_invested += purchase_value
                    total_profit_loss += item['profit_loss']
                else:
                    item['purchase_value'] = None
                    item['profit_loss'] = None
                    item['profit_loss_percentage'] = None
            else:
                item['current_price'] = None
                item['current_value'] = None
                item['change_24h'] = None
                item['volume_24h'] = None
                item['market_cap'] = None
                item['purchase_value'] = None
                item['profit_loss'] = None
                item['profit_loss_percentage'] = None
        # Portfolio summary
        portfolio_summary = {
            'total_value': total_value,
            'total_invested': total_invested,
            'total_profit_loss': total_profit_loss,
            'total_profit_loss_percentage': ((total_profit_loss / total_invested) * 100) if total_invested > 0 else 0,
            'total_holdings': len(portfolio)
        }
        return jsonify({
            'portfolio': portfolio,
            'summary': portfolio_summary
        })
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/portfolio', methods=['POST'])
def add_to_portfolio():
    """Add coin to portfolio with validation"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    # Validate required fields
    required_fields = ['coin_id', 'coin_name', 'symbol', 'quantity']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    # Validate quantity
    try:
        quantity = float(data['quantity'])
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity format'}), 400
    # Validate purchase price
    purchase_price = None
    if data.get('purchase_price'):
        try:
            purchase_price = float(data['purchase_price'])
            if purchase_price < 0:
                return jsonify({'error': 'Purchase price cannot be negative'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid purchase price format'}), 400
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor()
        # Check if coin already exists in portfolio
        cursor.execute("SELECT id, quantity FROM portfolio WHERE coin_id = %s", (data['coin_id'],))
        existing = cursor.fetchone()
        if existing and request.args.get('merge', 'false').lower() == 'true':
            # Merge with existing holding
            new_quantity = float(existing[1]) + quantity
            # Calculate weighted average price if both have purchase prices
            if purchase_price and existing[1]:
                cursor.execute("SELECT purchase_price FROM portfolio WHERE id = %s", (existing[0],))
                existing_price = cursor.fetchone()[0]
                if existing_price:
                    weighted_price = ((float(existing[1]) * float(existing_price)) + (quantity * purchase_price)) / new_quantity
                    purchase_price = weighted_price
            update_query = """
            UPDATE portfolio 
            SET quantity = %s, purchase_price = %s, notes = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """
            cursor.execute(update_query, (new_quantity, purchase_price, data.get('notes', ''), existing[0]))
            return jsonify({
                'message': 'Position merged successfully',
                'id': existing[0],
                'merged': True
            })
        else:
            # Verify coin exists by making API call
            coin_data = get_coin_price(data['coin_id'])
            if not coin_data:
                return jsonify({'error': 'Invalid coin ID or coin not found'}), 400
            # Add as new position
            insert_query = """
            INSERT INTO portfolio (coin_id, coin_name, symbol, quantity, purchase_price, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            values = (
                data['coin_id'],
                data['coin_name'],
                data['symbol'].upper(),
                quantity,
                purchase_price,
                data.get('notes', '')
            )
            cursor.execute(insert_query, values)
            return jsonify({
                'message': 'Coin added to portfolio successfully',
                'id': cursor.lastrowid,
                'merged': False,
                'current_price': coin_data['price']
            }), 201
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/portfolio/<int:portfolio_id>', methods=['PUT'])
def update_portfolio_item(portfolio_id):
    """Update portfolio item"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor()
        # Check if portfolio item exists
        cursor.execute("SELECT id FROM portfolio WHERE id = %s", (portfolio_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Portfolio item not found'}), 404
        # Build update query dynamically
        update_fields = []
        values = []
        if 'quantity' in data:
            try:
                quantity = float(data['quantity'])
                if quantity <= 0:
                    return jsonify({'error': 'Quantity must be positive'}), 400
                update_fields.append('quantity = %s')
                values.append(quantity)
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid quantity format'}), 400
        if 'purchase_price' in data:
            if data['purchase_price'] is not None:
                try:
                    purchase_price = float(data['purchase_price'])
                    if purchase_price < 0:
                        return jsonify({'error': 'Purchase price cannot be negative'}), 400
                    update_fields.append('purchase_price = %s')
                    values.append(purchase_price)
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid purchase price format'}), 400
            else:
                update_fields.append('purchase_price = NULL')
        if 'notes' in data:
            update_fields.append('notes = %s')
            values.append(data['notes'])
        if not update_fields:
            return jsonify({'error': 'No valid fields to update'}), 400
        values.append(portfolio_id)
        update_query = f"UPDATE portfolio SET {', '.join(update_fields)} WHERE id = %s"
        cursor.execute(update_query, values)
        return jsonify({'message': 'Portfolio item updated successfully'})
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/portfolio/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio_item(portfolio_id):
    """Delete portfolio item"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor()
        # Check if portfolio item exists
        cursor.execute("SELECT id FROM portfolio WHERE id = %s", (portfolio_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Portfolio item not found'}), 404
        cursor.execute("DELETE FROM portfolio WHERE id = %s", (portfolio_id,))
        return jsonify({'message': 'Portfolio item deleted successfully'})
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    """Get watchlist with current prices"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, coin_id, coin_name, symbol, added_at
            FROM watchlist
            ORDER BY added_at DESC
        """)
        watchlist = cursor.fetchall()
        # Add current prices
        for item in watchlist:
            price_data = get_coin_price(item['coin_id'])
            if price_data:
                item['current_price'] = price_data['price']
                item['change_24h'] = price_data['change_24h']
                item['volume_24h'] = price_data['volume_24h']
            else:
                item['current_price'] = None
                item['change_24h'] = None
                item['volume_24h'] = None
        return jsonify({'watchlist': watchlist})
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/watchlist/<int:watchlist_id>', methods=['DELETE'])
def remove_from_watchlist(watchlist_id):
    """Remove coin from watchlist"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor()
        # Check if watchlist item exists
        cursor.execute("SELECT id FROM watchlist WHERE id = %s", (watchlist_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Watchlist item not found'}), 404
        cursor.execute("DELETE FROM watchlist WHERE id = %s", (watchlist_id,))
        return jsonify({'message': 'Coin removed from watchlist successfully'})
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/analytics/portfolio', methods=['GET'])
def get_portfolio_analytics():
    """Get detailed portfolio analytics"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT coin_id, coin_name, symbol, quantity, purchase_price, purchase_date
            FROM portfolio
        """)
        portfolio = cursor.fetchall()
        if not portfolio:
            return jsonify({'analytics': {}, 'message': 'No portfolio data found'})
        # Calculate comprehensive analytics
        analytics = {
            'total_value': 0,
            'total_invested': 0,
            'total_profit_loss': 0,
            'total_profit_loss_percentage': 0,
            'best_performer': None,
            'worst_performer': None,
            'largest_holding': None,
            'allocation': [],
            'daily_change': 0,
            'holdings_count': len(portfolio)
        }
        holdings_data = []
        daily_change_total = 0
        for item in portfolio:
            price_data = get_coin_price(item['coin_id'])
            if not price_data:
                continue
            current_price = price_data['price']
            current_value = float(item['quantity']) * current_price
            change_24h = price_data['change_24h']
            holding_data = {
                'coin_id': item['coin_id'],
                'coin_name': item['coin_name'], 
                'symbol': item['symbol'],
                'quantity': float(item['quantity']),
                'current_price': current_price,
                'current_value': current_value,
                'change_24h': change_24h,
                'daily_change_value': (current_value * change_24h / 100) if change_24h else 0
            }
            analytics['total_value'] += current_value
            daily_change_total += holding_data['daily_change_value']
            if item['purchase_price']:
                purchase_price = float(item['purchase_price'])
                purchase_value = float(item['quantity']) * purchase_price
                profit_loss = current_value - purchase_value
                profit_loss_percentage = ((current_price - purchase_price) / purchase_price) * 100
                holding_data.update({
                    'purchase_price': purchase_price,
                    'purchase_value': purchase_value,
                    'profit_loss': profit_loss,
                    'profit_loss_percentage': profit_loss_percentage
                })
                analytics['total_invested'] += purchase_value
                analytics['total_profit_loss'] += profit_loss
                # Track best and worst performers
                if not analytics['best_performer'] or profit_loss_percentage > analytics['best_performer']['profit_loss_percentage']:
                    analytics['best_performer'] = holding_data
                if not analytics['worst_performer'] or profit_loss_percentage < analytics['worst_performer']['profit_loss_percentage']:
                    analytics['worst_performer'] = holding_data
            holdings_data.append(holding_data)
        # Calculate remaining analytics
        if analytics['total_invested'] > 0:
            analytics['total_profit_loss_percentage'] = (analytics['total_profit_loss'] / analytics['total_invested']) * 100
        analytics['daily_change'] = daily_change_total
        analytics['daily_change_percentage'] = (daily_change_total / analytics['total_value']) * 100 if analytics['total_value'] > 0 else 0
        # Find largest holding by value
        if holdings_data:
            analytics['largest_holding'] = max(holdings_data, key=lambda x: x['current_value'])
            # Calculate allocation percentages
            for holding in holdings_data:
                allocation_percentage = (holding['current_value'] / analytics['total_value']) * 100
                analytics['allocation'].append({
                    'coin_id': holding['coin_id'],
                    'coin_name': holding['coin_name'],
                    'symbol': holding['symbol'],
                    'percentage': allocation_percentage,
                    'value': holding['current_value']
                })
            # Sort allocation by percentage
            analytics['allocation'].sort(key=lambda x: x['percentage'], reverse=True)
        return jsonify({
            'analytics': analytics,
            'holdings': holdings_data,
            'timestamp': datetime.now().isoformat()
        })
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/analytics/market', methods=['GET'])
def get_market_analytics():
    """Get market overview and trends, with caching"""
    try:
        # --- Use cache for top coins ---
        def fetch_top_coins():
            return get_coins_list(1, 10)
        top_coins = get_cached_coingecko_response("analytics_market_top10", fetch_top_coins)
        if not top_coins:
            return jsonify({'error': 'Unable to fetch market data'}), 500
        # Calculate market metrics
        total_market_cap = sum(coin['market_cap'] for coin in top_coins if coin['market_cap'])
        avg_24h_change = statistics.mean([coin['price_change_percentage_24h'] for coin in top_coins if coin['price_change_percentage_24h']])
        # Count gainers vs losers
        gainers = [coin for coin in top_coins if coin['price_change_percentage_24h'] and coin['price_change_percentage_24h'] > 0]
        losers = [coin for coin in top_coins if coin['price_change_percentage_24h'] and coin['price_change_percentage_24h'] < 0]
        market_sentiment = "bullish" if len(gainers) > len(losers) else "bearish" if len(losers) > len(gainers) else "neutral"
        analytics = {
            'top_coins': top_coins,
            'market_metrics': {
                'total_market_cap': total_market_cap,
                'average_24h_change': avg_24h_change,
                'gainers_count': len(gainers),
                'losers_count': len(losers),
                'market_sentiment': market_sentiment
            },
            'top_gainers': sorted([coin for coin in top_coins if coin['price_change_percentage_24h']], 
                                key=lambda x: x['price_change_percentage_24h'], reverse=True)[:5],
            'top_losers': sorted([coin for coin in top_coins if coin['price_change_percentage_24h']], 
                               key=lambda x: x['price_change_percentage_24h'])[:5]
        }
        return jsonify({
            'market_analytics': analytics,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching market analytics: {str(e)}'}), 500

@app.route('/api/compare', methods=['POST'])
def compare_coins():
    """Compare multiple coins"""
    data = request.get_json()
    if not data or 'coin_ids' not in data:
        return jsonify({'error': 'coin_ids array is required'}), 400
    coin_ids = data['coin_ids']
    if not isinstance(coin_ids, list) or len(coin_ids) < 2:
        return jsonify({'error': 'At least 2 coin IDs are required for comparison'}), 400
    if len(coin_ids) > 10:
        return jsonify({'error': 'Maximum 10 coins can be compared at once'}), 400
    days = data.get('days', 30)
    try:
        comparison_data = []
        for coin_id in coin_ids:
            # Get current price
            price_data = get_coin_price(coin_id)
            if not price_data:
                continue
            # Get historical data
            history = get_coin_history(coin_id, days)
            if not history:
                continue
            # Calculate metrics
            prices = [item['price'] for item in history]
            if len(prices) >= 2:
                period_change = ((prices[-1] - prices[0]) / prices[0]) * 100
                volatility = statistics.stdev(prices) if len(prices) > 1 else 0
                avg_volume = statistics.mean([item['volume'] for item in history])
            else:
                period_change = 0
                volatility = 0
                avg_volume = 0
            comparison_data.append({
                'coin_id': coin_id,
                'current_price': price_data['price'],
                'change_24h': price_data['change_24h'],
                'market_cap': price_data['market_cap'],
                'volume_24h': price_data['volume_24h'],
                'period_change': period_change,
                'volatility': volatility,
                'avg_volume': avg_volume,
                'highest_price': max(prices),
                'lowest_price': min(prices),
                'price_history': history[-30:]  # Last 30 data points for charts
            })
        if not comparison_data:
            return jsonify({'error': 'No valid coin data found for comparison'}), 404
        return jsonify({
            'comparison': comparison_data,
            'period_days': days,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Error comparing coins: {str(e)}'}), 500

@app.route('/api/alerts', methods=['GET'])
def get_price_alerts():
    """Get price alerts (placeholder for future implementation)"""
    return jsonify({
        'alerts': [],
        'message': 'Price alerts feature coming soon'
    })

@app.route('/api/export/portfolio', methods=['GET'])
def export_portfolio():
    """Export portfolio data"""
    format_type = request.args.get('format', 'json').lower()
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT coin_id, coin_name, symbol, quantity, purchase_price, 
                   purchase_date, notes, created_at
            FROM portfolio
            ORDER BY created_at DESC
        """)
        portfolio = cursor.fetchall()
        # Add current prices
        for item in portfolio:
            price_data = get_coin_price(item['coin_id'])
            if price_data:
                item['current_price'] = price_data['price']
                item['current_value'] = float(item['quantity']) * price_data['price']
                if item['purchase_price']:
                    item['profit_loss'] = item['current_value'] - (float(item['quantity']) * float(item['purchase_price']))
                    item['profit_loss_percentage'] = ((price_data['price'] - float(item['purchase_price'])) / float(item['purchase_price'])) * 100
        if format_type == 'csv':
            # Convert to CSV format
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=portfolio[0].keys() if portfolio else [])
            writer.writeheader()
            writer.writerows(portfolio)
            return jsonify({
                'data': output.getvalue(),
                'format': 'csv',
                'filename': f'portfolio_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            })
        else:
            return jsonify({
                'data': portfolio,
                'format': 'json',
                'filename': f'portfolio_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json',
                'exported_at': datetime.now().isoformat()
            })
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

@app.route('/api/stats', methods=['GET'])
def get_system_stats():
    """Get system statistics"""
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    try:
        cursor = connection.cursor()
        # Get portfolio stats
        cursor.execute("SELECT COUNT(*) FROM portfolio")
        portfolio_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM watchlist")
        watchlist_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM coin_cache")
        cached_coins = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(last_updated) FROM coin_cache")
        last_cache_update = cursor.fetchone()[0]
        stats = {
            'portfolio_holdings': portfolio_count,
            'watchlist_items': watchlist_count,
            'cached_coins': cached_coins,
            'last_cache_update': last_cache_update.isoformat() if last_cache_update else None,
            'api_source': 'CoinGecko',
            'uptime': datetime.now().isoformat()
        }
        return jsonify({'stats': stats})
    except Error as e:
        return jsonify({'error': f'Database error: {str(e)}'}), 500
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

def background_cache_update():
    """Background task to update coin cache periodically"""
    while True:
        try:
            print("Updating coin cache...")
            with cache_lock:  # Add thread lock
                # Update cache with top 500 coins
                for page in range(1, 3):  # Pages 1-2 (500 coins total)
                    coins = get_coins_list(page, 250)
                    if coins:
                        update_coin_cache(coins)
                    time.sleep(2)  # Rate limiting between pages
            print("Cache update completed")
            time.sleep(3600)  # Update every hour
        except Exception as e:
            print(f"Error in background cache update: {e}")
            time.sleep(600)  # Retry after 10 minutes on error

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def rate_limit_error(error):
    return jsonify({'error': 'Rate limit exceeded'}), 429

if __name__ == '__main__':
    print("🚀 Starting Crypto Portfolio Tracker")
    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        exit(1)
    # Start background cache update thread
    cache_thread = threading.Thread(target=background_cache_update, daemon=True)
    cache_thread.start()
    print("✓ Background cache update started")
    # Start Flask app
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('FLASK_PORT', 5000))
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    print(f"✓ Server starting on {host}:{port}")
    print(f"✓ Debug mode: {debug_mode}")
    print("✓ Available endpoints:")
    print("  - GET  /api/health")
    print("  - GET  /api/coins/all")
    print("  - GET  /api/coins/search")
    print("  - GET  /api/coins/<coin_id>/price")
    print("  - GET  /api/coins/<coin_id>/history")
    print("  - GET  /api/portfolio")
    print("  - POST /api/portfolio")
    print("  - PUT  /api/portfolio/<id>")
    print("  - DELETE /api/portfolio/<id>")
    print("  - GET  /api/watchlist")
    print("  - POST /api/watchlist")
    print("  - DELETE /api/watchlist/<id>")
    print("  - GET  /api/analytics/portfolio")
    print("  - GET  /api/analytics/market")
    print("  - POST /api/compare")
    print("  - GET  /api/export/portfolio")
    print("  - GET  /api/stats")
    print()
    print("🎯 Crypto Portfolio Tracker is ready!")
    app.run(host=host, port=port, debug=debug_mode)