from flask import Flask, render_template, redirect, url_for
import requests
import os
import logging
import sqlite3

# Initialize Flask app with custom template folder
app = Flask(__name__, template_folder='templates')

# Configure logging only when debug mode is enabled
if app.debug:
    logging.basicConfig(level=logging.INFO)

# Load Cloudflare API credentials from environment variables
CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
CLOUDFLARE_KEY = os.getenv('CLOUDFLARE_KEY')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')


from flask import Flask, render_template, redirect, url_for
import requests
import os
import logging
import sqlite3

# Initialize Flask app with custom template folder
app = Flask(__name__, template_folder='templates')

# Configure logging only when debug mode is enabled
if app.debug:
    logging.basicConfig(level=logging.INFO)

# Load Cloudflare API credentials from environment variables
CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
CLOUDFLARE_KEY = os.getenv('CLOUDFLARE_KEY')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')

def setup_database():
    """Initialize the database and set up tables if they don't exist."""
    conn = sqlite3.connect('cloudflare_manager.db')
    cursor = conn.cursor()

    # Create zones table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            type TEXT,
            plan_name TEXT,
            name_servers TEXT,
            original_name_servers TEXT,
            created_on TEXT,
            modified_on TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auth_code_from_directnic TEXT
        )
    ''')

    # Add a table to track the version of the database
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER
        )
    ''')

    # Check if there's a version in the db_version table, if not, insert version 1
    cursor.execute('SELECT COUNT(*) FROM db_version')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO db_version (version) VALUES (1)')

    conn.commit()
    conn.close()

    """Initialize the database and set up tables if they don't exist."""
    conn = sqlite3.connect('cloudflare_manager.db')
    cursor = conn.cursor()

    # Create zones table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            type TEXT,
            plan_name TEXT,
            name_servers TEXT,
            original_name_servers TEXT,
            created_on TEXT,
            modified_on TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            auth_code_from_directnic TEXT
        )
    ''')

    # Add a table to track the version of the database
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS db_version (
            version INTEGER
        )
    ''')

    # Check if there's a version in the db_version table, if not, insert version 1
    cursor.execute('SELECT COUNT(*) FROM db_version')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO db_version (version) VALUES (1)')

    conn.commit()
    conn.close()

# Cloudflare API functions
def get_zones_with_params(params):
    """Fetches zones from Cloudflare based on provided parameters in a paginated manner."""
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        'X-Auth-Email': CLOUDFLARE_EMAIL,
        'X-Auth-Key': CLOUDFLARE_KEY
    }

    all_zones = []
    page = 0
    total_pages = 1  # Default to 1 for the first iteration
    max_iterations = 10  # Safety measure to avoid infinite loops
    iteration = 0

    while page < total_pages and iteration < max_iterations:
        page += 1  # Increment page number
        params['page'] = page
        iteration += 1

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            all_zones.extend(result.get('result', []))

            # Update total_pages based on result_info from Cloudflare
            total_pages = result.get('result_info', {}).get('total_pages', 1)
        else:
            # Log error messages only when debug mode is enabled
            if app.debug:
                logging.error(f"Failed to fetch zones for page {page}. Reason: {response.text}")

    return all_zones


def get_all_zones():
    """Retrieve all zones from Cloudflare."""
    return get_zones_with_params({'per_page': 50})


def get_paused_zones():
    """Retrieve paused zones from Cloudflare."""
    return get_zones_with_params({'status': 'paused', 'per_page': 50})


def get_zones_without_dnssec():
    """Retrieve zones from Cloudflare where DNSSEC is not active."""
    all_zones = get_all_zones()
    zones_without_dnssec = []

    url_template = "https://api.cloudflare.com/client/v4/zones/{}/dnssec"
    headers = {
        'X-Auth-Email': CLOUDFLARE_EMAIL,
        'X-Auth-Key': CLOUDFLARE_KEY
    }
    
    for zone in all_zones:
        zone_id = zone['id']
        response = requests.get(url_template.format(zone_id), headers=headers)
        if response.status_code == 200:
            dnssec_data = response.json()
            if dnssec_data['result']['status'] != 'active':
                zones_without_dnssec.append(zone)
        else:
            if app.debug:
                logging.error(f"Failed to fetch DNSSEC status for zone {zone_id}. Reason: {response.text}")

    return zones_without_dnssec

# Application routes
@app.route('/')
def index():
    """Render the index page with a table listing all Cloudflare zones."""
    zones = get_all_zones()
    return render_template('index.html', zones=zones, title="All Zones", account_id=CLOUDFLARE_ACCOUNT_ID)


@app.route('/pending')
def pending():
    """Render the Pending page with Cloudflare zones that have a 'pending' status."""
    pending_zones = get_zones_with_params({'status': 'pending', 'per_page': 50})
    return render_template('pending.html', zones=pending_zones, title="Pending Zones", account_id=CLOUDFLARE_ACCOUNT_ID)


@app.route('/reactivate')
def reactivate():
    """Render the Reactivate page with paused Cloudflare zones."""
    paused_zones = get_paused_zones()
    return render_template('reactivate.html', zones=paused_zones, title="Paused Zones", account_id=CLOUDFLARE_ACCOUNT_ID)


@app.route('/no_dnssec')
def no_dnssec():
    """Render a page listing Cloudflare zones without active DNSSEC."""
    zones = get_zones_without_dnssec()
    return render_template('no_dnssec.html', zones=zones, title="Zones Without DNSSEC", account_id=CLOUDFLARE_ACCOUNT_ID)


@app.route('/save_to_db', methods=['POST'])
def save_to_db():
    """Save zones data to the database."""
    zones = get_all_zones()
    conn = sqlite3.connect('cloudflare_manager.db')
    cursor = conn.cursor()
    
    for zone in zones:
        # Ensure name_servers and original_name_servers are lists before joining
        name_servers = zone.get('name_servers')
        if not isinstance(name_servers, list):
            name_servers = []

        original_name_servers = zone.get('original_name_servers')
        if not isinstance(original_name_servers, list):
            original_name_servers = []

        cursor.execute('''
            INSERT OR REPLACE INTO zones (
                id, name, status, type, plan_name, name_servers, 
                original_name_servers, created_on, modified_on, auth_code_from_directnic, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (
            zone.get('id'),
            zone.get('name'),
            zone.get('status'),
            zone.get('type'),
            zone.get('plan', {}).get('name'),
            ", ".join(name_servers),
            ", ".join(original_name_servers),
            zone.get('created_on'),
            zone.get('modified_on'),
            ""  # Placeholder for auth_code_from_directnic, replace when you have the data
        ))
        
        # Update the last_updated timestamp for the modified row
        cursor.execute('''
            UPDATE zones SET last_updated = CURRENT_TIMESTAMP WHERE id = ?
        ''', (zone.get('id'),))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('index'))

if __name__ == '__main__':
    setup_database()  # Initialize the database and create tables if they don't exist.
    app.run(debug=True)