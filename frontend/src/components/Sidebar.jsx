
export default function Sidebar({ currentPage = 'dashboard', onNavigate }) {
  const menuItems = [
    { id: 'dashboard', label: '📊 Dashboard', icon: '📊' },
    { id: 'chat', label: '💬 Intelligent Search', icon: '💬' },
    { id: 'network', label: '🔗 Network Analysis', icon: '🔗' },
    { id: 'map', label: '🗺️ Crime Map', icon: '🗺️' },
    { id: 'analytics', label: '📈 Analytics', icon: '📈' },
    { id: 'fir', label: '📋 FIR Details', icon: '📋' },
    { id: 'network_live', label: '🔗 Live Network', icon: '🔗' },
    { id: 'map_live', label: '🗺️ Live Map', icon: '🗺️' },
    { id: 'analytics_live', label: '📈 Live Stats', icon: '📈' },
  ];

  return (
    <div className="w-64 bg-gray-900 text-white h-screen flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-700">
        <h1 className="text-2xl font-bold">🔍 KSP Intelligence</h1>
        <p className="text-xs text-gray-400 mt-1">Crime Platform v1.0</p>
      </div>

      {/* Menu */}
      <nav className="flex-1 p-4">
        {menuItems.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`w-full text-left px-4 py-3 rounded-lg mb-2 transition ${
              currentPage === item.id
                ? 'bg-blue-600 text-white font-semibold'
                : 'text-gray-300 hover:bg-gray-800'
            }`}
          >
            <span className="mr-2">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-700 text-xs text-gray-400">
        <p>Logged in as: Inspector Sharma</p>
        <p>Role: Investigator</p>
        <button className="w-full mt-3 bg-red-600 hover:bg-red-700 text-white py-2 rounded">
          🚪 Logout
        </button>
      </div>
    </div>
  );
}
