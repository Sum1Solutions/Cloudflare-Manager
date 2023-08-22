from flask import Flask, render_template, redirect, url_for
import requests
import os
import logging
import sqlite3
import db_util

# Initialize Flask app with custom template folder
app = Flask(__name__, template_folder='templates')

# Configure logging only when debug mode is enabled
if app.debug:
    logging.basicConfig(level=logging.INFO)

# Load Cloudflare API credentials from environment variables
CLOUDFLARE_EMAIL = os.getenv('CLOUDFLARE_EMAIL')
CLOUDFLARE_KEY = os.getenv('CLOUDFLARE_KEY')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')


# Cloudflare API functions

def get_zones_with_params(params):
    """Fetch zones from Cloudflare based on provided parameters in a paginated manner."""
    url = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        'X-Auth-Email': CLOUDFLARE_EMAIL,
        'X-Auth-Key': CLOUDFLARE_KEY
    }

    all_zones = []
    page = 0
    total_pages = 1  # Start with 1 for the first iteration
    max_iterations = 10  # Avoid potential infinite loops

    while page < total_pages and page < max_iterations:
        page += 1  # Increment page number
        params['page'] = page

        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            all_zones.extend(result.get('result', []))

            # Update total_pages based on result_info from Cloudflare
            total_pages = result.get('result_info', {}).get('total_pages', 1)
        else:
            # Log error messages only in debug mode
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
            # Log error messages only in debug mode
            if app.debug:
                logging.error(f"Failed to fetch DNSSEC status for zone {zone_id}. Reason: {response.text}")

    return zones_without_dnssec

# Flask routes

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

@app.route('/view_db')
def view_db():
    """
    Endpoint to view all tables in the database and their metadata.
    
    This function fetches the list of all tables in the SQLite database 
    and for each table, retrieves its columns, the total row count, and 
    the last updated timestamp. The data is then passed to the 
    `view_db.html` template for rendering.
    """
    conn = sqlite3.connect('cloudflare_manager.db')
    cursor = conn.cursor()
    
    # Fetch all table names in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    table_names = [table[0] for table in cursor.fetchall()]
    
    tables = {}
    tables_metadata = {}  # Dictionary to store metadata like row count and last updated timestamp
    
    for table_name in table_names:
        # For each table, fetch details of its columns
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [{"name": column[1], "type": column[2], "notnull": column[3], "default": column[4], "pk": column[5]} for column in cursor.fetchall()]
        tables[table_name] = columns
        
        # Fetch row count for each table
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]
        
        # Fetch the last updated timestamp for each table (assuming there's a 'last_updated' column)
        cursor.execute(f"SELECT MAX(last_updated) FROM {table_name}")
        last_updated = cursor.fetchone()[0]
        
        # Store the metadata
        tables_metadata[table_name] = {
            'row_count': row_count,
            'last_updated': last_updated
        }
    
    conn.close()
    
    return render_template('view_db.html', tables=tables, tables_metadata=tables_metadata)

@app.route('/view_table_data/<table_name>')
def view_table_data(table_name):
    """Endpoint to view data for a specific table in the database."""
    conn = sqlite3.connect('cloudflare_manager.db')
    cursor = conn.cursor()
    
    # Fetch the column names for the table
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [{"name": column[1]} for column in cursor.fetchall()]
    
    # Fetch the data for the table
    cursor.execute(f"SELECT * FROM {table_name}")
    data = cursor.fetchall()
    
    conn.close()
    
    return render_template('view_table_data.html', data=data, table_name=table_name, columns=columns)


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
    db_util.setup_database()  # Initialize the database and create tables if they don't exist
    app.run(debug=True)