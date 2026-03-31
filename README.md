iq buffer generation and preview with interface to a signal hound vsg60a,  also calculators, etc

Run polarization calculator with backend TLE search:

1. Install dependencies:
	pip install -r requirements.txt
2. Start backend server:
	python tle_backend.py
3. Open browser:
	http://localhost:8000

Notes:
- TLE search in the web UI now uses backend endpoint `/api/tle/search`.
- `CelesTrak` and `Space-Track.org` are both supported.
- Space-Track credentials are prompted in the browser and sent only to the local backend for the active request.
