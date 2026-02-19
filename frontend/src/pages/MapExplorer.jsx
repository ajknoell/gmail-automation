import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getMapApiKey,
  geocodeAddress,
  searchNearbyPlaces,
  addPlaceToOutreach,
  getCampaigns,
} from '../api/client';

const BUSINESS_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'restaurant', label: 'Restaurant' },
  { value: 'cafe', label: 'Cafe' },
  { value: 'bar', label: 'Bar' },
  { value: 'store', label: 'Retail Store' },
  { value: 'plumber', label: 'Plumber' },
  { value: 'electrician', label: 'Electrician' },
  { value: 'dentist', label: 'Dentist' },
  { value: 'doctor', label: 'Doctor' },
  { value: 'lawyer', label: 'Lawyer' },
  { value: 'accounting', label: 'Accounting' },
  { value: 'real_estate_agency', label: 'Real Estate' },
  { value: 'insurance_agency', label: 'Insurance' },
  { value: 'car_repair', label: 'Auto Repair' },
  { value: 'beauty_salon', label: 'Beauty Salon' },
  { value: 'hair_care', label: 'Hair Care' },
  { value: 'gym', label: 'Gym / Fitness' },
  { value: 'veterinary_care', label: 'Veterinarian' },
  { value: 'bakery', label: 'Bakery' },
  { value: 'florist', label: 'Florist' },
  { value: 'laundry', label: 'Laundry' },
  { value: 'locksmith', label: 'Locksmith' },
  { value: 'moving_company', label: 'Moving Company' },
  { value: 'painter', label: 'Painter' },
  { value: 'pet_store', label: 'Pet Store' },
  { value: 'pharmacy', label: 'Pharmacy' },
  { value: 'roofing_contractor', label: 'Roofing' },
  { value: 'travel_agency', label: 'Travel Agency' },
];

const RATING_OPTIONS = [
  { value: 0, label: 'Any Rating' },
  { value: 3, label: '3+ Stars' },
  { value: 3.5, label: '3.5+ Stars' },
  { value: 4, label: '4+ Stars' },
  { value: 4.5, label: '4.5+ Stars' },
];

// Load the Google Maps JS API via a script tag
let mapsLoadPromise = null;
function loadGoogleMapsApi(apiKey) {
  if (window.google?.maps?.Map) return Promise.resolve();
  if (mapsLoadPromise) return mapsLoadPromise;

  mapsLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=marker&v=weekly`;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => {
      mapsLoadPromise = null;
      reject(new Error('Failed to load Google Maps'));
    };
    document.head.appendChild(script);
  });
  return mapsLoadPromise;
}

function MapExplorer() {
  // API key & map loading
  const [apiKey, setApiKey] = useState(null);
  const [mapsReady, setMapsReady] = useState(false);
  const [loadError, setLoadError] = useState('');

  // Search state
  const [searchInput, setSearchInput] = useState('');
  const [center, setCenter] = useState(null);
  const [formattedAddress, setFormattedAddress] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');

  // Filters
  const [businessType, setBusinessType] = useState('');
  const [radius, setRadius] = useState(5000);
  const [minRating, setMinRating] = useState(0);

  // Selected place & info window
  const [selectedPlace, setSelectedPlace] = useState(null);

  // Add to outreach modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [addAction, setAddAction] = useState('contact');
  const [addEmail, setAddEmail] = useState('');
  const [addCampaignId, setAddCampaignId] = useState('');
  const [addNotes, setAddNotes] = useState('');
  const [adding, setAdding] = useState(false);
  const [addResult, setAddResult] = useState(null);
  const [campaigns, setCampaigns] = useState([]);

  // Map refs
  const mapRef = useRef(null);
  const mapContainerRef = useRef(null);
  const markersRef = useRef([]);
  const infoWindowRef = useRef(null);

  // Load API key on mount
  useEffect(() => {
    getMapApiKey()
      .then((res) => {
        setApiKey(res.data.key);
        return loadGoogleMapsApi(res.data.key);
      })
      .then(() => setMapsReady(true))
      .catch((err) => {
        const msg = err.response?.data?.error || err.message || 'Failed to load Google Maps API';
        setLoadError(msg);
      });

    getCampaigns()
      .then((res) => setCampaigns(res.data.campaigns || res.data || []))
      .catch(() => {});

    const handleWsChange = () => {
      getCampaigns()
        .then((res) => setCampaigns(res.data.campaigns || res.data || []))
        .catch(() => {});
      setResults([]);
      setSelectedPlace(null);
      setCenter(null);
      setFormattedAddress('');
    };
    window.addEventListener('workspace-changed', handleWsChange);
    return () => window.removeEventListener('workspace-changed', handleWsChange);
  }, []);

  // Initialize map when Maps JS API is loaded
  useEffect(() => {
    if (!mapsReady || !mapContainerRef.current || mapRef.current) return;

    mapRef.current = new window.google.maps.Map(mapContainerRef.current, {
      center: { lat: 39.8283, lng: -98.5795 }, // Center of US
      zoom: 4,
      mapId: 'DEMO_MAP_ID',
      gestureHandling: 'greedy',
      streetViewControl: false,
      mapTypeControl: false,
    });

    infoWindowRef.current = new window.google.maps.InfoWindow();
  }, [mapsReady]);

  // Update map center when center changes
  useEffect(() => {
    if (!mapRef.current || !center) return;
    mapRef.current.setCenter(center);
    mapRef.current.setZoom(13);
  }, [center]);

  // Clear markers helper
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => {
      m.map = null;
    });
    markersRef.current = [];
    if (infoWindowRef.current) infoWindowRef.current.close();
  }, []);

  // Render markers when results change
  useEffect(() => {
    if (!mapRef.current || !mapsReady) return;
    clearMarkers();

    results.forEach((place) => {
      if (!place.lat || !place.lng) return;

      const marker = new window.google.maps.marker.AdvancedMarkerElement({
        map: mapRef.current,
        position: { lat: place.lat, lng: place.lng },
        title: place.name,
      });

      marker.addListener('click', () => {
        setSelectedPlace(place);
        if (infoWindowRef.current) {
          infoWindowRef.current.setContent(buildInfoContent(place));
          infoWindowRef.current.open({ anchor: marker, map: mapRef.current });
        }
      });

      markersRef.current.push(marker);
    });
  }, [results, mapsReady, clearMarkers]);

  const buildInfoContent = (place) => {
    const stars = place.rating ? `${place.rating} / 5` : 'N/A';
    return `
      <div style="max-width:280px;font-family:system-ui,sans-serif;">
        <h3 style="margin:0 0 4px;font-size:14px;">${escapeHtml(place.name)}</h3>
        <p style="margin:0 0 4px;font-size:12px;color:#6B7280;">${escapeHtml(place.address)}</p>
        <p style="margin:0 0 4px;font-size:12px;">Rating: ${stars}${place.user_ratings_total ? ` (${place.user_ratings_total} reviews)` : ''}</p>
        ${place.phone ? `<p style="margin:0 0 4px;font-size:12px;">Phone: ${escapeHtml(place.phone)}</p>` : ''}
        ${place.website ? `<p style="margin:0 0 4px;font-size:12px;"><a href="${escapeHtml(place.website)}" target="_blank" rel="noopener">Website</a></p>` : ''}
      </div>
    `;
  };

  const escapeHtml = (str) => {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  // Search handler
  const handleSearch = async () => {
    if (!searchInput.trim()) return;
    setError('');
    setSearching(true);
    setSelectedPlace(null);

    try {
      const geoRes = await geocodeAddress(searchInput.trim());
      const { lat, lng, formatted_address } = geoRes.data;
      setCenter({ lat, lng });
      setFormattedAddress(formatted_address);

      const searchRes = await searchNearbyPlaces({
        lat,
        lng,
        radius,
        type: businessType,
        min_rating: minRating,
        max_results: 20,
      });
      setResults(searchRes.data.results || []);
      if ((searchRes.data.results || []).length === 0) {
        setError('No businesses found in this area. Try expanding your radius or changing the business type.');
      }
    } catch (err) {
      const msg = err.response?.data?.error || 'Search failed. Please try again.';
      setError(msg);
      setResults([]);
    }
    setSearching(false);
  };

  // Re-search when filters change (if we already have a center)
  const handleFilterSearch = useCallback(async (newType, newRadius, newRating) => {
    if (!center) return;
    setError('');
    setSearching(true);
    setSelectedPlace(null);

    try {
      const searchRes = await searchNearbyPlaces({
        lat: center.lat,
        lng: center.lng,
        radius: newRadius,
        type: newType,
        min_rating: newRating,
        max_results: 20,
      });
      setResults(searchRes.data.results || []);
      if ((searchRes.data.results || []).length === 0) {
        setError('No businesses found with these filters. Try adjusting your criteria.');
      }
    } catch {
      setError('Search failed.');
    }
    setSearching(false);
  }, [center]);

  // Add to outreach modal handlers
  const openAddModal = (place) => {
    setSelectedPlace(place);
    setShowAddModal(true);
    setAddEmail('');
    setAddAction('contact');
    setAddCampaignId('');
    setAddNotes(`Found via Map Explorer${place.rating ? ` - Rating: ${place.rating}/5` : ''}`);
    setAddResult(null);
  };

  const handleAddToOutreach = async () => {
    if (!addEmail.trim()) {
      setAddResult({ type: 'error', message: 'Email is required.' });
      return;
    }
    setAdding(true);
    setAddResult(null);

    try {
      const res = await addPlaceToOutreach({
        place_id: selectedPlace.place_id,
        name: selectedPlace.name,
        address: selectedPlace.address,
        phone: selectedPlace.phone,
        website: selectedPlace.website,
        rating: selectedPlace.rating,
        types: selectedPlace.types,
        email: addEmail.trim(),
        action: addAction,
        campaign_id: addAction !== 'contact' ? addCampaignId : null,
        notes: addNotes,
      });

      const messages = [];
      if (res.data.contact_existed) messages.push('Contact already exists.');
      else if (res.data.contact) messages.push('Contact created.');
      if (res.data.recipient_existed) messages.push('Recipient already in campaign.');
      else if (res.data.recipient) messages.push('Added to campaign.');

      setAddResult({ type: 'success', message: messages.join(' ') || 'Added successfully.' });
    } catch (err) {
      setAddResult({
        type: 'error',
        message: err.response?.data?.error || 'Failed to add. Please try again.',
      });
    }
    setAdding(false);
  };

  const formatType = (type) => {
    if (!type) return '';
    return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const renderStars = (rating) => {
    if (!rating) return 'N/A';
    const full = Math.floor(rating);
    const half = rating - full >= 0.5;
    let s = '';
    for (let i = 0; i < full; i++) s += '\u2605';
    if (half) s += '\u00BD';
    return `${s} ${rating}`;
  };

  // --- RENDER ---

  if (loadError) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Map Explorer</h1>
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          background: '#FEF2F2',
          borderRadius: '0.75rem',
          border: '1px solid #FECACA',
          color: '#991B1B',
        }}>
          <p style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Unable to load Google Maps</p>
          <p style={{ fontSize: '0.875rem' }}>{loadError}</p>
        </div>
      </div>
    );
  }

  if (!mapsReady) {
    return (
      <div style={{ padding: '2rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem' }}>Map Explorer</h1>
        <div style={{ textAlign: 'center', padding: '3rem', color: '#6B7280' }}>
          Loading Google Maps...
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '1.5rem' }}>
      {/* Header */}
      <div style={{ marginBottom: '1rem' }}>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Map Explorer</h1>
        <p style={{ color: '#6B7280', fontSize: '0.875rem', margin: '0.25rem 0 0' }}>
          Search for local businesses and add them to your outreach lists
        </p>
      </div>

      {/* Search bar */}
      <div style={{
        display: 'flex',
        gap: '0.5rem',
        marginBottom: '0.75rem',
        flexWrap: 'wrap',
      }}>
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder="Enter a city or address (e.g., Austin, TX)"
          style={{
            flex: 1,
            minWidth: '250px',
            padding: '0.5rem 0.75rem',
            border: '1px solid #D1D5DB',
            borderRadius: '0.5rem',
            fontSize: '0.875rem',
          }}
        />
        <button
          onClick={handleSearch}
          disabled={searching || !searchInput.trim()}
          style={{
            padding: '0.5rem 1.25rem',
            background: searching ? '#9CA3AF' : '#3B82F6',
            color: '#fff',
            border: 'none',
            borderRadius: '0.5rem',
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: searching ? 'not-allowed' : 'pointer',
          }}
        >
          {searching ? 'Searching...' : 'Search'}
        </button>
      </div>

      {/* Filters */}
      <div style={{
        display: 'flex',
        gap: '0.75rem',
        marginBottom: '1rem',
        flexWrap: 'wrap',
        alignItems: 'center',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <label style={{ fontSize: '0.8rem', color: '#374151', fontWeight: 500 }}>Type:</label>
          <select
            value={businessType}
            onChange={(e) => {
              setBusinessType(e.target.value);
              handleFilterSearch(e.target.value, radius, minRating);
            }}
            style={{
              padding: '0.35rem 0.5rem',
              border: '1px solid #D1D5DB',
              borderRadius: '0.375rem',
              fontSize: '0.8rem',
              background: '#fff',
            }}
          >
            {BUSINESS_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <label style={{ fontSize: '0.8rem', color: '#374151', fontWeight: 500 }}>
            Radius: {radius >= 1000 ? `${(radius / 1000).toFixed(0)}km` : `${radius}m`}
          </label>
          <input
            type="range"
            min={1000}
            max={50000}
            step={1000}
            value={radius}
            onChange={(e) => {
              const v = parseInt(e.target.value);
              setRadius(v);
            }}
            onMouseUp={() => handleFilterSearch(businessType, radius, minRating)}
            onTouchEnd={() => handleFilterSearch(businessType, radius, minRating)}
            style={{ width: '120px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <label style={{ fontSize: '0.8rem', color: '#374151', fontWeight: 500 }}>Rating:</label>
          <select
            value={minRating}
            onChange={(e) => {
              const v = parseFloat(e.target.value);
              setMinRating(v);
              handleFilterSearch(businessType, radius, v);
            }}
            style={{
              padding: '0.35rem 0.5rem',
              border: '1px solid #D1D5DB',
              borderRadius: '0.375rem',
              fontSize: '0.8rem',
              background: '#fff',
            }}
          >
            {RATING_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </div>

        {formattedAddress && (
          <span style={{ fontSize: '0.8rem', color: '#6B7280', marginLeft: 'auto' }}>
            Showing results near: <strong>{formattedAddress}</strong>
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: '0.75rem 1rem',
          marginBottom: '0.75rem',
          background: '#FEF3C7',
          border: '1px solid #FCD34D',
          borderRadius: '0.5rem',
          fontSize: '0.85rem',
          color: '#92400E',
        }}>
          {error}
        </div>
      )}

      {/* Main layout: sidebar + map */}
      <div style={{ display: 'flex', gap: '1rem', height: 'calc(100vh - 310px)', minHeight: '400px' }}>
        {/* Results sidebar */}
        <div style={{
          width: '340px',
          minWidth: '300px',
          overflowY: 'auto',
          border: '1px solid #E5E7EB',
          borderRadius: '0.75rem',
          background: '#fff',
        }}>
          {results.length === 0 ? (
            <div style={{
              padding: '2rem',
              textAlign: 'center',
              color: '#9CA3AF',
              fontSize: '0.875rem',
            }}>
              {center ? 'No results found' : 'Search for a location to see businesses'}
            </div>
          ) : (
            <div>
              <div style={{
                padding: '0.5rem 0.75rem',
                borderBottom: '1px solid #E5E7EB',
                fontSize: '0.8rem',
                color: '#6B7280',
                fontWeight: 500,
              }}>
                {results.length} business{results.length !== 1 ? 'es' : ''} found
              </div>
              {results.map((place) => (
                <div
                  key={place.place_id}
                  onClick={() => {
                    setSelectedPlace(place);
                    if (mapRef.current) {
                      mapRef.current.panTo({ lat: place.lat, lng: place.lng });
                    }
                    // Open info window on the matching marker
                    const idx = results.indexOf(place);
                    if (markersRef.current[idx] && infoWindowRef.current) {
                      infoWindowRef.current.setContent(buildInfoContent(place));
                      infoWindowRef.current.open({ anchor: markersRef.current[idx], map: mapRef.current });
                    }
                  }}
                  style={{
                    padding: '0.75rem',
                    borderBottom: '1px solid #F3F4F6',
                    cursor: 'pointer',
                    background: selectedPlace?.place_id === place.place_id ? '#EFF6FF' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => {
                    if (selectedPlace?.place_id !== place.place_id) {
                      e.currentTarget.style.background = '#F9FAFB';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background =
                      selectedPlace?.place_id === place.place_id ? '#EFF6FF' : 'transparent';
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.2rem' }}>
                        {place.name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#6B7280', marginBottom: '0.2rem' }}>
                        {place.address}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#9CA3AF', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {place.rating > 0 && (
                          <span style={{ color: '#F59E0B' }}>{renderStars(place.rating)}</span>
                        )}
                        {place.primary_type && (
                          <span>{formatType(place.primary_type)}</span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        openAddModal(place);
                      }}
                      title="Add to outreach"
                      style={{
                        padding: '0.25rem 0.5rem',
                        background: '#10B981',
                        color: '#fff',
                        border: 'none',
                        borderRadius: '0.375rem',
                        fontSize: '0.7rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        flexShrink: 0,
                      }}
                    >
                      + Add
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Map container */}
        <div
          ref={mapContainerRef}
          style={{
            flex: 1,
            borderRadius: '0.75rem',
            border: '1px solid #E5E7EB',
            minHeight: '400px',
          }}
        />
      </div>

      {/* Add to Outreach Modal */}
      {showAddModal && selectedPlace && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
          }}
          onClick={() => setShowAddModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: '#fff',
              borderRadius: '0.75rem',
              padding: '1.5rem',
              width: '480px',
              maxWidth: '95vw',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
            }}
          >
            <h2 style={{ margin: '0 0 1rem', fontSize: '1.1rem', fontWeight: 700 }}>
              Add to Outreach
            </h2>

            {/* Business info display */}
            <div style={{
              padding: '0.75rem',
              background: '#F9FAFB',
              borderRadius: '0.5rem',
              marginBottom: '1rem',
              fontSize: '0.85rem',
            }}>
              <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{selectedPlace.name}</div>
              <div style={{ color: '#6B7280', fontSize: '0.8rem' }}>{selectedPlace.address}</div>
              {selectedPlace.phone && (
                <div style={{ color: '#6B7280', fontSize: '0.8rem' }}>Phone: {selectedPlace.phone}</div>
              )}
              {selectedPlace.website && (
                <div style={{ color: '#6B7280', fontSize: '0.8rem' }}>
                  Website: <a href={selectedPlace.website} target="_blank" rel="noopener noreferrer" style={{ color: '#3B82F6' }}>
                    {selectedPlace.website.replace(/^https?:\/\//, '').slice(0, 40)}
                  </a>
                </div>
              )}
              {selectedPlace.rating > 0 && (
                <div style={{ color: '#F59E0B', fontSize: '0.8rem' }}>
                  Rating: {selectedPlace.rating}/5 ({selectedPlace.user_ratings_total || 0} reviews)
                </div>
              )}
            </div>

            {/* Email (required) */}
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={{ display: 'block', fontWeight: 500, fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                Email Address <span style={{ color: '#EF4444' }}>*</span>
              </label>
              <input
                type="email"
                value={addEmail}
                onChange={(e) => setAddEmail(e.target.value)}
                placeholder="business@example.com"
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #D1D5DB',
                  borderRadius: '0.375rem',
                  fontSize: '0.85rem',
                  boxSizing: 'border-box',
                }}
              />
              <p style={{ fontSize: '0.75rem', color: '#9CA3AF', margin: '0.25rem 0 0' }}>
                Google Places doesn't provide emails. Check the business website for contact info.
              </p>
            </div>

            {/* Action type */}
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={{ display: 'block', fontWeight: 500, fontSize: '0.85rem', marginBottom: '0.35rem' }}>
                Add as
              </label>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                {[
                  { value: 'contact', label: 'Contact' },
                  { value: 'recipient', label: 'Campaign Recipient' },
                  { value: 'both', label: 'Both' },
                ].map((opt) => (
                  <label key={opt.value} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                    <input
                      type="radio"
                      name="addAction"
                      value={opt.value}
                      checked={addAction === opt.value}
                      onChange={() => setAddAction(opt.value)}
                    />
                    {opt.label}
                  </label>
                ))}
              </div>
            </div>

            {/* Campaign selector */}
            {addAction !== 'contact' && (
              <div style={{ marginBottom: '0.75rem' }}>
                <label style={{ display: 'block', fontWeight: 500, fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                  Campaign
                </label>
                <select
                  value={addCampaignId}
                  onChange={(e) => setAddCampaignId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    border: '1px solid #D1D5DB',
                    borderRadius: '0.375rem',
                    fontSize: '0.85rem',
                    background: '#fff',
                    boxSizing: 'border-box',
                  }}
                >
                  <option value="">Select a campaign...</option>
                  {campaigns.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.status})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Notes */}
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontWeight: 500, fontSize: '0.85rem', marginBottom: '0.25rem' }}>
                Notes
              </label>
              <textarea
                value={addNotes}
                onChange={(e) => setAddNotes(e.target.value)}
                rows={2}
                style={{
                  width: '100%',
                  padding: '0.5rem 0.75rem',
                  border: '1px solid #D1D5DB',
                  borderRadius: '0.375rem',
                  fontSize: '0.85rem',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* Result message */}
            {addResult && (
              <div style={{
                padding: '0.5rem 0.75rem',
                marginBottom: '0.75rem',
                borderRadius: '0.375rem',
                fontSize: '0.85rem',
                background: addResult.type === 'success' ? '#ECFDF5' : '#FEF2F2',
                color: addResult.type === 'success' ? '#065F46' : '#991B1B',
                border: `1px solid ${addResult.type === 'success' ? '#A7F3D0' : '#FECACA'}`,
              }}>
                {addResult.message}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAddModal(false)}
                style={{
                  padding: '0.5rem 1rem',
                  border: '1px solid #D1D5DB',
                  borderRadius: '0.375rem',
                  background: '#fff',
                  fontSize: '0.85rem',
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
              <button
                onClick={handleAddToOutreach}
                disabled={adding || !addEmail.trim() || (addAction !== 'contact' && !addCampaignId)}
                style={{
                  padding: '0.5rem 1rem',
                  background: adding ? '#9CA3AF' : '#3B82F6',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '0.375rem',
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  cursor: adding ? 'not-allowed' : 'pointer',
                }}
              >
                {adding ? 'Adding...' : 'Add to Outreach'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MapExplorer;
