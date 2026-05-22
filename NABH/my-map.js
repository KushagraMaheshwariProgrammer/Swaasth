//Get user location
function getLocation(event) {
    event.preventDefault();
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(showPosition, showError);
    } else {
        document.getElementById("locationOutput").innerText = "Geolocation is not supported by this browser.";
    }
}
function showPosition(position) {
    const lat = position.coords.latitude;
    const lon = position.coords.longitude;
    // document.getElementById("locationOutput").innerText = `${lat},${lon}`;
    document.getElementById("lat").value = lat;
    document.getElementById("long").value = lon;
    getCityStateFromLatLng(lat, lon);
    fetchHospitals();
}
function showError(error) {
    switch(error.code) {
        case error.PERMISSION_DENIED:
            msg = "User denied";
            break;
        case error.POSITION_UNAVAILABLE:
            msg = "Unavailable.";
            break;
        case error.TIMEOUT:
            msg = "Timed out.";
            break;
        case error.UNKNOWN_ERROR:
            msg = "Unknown error";
            break;
    }
    //document.getElementById("DetectLocationDown").innerText = msg;
    document.querySelector('#DetectLocationDown li').innerText = "Please reset your browser's location permissions to continue.";
}

document.addEventListener("DOMContentLoaded", function () {
  getLocation(event);
});
// End of user location

//Get state & city by lat long
function getCityStateFromLatLng(lat, lng) {
  const apiKey = myMapData.googleApiKey;
  const url = `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${apiKey}`;

  fetch(url)
    .then(res => res.json())
    .then(data => {
      if (data.status === 'OK') {
        const results = data.results;
        if (results.length > 0) {
          const addressComponents = results[0].address_components;

          let city = '';
          let state = '';

          addressComponents.forEach(component => {
            if (component.types.includes('locality')) {
              city = component.long_name;
            }
            if (component.types.includes('administrative_area_level_1')) {
              state = component.long_name;
            }
          });

          document.getElementById("locationOutput").innerText = `${city},${state}`;
          const selectStateDown = document.getElementById('selectState');
          const tomSelectStateDown = selectStateDown.tomselect;
          const selectCityDown = document.getElementById('selectCity');
          const tomSelectCityDown = selectCityDown.tomselect;
          setTimeout(() => {
            tomSelectStateDown.setValue([state]);
          }, 1000);
          setTimeout(() => {
            tomSelectCityDown.setValue([city]);
          }, 2000);
          //console.log(city);
          //console.log(state);
        }
      } else {
        console.log('Geocoding failed:', data.status);
      }
    })
    .catch(error => console.error('Error:', error));
}

//Get Lat long by state and city
async function getLatLong(state, city) {
  const apiKey = myMapData.googleApiKey;
  //const address = `${city}, ${state}, India`;
  const address = [city, state, 'India'].filter(Boolean).join(', ');
  const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(address)}&key=${apiKey}`;

  try {
    const response = await fetch(url);
    const result = await response.json();

    if (result.status === "OK" && result.results.length > 0) {
      const { lat, lng } = result.results[0].geometry.location;
      document.getElementById("lat").value = lat;
        document.getElementById("long").value = lng;
      //console.log(`Latitude: ${lat}, Longitude: ${lng}`);
    } else {
      console.warn('Location not found:', result.status);
    }
  } catch (error) {
    console.error('Geocoding error:', error);
  }
}

document.getElementById('selectCity').addEventListener('change', function () {
  const city = this.value;
  const state = document.getElementById('selectState').value;
  if (city && state) {
    getLatLong(state, city);
    //document.getElementById("locationOutput").innerText = `${city},${state}`;
  }else if (state) {
    getLatLong(state, '');
  }

});

//Fetch Hospitals list 
function fetchHospitals(page) {
  // Show loader
  document.getElementById('hospitalResultsMap').style.display = 'flex';
  document.getElementById('hospitalResultsList').style.display = 'flex';

  const formData = new FormData(document.getElementById('hospitalSearchForm'));
  const selectedSpecText = document.getElementById('selectedSpecText').value;
  formData.append('selectedSpecText', selectedSpecText);
  formData.append('page', page);
  fetch(`${myMapData.ajax_url}`, {
    method: 'POST',
    body: formData,
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('hospitalResults').innerHTML = data.html;
    renderPagination(data.pagination);
    document.getElementById('hospitalResultsList').style.display = 'none';
    const mapData = data.mapData;
    if (mapData && Array.isArray(mapData)) {
      const fallbackLat = document.getElementById('lat').value;
      const fallbackLng = document.getElementById('long').value;
      updateMapMarkers(mapData, fallbackLat, fallbackLng); 
    }
     // Hide loader
    document.getElementById('hospitalResultsMap').style.display = 'none';
    //console.log(mapData);
    // Scroll to results
    // const resultsSection = document.getElementById('hospitalResults');
    // if (resultsSection) {
    //   resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    // }
  });
}

fetchHospitals(1);

// document.getElementById('searchText').addEventListener('input', function() {
//   fetchHospitals();
// });

document.getElementById('searchHospitalBtn').addEventListener('click', function(event) {
    event.preventDefault();
    const selState = document.getElementById('selectState').value;
    const selCity = document.getElementById('selectCity').value;

    // document.getElementById("locationOutput").innerText = `${selCity},${selState}`;
    const isValidState = selState && selState !== 'Select State';
    const isValidCity = selCity && selCity !== 'Select City';

    if (isValidState || isValidCity) {
      const displayCity = isValidCity ? selCity : '';
      const displayState = isValidState ? selState : '';
      const locationText = [displayCity, displayState].filter(Boolean).join(', ');
      document.getElementById("locationOutput").innerText = locationText;
    }

    let selSpecialities = [];
    document.querySelectorAll('input[name="specialities[]"]:checked')
    .forEach(cb => {
        let label = document.querySelector(`label[for="${cb.id}"]`);
        if (label) {
          selSpecialities.push(label.innerText.trim());
        }
    });
    document.getElementById("selectedSpecText").value = selSpecialities.join(", ");

    fetchHospitals();
});


//Pagination 
function renderPagination(pagination) {
  const paginationSection = document.getElementById('pagination');
  paginationSection.innerHTML = ''; // Clear old

  const { total_pages, current_page, total_results} = pagination;
  const maxVisible = 5;

  if(total_results > 0){
  //Showing results text
  const showingText = document.createElement('p');
  showingText.className = 'text-center';
  const startCount = (current_page - 1) * 25 + 1;
  const endCount = Math.min(current_page * 25, total_results);
  showingText.innerHTML = `Showing <strong>${startCount}</strong>-<strong>${endCount}</strong> of <strong>${total_results}</strong> results`;

  paginationSection.appendChild(showingText);

  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'Page navigation');

  const ul = document.createElement('ul');
  ul.classList.add('pagination');

  let start = Math.max(1, current_page - Math.floor(maxVisible / 2));
  let end = Math.min(total_pages, start + maxVisible - 1);
  if (end - start < maxVisible - 1) {
    start = Math.max(1, end - maxVisible + 1);
  }

  // Previous Button
  const prevLi = document.createElement('li');
  prevLi.className = 'page-item' + (current_page === 1 ? ' disabled' : '');

  const prevLink = document.createElement('a');
  prevLink.className = 'page-link';
  prevLink.href = '#';
  prevLink.innerText = 'Previous';
  prevLink.addEventListener('click', (e) => {
    e.preventDefault();
    if (current_page > 1) fetchHospitals(current_page - 1);
  });

  prevLi.appendChild(prevLink);
  ul.appendChild(prevLi);

  // Numbered page buttons
  for (let i = start; i <= end; i++) {
    const li = document.createElement('li');
    li.className = 'page-item' + (i === current_page ? ' active' : '');

    const a = document.createElement('a');
    a.className = 'page-link';
    a.href = '#';
    a.innerText = i;

    a.addEventListener('click', (e) => {
      e.preventDefault();
      fetchHospitals(i);
    });

    li.appendChild(a);
    ul.appendChild(li);
  }

  // Next Button
  const nextLi = document.createElement('li');
  nextLi.className = 'page-item' + (current_page === total_pages ? ' disabled' : '');

  const nextLink = document.createElement('a');
  nextLink.className = 'page-link';
  nextLink.href = '#';
  nextLink.innerText = 'Next';
  nextLink.addEventListener('click', (e) => {
    e.preventDefault();
    if (current_page < total_pages) fetchHospitals(current_page + 1);
  });

  nextLi.appendChild(nextLink);
  ul.appendChild(nextLi);

  nav.appendChild(ul);
  paginationSection.appendChild(nav);
}
}

//Show google map with hospital marker
    let map;
    let markers = [];
  function initMap() {
    // Default center (India)
    const center = { lat: 20.5937, lng: 78.9629 };
    map = new google.maps.Map(document.getElementById("map"), {
      zoom: 5,
      center: center,
      zoomControl: true,
      mapTypeControl: false,
      streetViewControl: false,
      fullscreenControl: false,
      scaleControl: false,
      rotateControl: false,
    });
  }

  let currentInfoWindow = null;
  function updateMapMarkers(hospitals,fallbackLat,fallbackLng) {
  // Clear old markers
  markers.forEach(marker => marker.setMap(null));
  markers = [];

  //if (!hospitals.length) return;
  const fallbackPosition = { lat: parseFloat(fallbackLat), lng: parseFloat(fallbackLng) };
  if (!hospitals.length) {
    map.setCenter(fallbackPosition);
    map.setZoom(7);
    return;
  }

  //Show circle range of 100km
  if (myMapData.env === 'local' || myMapData.env === 'development') {
    const radiusRange = new google.maps.Circle({
        map: map,
        center: fallbackPosition,
        radius: 100000, // 100km in meters
        fillColor: "#4285F4",
        fillOpacity: 0.2,
        strokeColor: "#4285F4",
        strokeOpacity: 0.8,
        strokeWeight: 2,
      });
  }

  const bounds = new google.maps.LatLngBounds();
  hospitals.forEach(hospital => {
    const position = { lat: parseFloat(hospital.lat), lng: parseFloat(hospital.lng) };
    const marker = new google.maps.Marker({
      position,
      map,
      title: hospital.name,
      icon: "https://nabh.co/wp-content/themes/nabh/assets/images/badges/hospital-pin.png",
    });
    const infoWindow = new google.maps.InfoWindow({
      content: `<div>
                <strong>${hospital.name}</strong><br /><br />
                <span>${hospital.address}</span><br /><br />
                <strong class="fw-bold"><a href="https://www.google.com/maps?q=${hospital?.lat},${hospital?.lng}" target="_blank">Show on Map</a></strong>
              </div>`,
    });
    marker.addListener("click", () => {
      if (currentInfoWindow) {
        currentInfoWindow.close();
      }
      infoWindow.open(map, marker);
      currentInfoWindow = infoWindow;
    });
    markers.push(marker);
    bounds.extend(position);
  });

  map.fitBounds(bounds);
}


//Show State and city Dropdown

async function loadStates() {
  const response = await fetch(`${myMapData.ajax_url}?action=get_states`, {
    method: 'POST'
  });
  const result = await response.json();
  const states = result;

    const selectState = document.getElementById('selectState');
    const tomSelectState = selectState.tomselect;
    //tomSelectState.clearOptions();
    states.forEach(state => {
      //console.log(state);
    tomSelectState.addOption({ value: state, text: state });
    });
    tomSelectState.refreshOptions(false);
}

async function loadCities(stateName) {

  const response = await fetch(`${myMapData.ajax_url}?action=get_cities_by_state&state=`+stateName, {
    method: 'POST'
  });

  const result = await response.json();
  const cities = result;

    const selectCity = document.getElementById('selectCity');
    const tomSelectCity = selectCity.tomselect;
    tomSelectCity.clear(); 
    tomSelectCity.clearOptions();
    tomSelectCity.addOption({ value: '', text: 'Select City' });
    cities.forEach(city => {
        tomSelectCity.addOption({ value: city, text: city });
    });
    tomSelectCity.refreshOptions(false);
    tomSelectCity.setValue('');
}

      loadStates();

      document.getElementById('selectState').addEventListener('change', function () {
        const selectedState = this.value;
        if (selectedState) {
          getLatLong(selectedState, '');
          loadCities(selectedState);
        }
      });