import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  TrendingUp, 
  TrendingDown, 
  Plus, 
  Trash2, 
  BarChart3,
  RefreshCw,
  DollarSign,
  Activity,
  AlertCircle,
  X,
  LineChart
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:5000/api';

// Utility functions
const formatCurrency = (amount) => {
  if (!amount && amount !== 0) return 'N/A';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 6
  }).format(amount);
};

const formatPercentage = (value) => {
  const num = Number(value);
  if (isNaN(num)) return 'N/A';
  return `${num >= 0 ? '+' : ''}${num.toFixed(2)}%`;
};

const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  });
};

// Custom hooks
const useApi = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const apiCall = useCallback(async (endpoint, options = {}) => {
    try {
      setLoading(true);
      setError('');
      
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
      const errorMessage = `API Error: ${err.message}`;
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  return { apiCall, loading, error, setError };
};

// Components
const LoadingSpinner = ({ message = "Loading..." }) => (
  <div className="flex items-center justify-center py-12">
    <RefreshCw className="animate-spin text-blue-600 mr-2" size={24} />
    <span className="text-gray-600">{message}</span>
  </div>
);

const ErrorAlert = ({ error, onClose }) => (
  error && (
    <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-center">
      <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
      <span className="text-red-700">{error}</span>
      <button
        onClick={onClose}
        className="ml-auto text-red-400 hover:text-red-600"
      >
        <X size={16} />
      </button>
    </div>
  )
);

const CoinTableRow = React.memo(({ coin, index, page, perPage, onAddToPortfolio }) => (
  <tr className="hover:bg-gray-50">
    <td className="px-6 py-4 text-sm text-gray-900">
      #{((page - 1) * perPage) + index + 1}
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
        onClick={() => onAddToPortfolio(coin)}
        className="text-blue-600 hover:text-blue-900 mr-2"
        title="Add to Portfolio"
      >
        <Plus size={16} />
      </button>
    </td>
  </tr>
));

const PortfolioRow = React.memo(({ item, onRemove }) => (
  <tr className="hover:bg-gray-50">
    <td className="px-6 py-4">
      <div>
        <div className="font-medium text-gray-900">{item.coin_name}</div>
        <div className="text-sm text-gray-500">{item.symbol}</div>
      </div>
    </td>
    <td className="px-6 py-4 text-sm text-gray-900">
      {item.quantity}
    </td>
    <td className="px-6 py-4 text-sm text-gray-900">
      {formatCurrency(item.current_price)}
    </td>
    <td className="px-6 py-4 text-sm text-gray-900">
      {formatCurrency(item.quantity * item.current_price)}
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
      <button
        onClick={() => onRemove(item.id)}
        className="text-red-600 hover:text-red-900"
        title="Remove from Portfolio"
      >
        <Trash2 size={16} />
      </button>
    </td>
  </tr>
));

const WatchlistRow = React.memo(({ item, onAddToPortfolio, onRemove }) => (
  <tr className="hover:bg-gray-50">
    <td className="px-6 py-4">
      <div>
        <div className="font-medium text-gray-900">{item.coin_name}</div>
        <div className="text-sm text-gray-500">{item.symbol}</div>
      </div>
    </td>
    <td className="px-6 py-4 text-sm text-gray-900">
      {formatCurrency(item.current_price)}
    </td>
    <td className="px-6 py-4 text-sm">
      <span className={`flex items-center ${
        item.change_24h >= 0 ? 'text-green-600' : 'text-red-600'
      }`}>
        {item.change_24h >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
        {formatPercentage(item.change_24h)}
      </span>
    </td>
    <td className="px-6 py-4 text-sm text-gray-900">
      {formatCurrency(item.market_cap)}
    </td>
    <td className="px-6 py-4 text-sm text-gray-500">
      {formatDate(item.added_at)}
    </td>
    <td className="px-6 py-4 text-sm">
      <div className="flex gap-2">
        <button
          onClick={() => onAddToPortfolio(item)}
          className="text-blue-600 hover:text-blue-900"
          title="Add to Portfolio"
        >
          <Plus size={16} />
        </button>
        <button
          onClick={() => onRemove(item.id)}
          className="text-red-600 hover:text-red-900"
          title="Remove from Watchlist"
        >
          <Trash2 size={16} />
        </button>
      </div>
    </td>
  </tr>
));

const MarketTab = ({ onAddToPortfolio }) => {
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(50);
  const [coins, setCoins] = useState([]);
  const { apiCall, loading, error } = useApi();

  const fetchCoins = useCallback(async () => {
    try {
      const data = await apiCall(`/coins/all?page=${page}&per_page=${perPage}`);
      if (data.error) {
        throw new Error(data.error);
      }
      setCoins(data.coins || []);
    } catch (err) {
      setCoins([]);
    }
  }, [apiCall, page, perPage]);

  useEffect(() => {
    fetchCoins();
  }, [fetchCoins]);

  const totalPages = useMemo(() => Math.ceil(500 / perPage), [perPage]);

  return (
    <div className="space-y-6">
      {error && <ErrorAlert error={error} onClose={() => {}} />}
      
      {/* Market stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg shadow">
          <div className="flex items-center">
            <div className="p-2 bg-blue-100 rounded-lg">
              <BarChart3 className="text-blue-600" size={24} />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Total Coins</p>
              <p className="text-xl font-semibold">500</p>
            </div>
          </div>
        </div>
      </div>

      {/* Coins table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">All Coins</h3>
          <select
            value={perPage}
            onChange={(e) => {
              setPerPage(Number(e.target.value));
              setPage(1);
            }}
            className="border rounded px-2 py-1 text-sm"
          >
            <option value={20}>20 per page</option>
            <option value={50}>50 per page</option>
            <option value={100}>100 per page</option>
          </select>
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
              {loading ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center">
                    <LoadingSpinner message="Loading coins..." />
                  </td>
                </tr>
              ) : coins.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No coins found
                  </td>
                </tr>
              ) : (
                coins.map((coin, index) => (
                  <CoinTableRow
                    key={coin.id}
                    coin={coin}
                    index={index}
                    page={page}
                    perPage={perPage}
                    onAddToPortfolio={onAddToPortfolio}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-6 py-4 border-t flex items-center justify-between">
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 border rounded-lg disabled:opacity-50"
            >
              Previous
            </button>
            <span className="px-4 py-2">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= totalPages}
              className="px-4 py-2 border rounded-lg disabled:opacity-50"
            >   
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

const PortfolioTab = ({ portfolio, onShowAddForm, onRemoveFromPortfolio }) => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <h2 className="text-2xl font-bold text-gray-900">Portfolio</h2>
      <button
        onClick={onShowAddForm}
        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
      >
        <Plus size={16} />
        Add Coin
      </button>
    </div>

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
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Current Price</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">24h Change</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {portfolio.map((item) => (
                <PortfolioRow
                  key={item.id}
                  item={item}
                  onRemove={onRemoveFromPortfolio}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
);

const WatchlistTab = ({ watchlist, onShowAddForm, onAddToPortfolio, onRemoveFromWatchlist }) => (
  <div className="space-y-6">
    <div className="flex justify-between items-center">
      <h2 className="text-2xl font-bold text-gray-900">Watchlist</h2>
      <button
        onClick={onShowAddForm}
        className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg flex items-center gap-2"
      >
        <Plus size={16} />
        Add to Watchlist
      </button>
    </div>

    {watchlist.length === 0 ? (
      <div className="text-center py-12">
        <Activity size={48} className="mx-auto text-gray-400 mb-4" />
        <p className="text-gray-600">No coins in your watchlist yet. Add some to track their performance!</p>
      </div>
    ) : (
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Coin</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Price</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">24h Change</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Market Cap</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Added</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {watchlist.map((item) => (
                <WatchlistRow
                  key={item.id}
                  item={item}
                  onAddToPortfolio={onAddToPortfolio}
                  onRemove={onRemoveFromWatchlist}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    )}
  </div>
);

const AddFormModal = ({ show, onClose, onSubmit, form, setForm, loading }) => (
  show && (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Add Coin to Portfolio</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        </div>
        <form onSubmit={onSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Coin Name
              </label>
              <input
                type="text"
                value={form.coin_name}
                onChange={(e) => setForm(prev => ({ ...prev, coin_name: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., Bitcoin"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Symbol
              </label>
              <input
                type="text"
                value={form.symbol}
                onChange={(e) => setForm(prev => ({ ...prev, symbol: e.target.value.toUpperCase() }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., BTC"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quantity
              </label>
              <input
                type="number"
                step="any"
                value={form.quantity}
                onChange={(e) => setForm(prev => ({ ...prev, quantity: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Purchase Price (USD) - Optional
              </label>
              <input
                type="number"
                step="any"
                value={form.purchase_price}
                onChange={(e) => setForm(prev => ({ ...prev, purchase_price: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="0.00"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Notes - Optional
              </label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm(prev => ({ ...prev, notes: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Add any notes about this purchase..."
                rows="3"
              />
            </div>

            <div className="flex justify-end gap-2 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Adding...' : 'Add to Portfolio'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
);

const CryptoPortfolioTracker = () => {
  // State management
  const [activeTab, setActiveTab] = useState('portfolio');
  const [portfolio, setPortfolio] = useState([]);
  const [portfolioSummary, setPortfolioSummary] = useState({});
  const [watchlist, setWatchlist] = useState([]);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState({
    coin_id: '',
    coin_name: '',
    symbol: '',
    quantity: '',
    purchase_price: '',
    notes: ''
  });

  const { apiCall, loading, error, setError } = useApi();

  // Data fetching functions
  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await apiCall('/portfolio');
      setPortfolio(data.portfolio || []);
      setPortfolioSummary(data.summary || {});
    } catch (err) {
      console.error('Failed to fetch portfolio');
    }
  }, [apiCall]);

  const fetchWatchlist = useCallback(async () => {
    try {
      const data = await apiCall('/watchlist');
      setWatchlist(data.watchlist || []);
    } catch (err) {
      console.error('Failed to fetch watchlist');
    }
  }, [apiCall]);

  // Load initial data
  useEffect(() => {
    fetchPortfolio();
    fetchWatchlist();
  }, [fetchPortfolio, fetchWatchlist]);

  // Action handlers
  const handleAddToPortfolio = useCallback((coin) => {
    setAddForm(prev => ({
      ...prev,
      coin_id: coin.id || coin.coin_id,
      coin_name: coin.name || coin.coin_name,
      symbol: coin.symbol
    }));
    setShowAddForm(true);
  }, []);

  const handleSubmitAddForm = useCallback(async (e) => {
    e.preventDefault();
    try {
      const response = await apiCall('/portfolio', {
        method: 'POST',
        body: JSON.stringify(addForm)
      });
      
      if (response.success) {
        setPortfolio(prev => [...prev, response.data]);
        setShowAddForm(false);
        setAddForm({
          coin_id: '',
          coin_name: '',
          symbol: '',
          quantity: '',
          purchase_price: '',
          notes: ''
        });
      }
    } catch (err) {
      console.error('Failed to add coin to portfolio');
    }
  }, [apiCall, addForm]);

  const handleRemoveFromPortfolio = useCallback(async (id) => {
    try {
      await apiCall(`/portfolio/${id}`, { method: 'DELETE' });
      setPortfolio(prev => prev.filter(item => item.id !== id));
    } catch (err) {
      console.error('Failed to remove from portfolio');
    }
  }, [apiCall]);

  const handleRemoveFromWatchlist = useCallback(async (id) => {
    try {
      await apiCall(`/watchlist/${id}`, { method: 'DELETE' });
      setWatchlist(prev => prev.filter(item => item.id !== id));
    } catch (err) {
      console.error('Failed to remove from watchlist');
    }
  }, [apiCall]);

  const tabs = useMemo(() => [
    { id: 'portfolio', label: 'Portfolio', icon: DollarSign },
    { id: 'market', label: 'Market', icon: BarChart3 },
    { id: 'watchlist', label: 'Watchlist', icon: Activity }
  ], []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <DollarSign className="h-8 w-8 text-blue-600 mr-3" />
              <h1 className="text-2xl font-bold text-gray-900">Crypto Portfolio Tracker</h1>
            </div>
            <button
              onClick={() => window.location.reload()}
              className="text-gray-500 hover:text-gray-700"
            >
              <RefreshCw size={20} />
            </button>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex items-center px-3 py-4 border-b-2 font-medium text-sm ${
                  activeTab === id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon size={16} className="mr-2" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <ErrorAlert error={error} onClose={() => setError('')} />

        {/* Tab Content */}
        {activeTab === 'portfolio' && (
          <PortfolioTab
            portfolio={portfolio}
            onShowAddForm={() => setShowAddForm(true)}
            onRemoveFromPortfolio={handleRemoveFromPortfolio}
          />
        )}
        {activeTab === 'market' && (
          <MarketTab onAddToPortfolio={handleAddToPortfolio} />
        )}
        {activeTab === 'watchlist' && (
          <WatchlistTab
            watchlist={watchlist}
            onShowAddForm={() => setShowAddForm(true)}
            onAddToPortfolio={handleAddToPortfolio}
            onRemoveFromWatchlist={handleRemoveFromWatchlist}
          />
        )}
      </main>

      {/* Modals */}
      <AddFormModal
        show={showAddForm}
        onClose={() => setShowAddForm(false)}
        onSubmit={handleSubmitAddForm}
        form={addForm}
        setForm={setAddForm}
        loading={loading}
      />
    </div>
  );
};

export default CryptoPortfolioTracker;