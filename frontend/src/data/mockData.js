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
  role: "investigator", 
  department: "KSP Cyber Crime",
  badge: "12345"
};
