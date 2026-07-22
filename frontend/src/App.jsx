import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Network from './pages/Network';
import Analytics from './pages/Analytics';
import CrimeMapPage from './pages/CrimeMap';
import FIRDetails from './pages/FIRDetails';

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [user, setUser] = useState(null);

  const handleLoginSuccess = (userData) => {
    setUser(userData);
    setIsLoggedIn(true);
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={handleLoginSuccess} />;
  }

  void user; // reserved for future per-user Sidebar rendering

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard />;
      case 'chat':
        return <Chat />;
      case 'network':
        return <Network />;
      case 'analytics':
        return <Analytics />;
      case 'map':
        return <CrimeMapPage />;
      case 'fir':
        return <FIRDetails />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar currentPage={currentPage} onNavigate={setCurrentPage} />
      <div className="flex-1 overflow-auto">
        {renderPage()}
      </div>
    </div>
  );
}
