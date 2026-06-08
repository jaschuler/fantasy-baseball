import sys
import requests
import pandas as pd
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config.settings import FANGRAPHS_COOKIE, FANGRAPHS_COOKIE_NAME

session = requests.Session()
session.cookies.set(FANGRAPHS_COOKIE_NAME, FANGRAPHS_COOKIE, domain='www.fangraphs.com')
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.fangraphs.com/projections',
})

# Try the direct Steamer API endpoint
url = 'https://www.fangraphs.com/api/steamer/batting'
params = {
    'type': 'ros',
    'pos': 'all',
    'team': 0,
    'players': 0,
}

# Add to test_fangraphs.py
url_pitch = 'https://www.fangraphs.com/api/steamer/pitching'
params_pitch = {
    'type': 'ros',
    'pos': 'all',
    'team': 0,
    'players': 0,
}

# # Add this to test_fangraphs.py after the existing code
import json

print("\nFetching Steamer ROS pitching...")
response_p = session.get(url_pitch, params=params_pitch)
print(f"Status: {response_p.status_code}")
data_p = json.loads(response_p.text)
print(f"Total pitchers: {len(data_p)}")
print(f"\nAll columns: {list(data_p[0].keys())}")

# print("Fetching Steamer ROS batting...")
# response = session.get(url, params=params)
# print(f"Status: {response.status_code}")
# print(f"Content type: {response.headers.get('content-type', '')}")
# print(f"First 500 chars: {response.text[:500]}")

# # Add this to test_fangraphs.py after the existing code
# import json
# data = json.loads(response.text)
# print(f"\nTotal players: {len(data)}")
# print(f"\nAll columns: {list(data[0].keys())}")