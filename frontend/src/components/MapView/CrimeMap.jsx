import { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import axios from 'axios';
import './CrimeMap.css';

const defaultIcon = L.icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function FitBoundsOnLoad({ firs }) {
  const map = useMap();
  useEffect(() => {
    if (!firs || firs.length === 0) return;
    const bounds = firs
      .filter((f) => f.latitude && f.longitude)
      .map((f) => [f.latitude, f.longitude]);
    if (bounds.length > 0) map.fitBounds(bounds, { padding: [30, 30] });
  }, [firs, map]);
  return null;
}

export default function CrimeMap() {
  const [firs, setFirs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    axios.get('/api/firs/', {
      params: { page_size: 1000 },
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => {
        const results = (res.data.results || []).filter((f) => f.latitude && f.longitude);
        setFirs(results);
      })
      .catch((err) => setError(err.message || err.response?.data?.error || 'Failed to load'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="map-status">Loading crime map...</div>;
  if (error) return <div className="map-status" style={{ color: '#e53e3e' }}>Error: {error}</div>;

  return (
    <div className="map-box">
      <h3 className="map-title">🗺️ Crime Hotspots</h3>
      <div className="map-container">
        <MapContainer center={[12.97, 77.59]} zoom={11} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {firs.map((f) => (
            <Marker key={f.id} position={[f.latitude, f.longitude]} icon={defaultIcon}>
              <Popup>
                <div className="fir-popup">
                  <strong>FIR:</strong> {f.fir_id}<br />
                  <strong>Crime:</strong> {f.crime_head}<br />
                  <strong>Status:</strong> {f.case_status}<br />
                  <strong>Station:</strong> {f.police_station}
                </div>
              </Popup>
            </Marker>
          ))}
          <FitBoundsOnLoad firs={firs} />
        </MapContainer>
      </div>
    </div>
  );
}