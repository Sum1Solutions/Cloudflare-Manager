# app.py

from flask import Flask, render_template
import requests
import os

app = Flask(__name__)

# Load Cloudflare API credentials from environment variables
CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
CLOUDFLARE_KEY = os.getenv('CLOUDFLARE_KEY')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')


@app.route('/')
def index():
    """
    Endpoint to display all zones.
    Renders the index page with a table listing all Cloudflare zones.
    """
    zones = get_all_zones()
    return render_template('index.html', zones=zones, title="All Zones", account_id=CLOUDFLARE_ACCOUNT_ID)

@app.route('/reactivate.html')
def reactivate():
    """
    Endpoint to display paused zones and offer reactivation.
    Renders the Reactivate page with a table listing paused Cloudflare zones.
    """
    paused_zones = get_paused_zones()
    return render_template('reactivate.html', zones=paused_zones, title="Paused Zones", account_id=CLOUDFLARE_ACCOUNT_ID)

@app.route('/pending.html')
def pending():
    """
    Endpoint to display zones with a 'pending' status.
    Renders the Pending page with a table listing Cloudflare zones that are pending.
    """
    pending_zones = get_zones_by_status('pending')
    return render_template('pending.html', zones=pending_zones, title="Pending Zones", account_id=CLOUDFLARE_ACCOUNT_ID)

def get_all_zones():
    """
    Function to retrieve all zones from Cloudflare.
    """
    return get_zones_with_params({'per_page': 50})

def get_paused_zones():
    """
    Function to retrieve paused zones from Cloudflare.
    """
    return get_zones_by_status('paused')

def get_zones_by_status(status):
    """
    Function to retrieve zones from Cloudflare based on their status.
    """
    return get_zones_with_params({'status': status, 'per_page': 50})

def get_zones_with_params(params):
    """
    Helper function to retrieve zones based on provided parameters.
    """
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        'X-Auth-Email': CLOUDFLARE_EMAIL,
        'X-Auth-Key': CLOUDFLARE_KEY
    }

    all_zones = []
    page = 0
    total_pages = 1  # Default to 1 for first iteration

    while page < total_pages:
        page += 1  # Increment page number
        params['page'] = page

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            all_zones.extend(result.get('result', []))
            
            # Update total_pages based on result_info from Cloudflare
            total_pages = result.get('result_info', {}).get('total_pages', 1)
        else:
            print(f"Failed to fetch zones for page {page}. Reason: {response.text}")

    return all_zones

if __name__ == '__main__':
    app.run(debug=True)
