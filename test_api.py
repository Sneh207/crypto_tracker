import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("-" * 50)

def test_search():
    """Test search functionality"""
    print("Testing search endpoint...")
    response = requests.get(f"{BASE_URL}/search?q=bitcoin")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Found {len(data['results'])} results")
    for coin in data['results'][:3]:
        print(f"  - {coin['name']} ({coin['symbol']}) - ID: {coin['id']}")
    print("-" * 50)

def test_price():
    """Test price endpoint"""
    print("Testing price endpoint...")
    response = requests.get(f"{BASE_URL}/price/bitcoin")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Bitcoin price: ${data['price']:,.2f}")
        print(f"24h change: {data['change_24h']:.2f}%")
    print("-" * 50)

def test_history():
    """Test history endpoint"""
    print("Testing history endpoint (last 7 days)...")
    response = requests.get(f"{BASE_URL}/history/bitcoin?days=7")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Retrieved {len(data['data'])} days of data")
        if data['data']:
            latest = data['data'][-1]
            print(f"Latest: {latest['date']} - ${latest['price']:,.2f}")
    print("-" * 50)

def test_portfolio():
    """Test portfolio operations"""
    print("Testing portfolio operations...")
    
    # Add a coin to portfolio
    portfolio_data = {
        "coin_id": "bitcoin",
        "coin_name": "Bitcoin",
        "symbol": "BTC",
        "quantity": 0.5,
        "purchase_price": 45000,
        "notes": "Test purchase"
    }
    
    print("Adding Bitcoin to portfolio...")
    response = requests.post(f"{BASE_URL}/portfolio", json=portfolio_data)
    print(f"Add Status: {response.status_code}")
    
    if response.status_code == 201:
        portfolio_id = response.json()['id']
        print(f"Added with ID: {portfolio_id}")
        
        # Get portfolio
        print("Getting portfolio...")
        response = requests.get(f"{BASE_URL}/portfolio")
        print(f"Get Status: {response.status_code}")
        
        if response.status_code == 200:
            portfolio = response.json()['portfolio']
            print(f"Portfolio has {len(portfolio)} items")
            for item in portfolio:
                print(f"  - {item['coin_name']}: {item['quantity']} {item['symbol']}")
                if item['current_price']:
                    print(f"    Current value: ${item['current_value']:,.2f}")
        
        # Update portfolio item
        print("Updating portfolio item...")
        update_data = {"quantity": 0.75, "notes": "Updated test purchase"}
        response = requests.put(f"{BASE_URL}/portfolio/{portfolio_id}", json=update_data)
        print(f"Update Status: {response.status_code}")
        
        # Delete portfolio item
        print("Deleting portfolio item...")
        response = requests.delete(f"{BASE_URL}/portfolio/{portfolio_id}")
        print(f"Delete Status: {response.status_code}")
    
    print("-" * 50)

if __name__ == "__main__":
    print("Crypto Portfolio Tracker API Test")
    print("=" * 50)
    
    try:
        test_health()
        test_search()
        test_price()
        test_history()
        test_portfolio()
        
        print("All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API server.")
        print("Make sure the server is running with: python app.py")
    except Exception as e:
        print(f"Error during testing: {e}")