import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Plus, 
  Search,  
  Trash2, 
  BarChart3,
  PieChart,
  Download,
  RefreshCw,
  DollarSign,
  Activity,
  AlertCircle,
  X
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5000/api';

const CryptoPortfolioTracker = () => {
  // State management
  const [activeTab, setActiveTab] = useState('portfolio');
  const [portfolio, setPortfolio] = useState([]);
  const [portfolioSummary, setPortfolioSummary] = useState({});
  const [watchlist, setWatchlist] = useState([]);
  const [coins, setCoins] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [portfolioAnalytics, setPortfolioAnalytics] = useState(null);
  const [marketAnalytics, setMarketAnalytics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  // Form states
  const [showAddForm, setShowAddForm] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [addForm, setAddForm] = useState({
    coin_id: '',
    coin_name: '',
    symbol: '',
    quantity: '',
    purchase_price: '',
    notes: ''
  });

  // API helper function
  const apiCall = async (endpoint, options = {}) => {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      return await response.json();
    } catch (err) {
      console.error('API call failed:', err);
      setError(`API Error: ${err.message}`);
      throw err;
    }
  };

  // Load initial data
  useEffect(() => {
    loadPortfolio();
    loadWatchlist();
    loadCoins();
  }, []);

  // Load portfolio data from backend
  const loadPortfolio = async () => {
    try {
      setLoading(true);
      const data = await apiCall('/portfolio');
      setPortfolio(data.portfolio || []);
      setPortfolioSummary(data.summary || {});
    } catch (err) {
      console.error('Failed to load portfolio:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load watchlist
  const loadWatchlist = async () => {
    try {
      const data = await apiCall('/watchlist');
      setWatchlist(data.watchlist || []);
    } catch (err) {
      console.error('Failed to load watchlist:', err);
    }
  };

  // Load all coins
  const loadCoins = async () => {
    try {
      const data = await apiCall('/coins/all?per_page=50');
      setCoins(data.coins || []);
    } catch (err) {
      console.error('Failed to load coins:', err);
    }
  };

  // Load portfolio analytics
  const loadPortfolioAnalytics = async () => {
    try {
      setLoading(true);
      const data = await apiCall('/analytics/portfolio');
      setPortfolioAnalytics(data.analytics);
    } catch (err) {
      console.error('Failed to load portfolio analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  // Load market analytics
  const loadMarketAnalytics = async () => {
    try {
      setLoading(true);
      const data = await apiCall('/analytics/market');
      setMarketAnalytics(data.market_analytics);
    } catch (err) {
      console.error('Failed to load market analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  // Search coins
  const searchCoins = async (query) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      const data = await apiCall(`/coins/search?q=${encodeURIComponent(query)}&limit=10`);
      setSearchResults(data.results || []);
    } catch (err) {
      console.error('Search failed:', err);
    }
  };

  // Add to portfolio
  const addToPortfolio = async (e) => {
    e.preventDefault();
    
    if (!addForm.coin_id || !addForm.quantity) {
      setError('Coin and quantity are required');
      return;
    }

    try {
      setLoading(true);
      await apiCall('/portfolio', {
        method: 'POST',
        body: JSON.stringify(addForm)
      });
      
      setShowAddForm(false);
      setAddForm({
        coin_id: '',
        coin_name: '',
        symbol: '',
        quantity: '',
        purchase_price: '',
        notes: ''
      });
      loadPortfolio();
      setError('');
    } catch (err) {
      console.error('Failed to add to portfolio:', err);
    } finally {
      setLoading(false);
    }
  };

  // Delete portfolio item
  const deletePortfolioItem = async (id) => {
    if (!window.confirm('Are you sure you want to delete this portfolio item?')) return;

    try {
      await apiCall(`/portfolio/${id}`, { method: 'DELETE' });
      loadPortfolio();
    } catch (err) {
      console.error('Failed to delete portfolio item:', err);
    }
  };

  // Remove from watchlist
  const removeFromWatchlist = async (id) => {
    try {
      await apiCall(`/watchlist/${id}`, { method: 'DELETE' });
      loadWatchlist();
    } catch (err) {
      console.error('Failed to remove from watchlist:', err);
    }
  };

  // Export portfolio
  const exportPortfolio = async (format = 'json') => {
    try {
      const data = await apiCall(`/export/portfolio?format=${format}`);
      
      const blob = new Blob([format === 'csv' ? data.data : JSON.stringify(data.data, null, 2)], {
        type: format === 'csv' ? 'text/csv' : 'application/json'
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = data.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
    }
  };

  // Format currency
  const formatCurrency = (amount) => {
    if (!amount && amount !== 0) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 6
    }).format(amount);
  };

  // Format percentage
  const formatPercentage = (value) => {
    const num = Number(value);
    if (isNaN(num)) return 'N/A';
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
  };

  // Portfolio Tab Component
  const PortfolioTab = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">My Portfolio</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddForm(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <Plus size={16} />
            Add Coin
          </button>
          <button
            onClick={() => exportPortfolio('json')}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <Download size={16} />
            Export
          </button>
        </div>
      </div>

      {/* Portfolio Summary */}
      {portfolioSummary && portfolio.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Value</p>
                <p className="text-2xl font-bold text-green-600">
                  {formatCurrency(portfolioSummary.total_value)}
                </p>
              </div>
              <DollarSign className="h-8 w-8 text-green-500" />
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total P&L</p>
                <p className={`text-2xl font-bold ${portfolioSummary.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(portfolioSummary.total_profit_loss)}
                </p>
                <p className={`text-sm ${portfolioSummary.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatPercentage(portfolioSummary.total_profit_loss_percentage)}
                </p>
              </div>
              {portfolioSummary.total_profit_loss >= 0 ? 
                <TrendingUp className="h-8 w-8 text-green-500" /> : 
                <TrendingDown className="h-8 w-8 text-red-500" />
              }
            </div>
          </div>
          <div className="bg-white p-4 rounded-lg shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Holdings</p>
                <p className="text-2xl font-bold text-blue-600">
                  {portfolioSummary.total_holdings}
                </p>
              </div>
              <PieChart className="h-8 w-8 text-blue-500" />
            </div>
          </div>
        </div>
      )}

      {portfolio.length === 0 ? (
        <div className="text-center py-12">
          <DollarSign size={48} className="mx-auto text-gray-400 mb-4" />
          <p className="text-gray-600">No coins in your portfolio yet. Add some to get started!</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Coin</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Holdings</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">24h Change</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">P&L</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {portfolio.map((item) => (
                  <tr key={item.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <div className="font-medium text-gray-900">{item.coin_name}</div>
                        <div className="text-sm text-gray-500">{item.symbol}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {parseFloat(item.quantity).toFixed(8)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {formatCurrency(item.current_price)}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900">
                      {formatCurrency(item.current_value)}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <span className={`flex items-center ${
                        item.change_24h >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {item.change_24h >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                        {formatPercentage(item.change_24h)}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm">
                      {item.profit_loss !== null ? (
                        <div className={item.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                          <div>{formatCurrency(item.profit_loss)}</div>
                          <div className="text-xs">
                            {formatPercentage(item.profit_loss_percentage)}
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400">N/A</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm">
                      <button
                        onClick={() => deletePortfolioItem(item.id)}
                        className="text-red-600 hover:text-red-900"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );

  // Market Tab Component (unchanged)
  const MarketTab = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Market Overview</h2>
        <button
          onClick={loadCoins}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <BarChart3 className="text-blue-600" size={24} />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Total Coins</p>
              <p className="text-xl font-semibold">{coins.length}</p>
            </div>
          </div>
        </div>
      </div>
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-medium">Top Cryptocurrencies</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Coin</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">24h Change</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Market Cap</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {coins.slice(0, 20).map((coin) => (
                <tr key={coin.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {coin.market_cap_rank}
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <div className="font-medium text-gray-900">{coin.name}</div>
                      <div className="text-sm text-gray-500">{coin.symbol}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {formatCurrency(coin.current_price)}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <span className={`flex items-center ${
                      coin.price_change_percentage_24h >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {coin.price_change_percentage_24h >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                      {formatPercentage(coin.price_change_percentage_24h)}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {formatCurrency(coin.market_cap)}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    <button
                      onClick={() => {
                        setAddForm(prev => ({
                          ...prev,
                          coin_id: coin.id,
                          coin_name: coin.name,
                          symbol: coin.symbol
                        }));
                        setShowAddForm(true);
                      }}
                      className="text-blue-600 hover:text-blue-900 mr-2"
                    >
                      <Plus size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // Analytics Tab Component (unchanged)
  const AnalyticsTab = () => {
    useEffect(() => {
      if (activeTab === 'analytics') {
        loadPortfolioAnalytics();
        loadMarketAnalytics();
      }
    }, [activeTab]);

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-900">Analytics</h2>
          <button
            onClick={() => {
              loadPortfolioAnalytics();
              loadMarketAnalytics();
            }}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>

        {portfolioAnalytics && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center">
                <div className="p-2 bg-green-100 rounded-lg">
                  <DollarSign className="text-green-600" size={24} />
                </div>
                <div className="ml-4">
                  <p className="text-sm text-gray-500">Total Value</p>
                  <p className="text-xl font-semibold">{formatCurrency(portfolioAnalytics.total_value)}</p>
                </div>
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <TrendingUp className="text-blue-600" size={24} />
                </div>
                <div className="ml-4">
                  <p className="text-sm text-gray-500">Total P&L</p>
                  <p className={`text-xl font-semibold ${
                    portfolioAnalytics.total_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {formatCurrency(portfolioAnalytics.total_profit_loss)}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center">
                <div className="p-2 bg-yellow-100 rounded-lg">
                  <Activity className="text-yellow-600" size={24} />
                </div>
                <div className="ml-4">
                  <p className="text-sm text-gray-500">24h Change</p>
                  <p className={`text-xl font-semibold ${
                    portfolioAnalytics.daily_change >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {formatCurrency(portfolioAnalytics.daily_change)}
                  </p>
                </div>
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="flex items-center">
                <div className="p-2 bg-purple-100 rounded-lg">
                  <PieChart className="text-purple-600" size={24} />
                </div>
                <div className="ml-4">
                  <p className="text-sm text-gray-500">Holdings</p>
                  <p className="text-xl font-semibold">{portfolioAnalytics.holdings_count}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {portfolioAnalytics?.allocation && (
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Portfolio Allocation</h3>
            <div className="space-y-3">
              {portfolioAnalytics.allocation.slice(0, 10).map((item) => (
                <div key={item.coin_id} className="flex items-center justify-between">
                  <div className="flex items-center">
                    <div className="w-4 h-4 bg-blue-500 rounded mr-3"></div>
                    <span className="font-medium">{item.coin_name}</span>
                    <span className="text-gray-500 ml-2">({item.symbol})</span>
                  </div>
                  <div className="flex items-center">
                    <span className="text-sm text-gray-600 mr-2">
                      {item.percentage.toFixed(1)}%
                    </span>
                    <span className="font-medium">
                      {formatCurrency(item.value)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Add Coin Form Modal (unchanged)
  const AddCoinModal = () => (
    showAddForm && (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-6 w-full max-w-md">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-medium">Add Coin to Portfolio</h3>
            <button
              onClick={() => setShowAddForm(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={20} />
            </button>
          </div>

          <form onSubmit={addToPortfolio} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Coin
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    searchCoins(e.target.value);
                  }}
                  placeholder="Search for a coin..."
                  className="w-full p-2 border rounded-lg pl-10"
                />
                <Search className="absolute left-3 top-2.5 text-gray-400" size={16} />
              </div>
              
              {searchResults.length > 0 && (
                <div className="mt-2 border rounded-lg max-h-40 overflow-y-auto">
                  {searchResults.map((coin) => (
                    <button
                      key={coin.id}
                      type="button"
                      onClick={() => {
                        setAddForm(prev => ({
                          ...prev,
                          coin_id: coin.id,
                          coin_name: coin.name,
                          symbol: coin.symbol
                        }));
                        setSearchQuery('');
                        setSearchResults([]);
                      }}
                      className="w-full p-2 text-left hover:bg-gray-50 flex items-center justify-between"
                    >
                      <div>
                        <div className="font-medium">{coin.name}</div>
                        <div className="text-sm text-gray-500">{coin.symbol}</div>
                      </div>
                      {coin.market_cap_rank && (
                        <span className="text-xs text-gray-400">#{coin.market_cap_rank}</span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {addForm.coin_name && (
              <div className="p-3 bg-blue-50 rounded-lg">
                <div className="font-medium">{addForm.coin_name}</div>
                <div className="text-sm text-gray-600">{addForm.symbol}</div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quantity *
              </label>
              <input
                type="number"
                step="any"
                value={addForm.quantity}
                onChange={(e) => setAddForm(prev => ({ ...prev, quantity: e.target.value }))}
                className="w-full p-2 border rounded-lg"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Purchase Price (Optional)
              </label>
              <input
                type="number"
                step="any"
                value={addForm.purchase_price}
                onChange={(e) => setAddForm(prev => ({ ...prev, purchase_price: e.target.value }))}
                className="w-full p-2 border rounded-lg"
                placeholder="0.00"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes (Optional)
              </label>
              <textarea
                value={addForm.notes}
                onChange={(e) => setAddForm(prev => ({ ...prev, notes: e.target.value }))}
                className="w-full p-2 border rounded-lg"
                rows="3"
                placeholder="Add any notes..."
              />
            </div>

            <div className="flex gap-2 pt-4">
              <button
                type="submit"
                disabled={!addForm.coin_id || !addForm.quantity || loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white py-2 rounded-lg"
              >
                {loading ? 'Adding...' : 'Add to Portfolio'}
              </button>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    )
  );

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <DollarSign className="text-blue-600 mr-2" size={24} />
              <h1 className="text-xl font-bold text-gray-900">Crypto Portfolio Tracker</h1>
            </div>
            
            <nav className="flex space-x-8">
              {[
                { id: 'portfolio', label: 'Portfolio', icon: DollarSign },
                { id: 'market', label: 'Market', icon: BarChart3 },
                { id: 'analytics', label: 'Analytics', icon: PieChart }
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg transition-colors ${
                    activeTab === id
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                  }`}
                >
                  <Icon size={16} />
                  {label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex">
              <AlertCircle className="text-red-400 mr-2" size={20} />
              <div>
                <h3 className="text-sm font-medium text-red-800">Error</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
              <button
                onClick={() => setError('')}
                className="ml-auto text-red-400 hover:text-red-600"
              >
                <X size={16} />
              </button>
            </div>
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="animate-spin text-blue-600 mr-2" size={20} />
            <span className="text-gray-600">Loading...</span>
          </div>
        )}

        {/* Tab Content */}
        {activeTab === 'portfolio' && <PortfolioTab />}
        {activeTab === 'market' && <MarketTab />}
        {activeTab === 'analytics' && <AnalyticsTab />}
      </main>

      {/* Add Coin Modal */}
      <AddCoinModal />
    </div>
  );
};

export default CryptoPortfolioTracker;