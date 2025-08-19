// scripts.js - helper functions + map init
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Map init for request form
function initRequestMap() {
  const mapEl = document.getElementById("map");
  if (!mapEl) return;
  const map = L.map("map").setView([6.5244, 3.3792], 11); // Lagos default
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(map);

  let pickupMarker = null;
  let dropMarker = null;
  let clickCount = 0;

  function setPickup(latlng){
    if (pickupMarker) map.removeLayer(pickupMarker);
    pickupMarker = L.marker(latlng, {draggable:true}).addTo(map).bindPopup("Pickup").openPopup();
    document.querySelector("input[name='pickup_lat']").value = latlng.lat;
    document.querySelector("input[name='pickup_lng']").value = latlng.lng;
    pickupMarker.on('dragend', (e)=> {
      const p = e.target.getLatLng();
      document.querySelector("input[name='pickup_lat']").value = p.lat;
      document.querySelector("input[name='pickup_lng']").value = p.lng;
    });
  }
  function setDrop(latlng){
    if (dropMarker) map.removeLayer(dropMarker);
    dropMarker = L.marker(latlng, {draggable:true, icon: L.icon({iconUrl: 'https://unpkg.com/leaflet@1.9.3/dist/images/marker-icon.png'})}).addTo(map).bindPopup("Dropoff").openPopup();
    document.querySelector("input[name='dropoff_lat']").value = latlng.lat;
    document.querySelector("input[name='dropoff_lng']").value = latlng.lng;
    dropMarker.on('dragend', (e)=> {
      const p = e.target.getLatLng();
      document.querySelector("input[name='dropoff_lat']").value = p.lat;
      document.querySelector("input[name='dropoff_lng']").value = p.lng;
    });
  }

  map.on('click', function(e){
    clickCount++;
    if (clickCount % 2 === 1) {
      setPickup(e.latlng);
    } else {
      setDrop(e.latlng);
    }
  });

  // try geolocation for convenience
  if (navigator.geolocation){
    navigator.geolocation.getCurrentPosition(function(pos){
      map.setView([pos.coords.latitude, pos.coords.longitude], 13);
    });
  }
}

function attachRideFormSubmit(){
  const form = document.getElementById("rideForm");
  if (!form) return;
  form.addEventListener("submit", function(ev){
    // basic validation: ensure coords are set
    const pLat = document.querySelector("input[name='pickup_lat']").value;
    const dLat = document.querySelector("input[name='dropoff_lat']").value;
    if (!pLat || !dLat) {
      ev.preventDefault();
      alert("Please select pickup and dropoff points on the map (click twice).");
    }
  });
}

// Polling logic for customer ride status
async function pollRequest(){
  if (typeof REQUEST_ID === 'undefined') return;
  const url = `/customer/poll/${REQUEST_ID}/`;
  try {
    const res = await fetch(url);
    const j = await res.json();
    document.getElementById("rr-status").textContent = j.status;
    const list = document.getElementById("matches-list");
    list.innerHTML = "";
    (j.matches || []).forEach(m=>{
      const el = document.createElement("div");
      el.className = "list-group-item";
      el.innerHTML = `<div><strong>${m.driver__user__username}</strong> — ${m.status} <div class="small text-muted">Dist: ${m.distance_to_pickup_km}km • ETA ${m.eta_to_pickup_min}min</div></div>`;
      list.appendChild(el);
    });
    if (j.ride) {
      const r = j.ride;
      const ri = document.getElementById("ride-info");
      ri.innerHTML = `<div class="alert alert-info">Matched to <strong>${r.driver}</strong> — Ride #${r.id} • Status: ${r.status}</div>`;
    }
  } catch (e){
    console.error(e);
  }
}
