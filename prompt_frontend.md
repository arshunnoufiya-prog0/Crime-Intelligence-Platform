# OpenCode Prompt: KSP Crime Intelligence Frontend Build
## Self-Contained Components (No Cross-File Dependencies)

Use this prompt in OpenCode. Work through ONE component at a time. Each component is independent until explicitly stated. Copy the exact file paths below to avoid hallucination.

---

## PROJECT CONTEXT (Read First)
You are building the **frontend for a crime-intelligence platform for KSP police officers**. Users ask natural-language questions about crimes ("Who are this suspect's associates?", "Show me crime patterns in Bengaluru 2022-2024") and get conversational answers with network graphs and analytics.

**Stack:**
- React (Vite) with JSX
- Tailwind CSS for styling
- Mock data initially (no API calls yet)
- Standalone components first, then wire together

**Folder Structure (exact):**
```
frontend/src/
├── components/
│   ├── AnalyticsChart.jsx       (build this)
│   ├── ChatWindow.jsx            (build this)
│   ├── CrimeCard.jsx             (build this)
│   ├── CrimeMap.jsx              (build this)
│   ├── CrimeTrendChart.jsx       (build this)
│   ├── Sidebar.jsx               (build this)
│   └── StatCard.jsx              (build this)
├── pages/
│   ├── Analytics.jsx             (build this)
│   ├── Chat.jsx                  (build this)
│   ├── CrimeMap.jsx              (build this)
│   ├── Dashboard.jsx             (build this)
│   ├── FIRDetails.jsx            (build this)
│   ├── Login.jsx                 (build this)
│   └── Network.jsx               (build this)
├── data/
│   └── mockData.js               (build this)
├── hooks/
│   └── useChat.js                (build this)
├── services/
│   └── (placeholder for API later)
├── styles/
│   └── dashboard.css             (already exists)
├── utils/
│   └── (placeholder)
├── App.jsx                       (update this)
├── main.jsx                      (leave as-is)
└── index.css                     (leave as-is)
```

---

## BUILD SEQUENCE (Follow in Order)

### STEP 1: Create Mock Data File
**File:** `frontend/src/data/mockData.js`

```javascript
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Do NOT import this anywhere yet.
// This file only exports mock data objects.
// Use this EXACT structure. No modifications.

export const mockCases = [
  {
    id: "CASE-2024-001",
    firNumber: "FIR/2024/001",
    date: "2024-01-15",
    location: "Bengaluru Central",
    crimeType: "Murder",
    accused: [
      { id: "ACC-001", name: "Rajesh Kumar", age: 35, status: "Arrested" },
      { id: "ACC-002", name: "Priya Sharma", age: 28, status: "Absconding" }
    ],
    victims: ["John Doe", "Jane Doe"],
    narrative: "Accused persons were involved in a premeditated attack...",
    status: "Under Investigation"
  },
  {
    id: "CASE-2024-002",
    firNumber: "FIR/2024/002",
    date: "2024-01-20",
    location: "Bengaluru South",
    crimeType: "Theft",
    accused: [
      { id: "ACC-003", name: "Amit Patel", age: 32, status: "Arrested" }
    ],
    victims: ["Store Owner"],
    narrative: "Stolen electronics from retail store...",
    status: "Closed"
  }
];

export const mockCrimeTrends = [
  { month: "Jan", murder: 5, theft: 12, assault: 8, fraud: 6 },
  { month: "Feb", murder: 3, theft: 15, assault: 10, fraud: 8 },
  { month: "Mar", murder: 7, theft: 10, assault: 9, fraud: 7 },
  { month: "Apr", murder: 4, theft: 18, assault: 11, fraud: 9 },
  { month: "May", murder: 6, theft: 14, assault: 12, fraud: 10 }
];

export const mockHotspots = [
  { lat: 12.9716, lng: 77.5946, crimeType: "Theft", count: 15, location: "Bengaluru Central" },
  { lat: 12.9352, lng: 77.6245, crimeType: "Assault", count: 8, location: "Bengaluru South" },
  { lat: 12.9698, lng: 77.7499, crimeType: "Fraud", count: 12, location: "Bengaluru East" }
];

export const mockNetworkGraph = {
  nodes: [
    { id: "ACC-001", label: "Rajesh Kumar", type: "accused", color: "#FF6B6B", size: 30, centrality: 0.85 },
    { id: "ACC-002", label: "Priya Sharma", type: "accused", color: "#FF6B6B", size: 25, centrality: 0.72 },
    { id: "LOC-001", label: "Bengaluru Central", type: "location", color: "#4ECDC4", size: 20, centrality: 0.65 },
    { id: "VIC-001", label: "John Doe", type: "victim", color: "#FFD93D", size: 15, centrality: 0.40 }
  ],
  edges: [
    { source: "ACC-001", target: "ACC-002", type: "co-accused" },
    { source: "ACC-001", target: "LOC-001", type: "crime-location" },
    { source: "ACC-002", target: "LOC-001", type: "crime-location" },
    { source: "ACC-001", target: "VIC-001", type: "victim" }
  ]
};

export const mockChatHistory = [
  { id: 1, role: "user", text: "Who are the associates of Rajesh Kumar?", timestamp: "10:15 AM" },
  { 
    id: 2, 
    role: "assistant", 
    text: "Based on crime records, Rajesh Kumar is associated with Priya Sharma. They appear together in FIR/2024/001 dated 2024-01-15 at Bengaluru Central as co-accused in a murder case. Both are currently wanted/arrested.",
    citations: ["FIR/2024/001 (2024-01-15)"],
    confidence: 0.92,
    timestamp: "10:15 AM"
  }
];

export const mockUser = {
  id: "USR-001",
  name: "Inspector Sharma",
  role: "investigator", // "investigator" | "analyst" | "policymaker"
  department: "KSP Cyber Crime",
  badge: "12345"
};
```

**What to test:** Open Chrome DevTools, go to Console, type `import('./data/mockData.js')` — should load with no errors.

---

### STEP 2: Build Stat Card Component
**File:** `frontend/src/components/StatCard.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// This component takes props only (no hooks, no state, no imports beyond React).
// It displays a single metric (e.g., "Cases: 42").

import React from 'react';

export default function StatCard({ title, value, icon, bgColor }) {
  return (
    <div className={`${bgColor} rounded-lg p-6 shadow-md text-white`}>
      <div className="flex justify-between items-center">
        <div>
          <p className="text-sm font-medium opacity-90">{title}</p>
          <h3 className="text-3xl font-bold mt-2">{value}</h3>
        </div>
        <div className="text-4xl opacity-50">{icon}</div>
      </div>
    </div>
  );
}
```

**Props to pass (example):**
- `title="Active Cases"`, `value="42"`, `icon="📋"`, `bgColor="bg-blue-600"`
- `title="Suspects"`, `value="156"`, `icon="👤"`, `bgColor="bg-red-600"`

**What to test:** This component should render a colored box with a number. No errors in console.

---

### STEP 3: Build Crime Card Component
**File:** `frontend/src/components/CrimeCard.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Props only. Display a single FIR/case as a card.
// Do NOT call any APIs or use fetch.

import React from 'react';

export default function CrimeCard({ caseId, firNumber, crimeType, location, date, accused, status }) {
  const statusColor = {
    "Under Investigation": "bg-yellow-100 text-yellow-800",
    "Closed": "bg-green-100 text-green-800",
    "Arrested": "bg-red-100 text-red-800"
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h4 className="font-bold text-gray-900">{firNumber}</h4>
          <p className="text-sm text-gray-500">{date}</p>
        </div>
        <span className={`text-xs font-semibold px-2 py-1 rounded ${statusColor[status] || 'bg-gray-100'}`}>
          {status}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-700 mb-2">{crimeType}</p>
      <p className="text-xs text-gray-600 mb-3">📍 {location}</p>
      <div className="border-t pt-3">
        <p className="text-xs font-semibold text-gray-700 mb-2">Accused ({accused?.length || 0})</p>
        <div className="flex flex-wrap gap-1">
          {accused?.map(acc => (
            <span key={acc.id} className="bg-red-50 text-red-700 text-xs px-2 py-1 rounded">
              {acc.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Props to pass (example from mockData):**
```jsx
<CrimeCard 
  caseId="CASE-2024-001"
  firNumber="FIR/2024/001"
  crimeType="Murder"
  location="Bengaluru Central"
  date="2024-01-15"
  accused={[{ id: "ACC-001", name: "Rajesh Kumar" }]}
  status="Under Investigation"
/>
```

**What to test:** Card should display all fields. Hover should add shadow. No console errors.

---

### STEP 4: Build Chat Window Component (Message Display Only)
**File:** `frontend/src/components/ChatWindow.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// This is ONLY for DISPLAYING messages, no input field yet.
// Props: chatHistory (array of message objects).
// Do NOT fetch or call APIs.

import React from 'react';

function MessageBubble({ message }) {
  const isUser = message.role === "user";
  
  return (
    <div className={`flex mb-4 ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
        isUser 
          ? 'bg-blue-600 text-white rounded-br-none' 
          : 'bg-gray-200 text-gray-900 rounded-bl-none'
      }`}>
        <p className="text-sm">{message.text}</p>
        
        {!isUser && message.citations && (
          <div className="mt-2 pt-2 border-t border-gray-400 text-xs opacity-80">
            <p className="font-semibold">Sources:</p>
            {message.citations.map((cite, idx) => (
              <p key={idx}>📄 {cite}</p>
            ))}
          </div>
        )}
        
        {!isUser && message.confidence && (
          <p className="mt-1 text-xs opacity-70">Confidence: {(message.confidence * 100).toFixed(0)}%</p>
        )}
        
        <p className="text-xs opacity-70 mt-2">{message.timestamp}</p>
      </div>
    </div>
  );
}

export default function ChatWindow({ chatHistory = [] }) {
  return (
    <div className="flex flex-col h-96 bg-white rounded-lg border border-gray-200 p-4 overflow-y-auto">
      {chatHistory.length === 0 ? (
        <div className="flex items-center justify-center h-full text-gray-500">
          <p>No messages yet. Start typing a question.</p>
        </div>
      ) : (
        chatHistory.map(msg => <MessageBubble key={msg.id} message={msg} />)
      )}
    </div>
  );
}
```

**Props to pass (example):**
```jsx
<ChatWindow chatHistory={mockChatHistory} />
```

**What to test:** Chat bubbles should display. User messages right-aligned, assistant messages left. Citations show below assistant messages. No console errors.

---

### STEP 5: Build Sidebar Component
**File:** `frontend/src/components/Sidebar.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Navigation menu. Props: currentPage (string), onNavigate (function).
// Do NOT use React Router yet.

import React from 'react';

export default function Sidebar({ currentPage = 'dashboard', onNavigate }) {
  const menuItems = [
    { id: 'dashboard', label: '📊 Dashboard', icon: '📊' },
    { id: 'chat', label: '💬 Intelligent Search', icon: '💬' },
    { id: 'network', label: '🔗 Network Analysis', icon: '🔗' },
    { id: 'map', label: '🗺️ Crime Map', icon: '🗺️' },
    { id: 'analytics', label: '📈 Analytics', icon: '📈' },
    { id: 'fir', label: '📋 FIR Details', icon: '📋' }
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
```

**Props to pass (example):**
```jsx
<Sidebar currentPage="dashboard" onNavigate={(page) => console.log(page)} />
```

**What to test:** Menu items should be clickable. Current page should highlight in blue. No errors.

---

### STEP 6: Build Crime Trend Chart (No Plotly Yet)
**File:** `frontend/src/components/CrimeTrendChart.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Simple table view of crime trends (Plotly comes later).
// Props: trendData (array of month/crime counts).

import React from 'react';

export default function CrimeTrendChart({ trendData = [] }) {
  if (trendData.length === 0) {
    return <div className="text-gray-500 p-4">No data available</div>;
  }

  // Get all crime types from data
  const crimeTypes = Object.keys(trendData[0]).filter(k => k !== 'month');

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">📈 Crime Trends (Last 5 Months)</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-gray-300">
              <th className="text-left py-2 px-2 font-semibold">Month</th>
              {crimeTypes.map(type => (
                <th key={type} className="text-center py-2 px-2 font-semibold capitalize">{type}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trendData.map((row, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                <td className="py-2 px-2 font-medium">{row.month}</td>
                {crimeTypes.map(type => (
                  <td key={type} className="text-center py-2 px-2">
                    <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-xs font-semibold">
                      {row[type]}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

**Props to pass (example):**
```jsx
<CrimeTrendChart trendData={mockCrimeTrends} />
```

**What to test:** Table should display. Rows should alternate colors. No console errors.

---

### STEP 7: Build Crime Map Placeholder
**File:** `frontend/src/components/CrimeMap.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Placeholder for map. Real Leaflet integration comes later.
// Props: hotspots (array with lat, lng, count).

import React from 'react';

export default function CrimeMap({ hotspots = [] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">🗺️ Crime Hotspots</h3>
      <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
        <div className="text-center text-gray-500">
          <p className="text-lg mb-2">🗺️ Map Loading...</p>
          <p className="text-sm">Leaflet integration coming soon</p>
          <p className="text-xs mt-2 text-gray-400">Total hotspots: {hotspots.length}</p>
        </div>
      </div>
      
      {/* Hotspots List */}
      <div className="mt-4">
        <p className="font-semibold text-sm mb-2">Detected Hotspots:</p>
        <div className="space-y-2">
          {hotspots.map((spot, idx) => (
            <div key={idx} className="bg-gray-50 p-2 rounded text-sm">
              <p className="font-medium">{spot.location}</p>
              <p className="text-xs text-gray-600">Crime Type: {spot.crimeType} | Count: {spot.count}</p>
              <p className="text-xs text-gray-500">Coordinates: {spot.lat}, {spot.lng}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Props to pass (example):**
```jsx
<CrimeMap hotspots={mockHotspots} />
```

**What to test:** Placeholder displays. Hotspots list shows all items. No console errors.

---

### STEP 8: Build Analytics Chart Placeholder
**File:** `frontend/src/components/AnalyticsChart.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Placeholder for charts. Real Plotly integration comes later.

import React from 'react';

export default function AnalyticsChart() {
  const stats = [
    { label: "Total Cases", value: "1,245", color: "blue" },
    { label: "Active Investigations", value: "342", color: "orange" },
    { label: "Solved Cases", value: "903", color: "green" },
    { label: "Suspects Arrested", value: "567", color: "red" }
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">📊 Crime Statistics</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className={`bg-${stat.color}-50 p-4 rounded-lg border border-${stat.color}-200`}>
            <p className="text-xs font-medium text-gray-600">{stat.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
```

**What to test:** Stats grid should display in 4 columns on desktop. No console errors.

---

### STEP 9: Build Login Page
**File:** `frontend/src/pages/Login.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Simple login form. No API calls yet.
// Props: onLoginSuccess (callback function).

import React, { useState } from 'react';

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [selectedRole, setSelectedRole] = useState('investigator');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (username && password) {
      // Mock success - in real app, call API here
      onLoginSuccess({
        name: username,
        role: selectedRole,
        badge: '12345'
      });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-600 flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-2xl p-8 w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900">🔍 KSP Intelligence</h1>
          <p className="text-sm text-gray-600 mt-2">Crime Investigation Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Badge/Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your badge number"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Role</label>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="investigator">🔎 Investigator</option>
              <option value="analyst">📊 Analyst</option>
              <option value="policymaker">🏛️ Policymaker</option>
            </select>
          </div>

          <button
            type="submit"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-lg transition"
          >
            🔓 Login
          </button>
        </form>

        <p className="text-center text-xs text-gray-600 mt-6">
          Demo credentials: Any username + password
        </p>
      </div>
    </div>
  );
}
```

**What to test:** Form should accept input. Role dropdown should work. Submit should trigger onLoginSuccess callback with user object.

---

### STEP 10: Build Dashboard Page (Combining Components)
**File:** `frontend/src/pages/Dashboard.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Combines StatCard, AnalyticsChart, CrimeTrendChart, CrimeMap.
// Props: none. Import mockData directly.

import React from 'react';
import StatCard from '../components/StatCard';
import AnalyticsChart from '../components/AnalyticsChart';
import CrimeTrendChart from '../components/CrimeTrendChart';
import CrimeMap from '../components/CrimeMap';
import { mockCrimeTrends, mockHotspots } from '../data/mockData';

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Active Cases" value="342" icon="📋" bgColor="bg-blue-600" />
        <StatCard title="Suspects" value="1,245" icon="👤" bgColor="bg-red-600" />
        <StatCard title="Arrests" value="567" icon="🚨" bgColor="bg-orange-600" />
        <StatCard title="Solved Cases" value="903" icon="✅" bgColor="bg-green-600" />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Analytics */}
        <div className="lg:col-span-2 space-y-6">
          <AnalyticsChart />
          <CrimeTrendChart trendData={mockCrimeTrends} />
        </div>

        {/* Right: Map */}
        <div>
          <CrimeMap hotspots={mockHotspots} />
        </div>
      </div>
    </div>
  );
}
```

**What to test:** Dashboard should display 4 stat cards at top. Three-column grid below. All components visible.

---

### STEP 11: Build Chat Page
**File:** `frontend/src/pages/Chat.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Chat interface with input field and message display.

import React, { useState } from 'react';
import ChatWindow from '../components/ChatWindow';
import { mockChatHistory } from '../data/mockData';

export default function Chat() {
  const [messages, setMessages] = useState(mockChatHistory);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = () => {
    if (!inputValue.trim()) return;

    // Add user message
    const userMsg = {
      id: messages.length + 1,
      role: "user",
      text: inputValue,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages([...messages, userMsg]);
    setInputValue('');
    setIsLoading(true);

    // Simulate AI response delay
    setTimeout(() => {
      const aiMsg = {
        id: messages.length + 2,
        role: "assistant",
        text: "This is a mock response. Real API integration coming soon.",
        citations: ["FIR/2024/001 (2024-01-15)"],
        confidence: 0.85,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, aiMsg]);
      setIsLoading(false);
    }, 1500);
  };

  return (
    <div className="p-6 h-screen flex flex-col">
      <h2 className="text-2xl font-bold mb-4">💬 Intelligent Crime Search</h2>
      
      <ChatWindow chatHistory={messages} />

      {isLoading && (
        <div className="mt-2 text-sm text-gray-500 flex items-center">
          <span className="inline-block w-2 h-2 bg-gray-500 rounded-full mr-2 animate-pulse"></span>
          AI is thinking...
        </div>
      )}

      {/* Input Area */}
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask about crimes, suspects, or patterns..."
          className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-600"
        />
        <button
          onClick={handleSend}
          disabled={isLoading || !inputValue.trim()}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-6 py-3 rounded-lg font-medium transition"
        >
          📤 Send
        </button>
      </div>
    </div>
  );
}
```

**What to test:** Type message, hit Send or Enter. Message appears as user bubble. AI response appears after 1.5s. Input clears. Loading indicator shows while waiting.

---

### STEP 12: Build Network Page Placeholder
**File:** `frontend/src/pages/Network.jsx`

```jsx
// INSTRUCTIONS FOR OPENCODE:
// Create a new file at the exact path above.
// Placeholder for network graph visualization.
// Real react-force-graph integration comes later.

import React from 'react';
import { mockNetworkGraph } from '../data/mockData';

export default function Network() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">🔗 Criminal Network Analysis</h2>
      
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Graph Placeholder */}
        <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 p-4">
          <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
            <div className="text-center text-gray-500">
              <p className="text-lg mb-2">🔗 Network Graph</p>
              <p className="text-sm">react-force-graph integration coming soon</p>
            </div>
          </div>
        </div>

        {/* Nodes List */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-bold mb-4">Nodes ({mockNetworkGraph.nodes.length})</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {mockNetworkGraph.nodes.map(node => (
              <div key={node.id} className="bg-gray-50 p-2 rounded text-sm">
                <p className="font-semibold">{node.label}</p>
                <p className="text-xs text-gray-600">Type: {node.type}</p>
                <p className="text-xs text-gray-600">Centrality: {(node.centrality * 100).toFixed(0)}%</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

**What to test:** Placeholder displays. Nodes list shows all items scrollable. No errors.

---

### STEP 13: Build Remaining Placeholder Pages
**File:** `frontend/src/pages/Analytics.jsx`

```jsx
import React from 'react';
import CrimeTrendChart from '../components/CrimeTrendChart';
import AnalyticsChart from '../components/AnalyticsChart';
import { mockCrimeTrends } from '../data/mockData';

export default function Analytics() {
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">📈 Analytics & Reports</h2>
      <AnalyticsChart />
      <CrimeTrendChart trendData={mockCrimeTrends} />
    </div>
  );
}
```

**File:** `frontend/src/pages/CrimeMap.jsx`

```jsx
import React from 'react';
import CrimeMap from '../components/CrimeMap';
import { mockHotspots } from '../data/mockData';

export default function CrimeMapPage() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">🗺️ Crime Hotspot Map</h2>
      <CrimeMap hotspots={mockHotspots} />
    </div>
  );
}
```

**File:** `frontend/src/pages/FIRDetails.jsx`

```jsx
import React from 'react';
import CrimeCard from '../components/CrimeCard';
import { mockCases } from '../data/mockData';

export default function FIRDetails() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">📋 FIR Details</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {mockCases.map(caseData => (
          <CrimeCard
            key={caseData.id}
            caseId={caseData.id}
            firNumber={caseData.firNumber}
            crimeType={caseData.crimeType}
            location={caseData.location}
            date={caseData.date}
            accused={caseData.accused}
            status={caseData.status}
          />
        ))}
      </div>
    </div>
  );
}
```

**What to test:** Each page loads. Content displays correctly. No console errors.

---

### STEP 14: Update App.jsx to Wire Everything Together
**File:** `frontend/src/App.jsx` (REPLACE entire content)

```jsx
// INSTRUCTIONS FOR OPENCODE:
// REPLACE the entire App.jsx file with this content.
// This is the main router/layout that stitches all pages together.

import React, { useState } from 'react';
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
```

**What to test:** 
1. Start with login screen
2. Click login (any username/password)
3. Should see Dashboard with sidebar
4. Click each sidebar menu item
5. Pages should switch correctly
6. All components should render without errors

---

## TESTING CHECKLIST (Do This After Each Step)

- [ ] Console has **zero** errors
- [ ] Component renders without crashing
- [ ] Props pass correctly (if applicable)
- [ ] Styling looks correct (Tailwind classes applied)
- [ ] No missing imports
- [ ] No typos in file paths

---

## COMMON ISSUES & FIXES

| Issue | Fix |
|-------|-----|
| "Cannot find module" error | Check file path is EXACT. Use `frontend/src/components/FileName.jsx` format. |
| Tailwind classes not working | Make sure `index.css` imports Tailwind. Restart dev server: `npm run dev` |
| Component not rendering | Check `export default` statement exists. Check parentheses/braces syntax. |
| Props not showing | Open Chrome DevTools → React tab → inspect component → check props object. |
| Sidebar not switching pages | Check `onNavigate` callback is wired to `setCurrentPage` in App.jsx. |

---

## NEXT STEPS (After All Steps Complete)

Once you've built all 14 steps:

1. **Run `npm run dev`** and test the full flow
2. **Test on mobile** (open DevTools, toggle device toolbar)
3. **Fix any styling issues** on different screen sizes
4. **Commit to git** (`git add .` → `git commit -m "Frontend: All components built"`)

Then I can show you how to:
- Integrate real Leaflet maps
- Integrate Plotly charts
- Hook up the real FastAPI backend
- Add chat streaming (Server-Sent Events)
- Build graph visualization with react-force-graph

---

**Document Version:** 1.0 | **For:** Crime Intelligence Platform Frontend | **Date:** July 2024
