from flask import Flask, render_template, jsonify
import csv
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

app = Flask(__name__)

def read_csv_data():
    """Read webapp data from CSV file"""
    webapps = []
    try:
        with open('data.csv', 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                webapps.append({
                    'webname': row.get('webname', '').strip(),
                    'env': row.get('env', '').strip(),
                    'healthUrl': row.get('healthUrl', '').strip(),
                    'infoUrl': row.get('infoUrl', '').strip(),
                    'port': row.get('port', '').strip(),
                    'supportEmail': row.get('supportEmail', '').strip()
                })
    except FileNotFoundError:
        print("Error: data.csv file not found")
    except Exception as e:
        print(f"Error reading CSV: {e}")
    
    return webapps

def check_endpoint(url, timeout=10):
    """Check if endpoint is accessible and return status and response data"""
    try:
        response = requests.get(url, timeout=timeout)
        status_code = response.status_code
        
        if status_code == 200:
            try:
                data = response.json()
                return {
                    'status_code': status_code,
                    'success': True,
                    'data': data,
                    'error': None
                }
            except json.JSONDecodeError:
                return {
                    'status_code': status_code,
                    'success': True,
                    'data': response.text,
                    'error': None
                }
        else:
            return {
                'status_code': status_code,
                'success': False,
                'data': None,
                'error': f"HTTP {status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            'status_code': None,
            'success': False,
            'data': None,
            'error': "Timeout"
        }
    except requests.exceptions.ConnectionError:
        return {
            'status_code': None,
            'success': False,
            'data': None,
            'error': "Connection Error"
        }
    except Exception as e:
        return {
            'status_code': None,
            'success': False,
            'data': None,
            'error': str(e)
        }

def extract_git_info(info_data):
    """Extract git information from Spring Boot info endpoint"""
    git_info = {}
    if isinstance(info_data, dict):
        git_data = info_data.get('git', {})
        if isinstance(git_data, dict):
            # Common git info fields
            git_info['branch'] = git_data.get('branch', 'N/A')
            git_info['commit'] = git_data.get('commit', {}).get('id', 'N/A')[:8] if git_data.get('commit') else 'N/A'
        
        # Java version
        build_info = info_data.get('build', {})
        if isinstance(build_info, dict):
            git_info['java_version'] = build_info.get('version', 'N/A')
    
    return git_info

def check_single_webapp(webapp):
    """Check health and info endpoints for a single webapp"""
    result = webapp.copy()
    
    # Check health endpoint
    health_result = check_endpoint(webapp['healthUrl'])
    result['health_status'] = health_result['success']
    result['health_error'] = health_result['error']
    result['health_status_code'] = health_result['status_code']
    
    # Check info endpoint
    info_result = check_endpoint(webapp['infoUrl'])
    result['info_status'] = info_result['success']
    result['info_error'] = info_result['error']
    result['info_status_code'] = info_result['status_code']
    
    # Extract git info if available
    if info_result['success'] and info_result['data']:
        git_info = extract_git_info(info_result['data'])
        result['git_info'] = git_info
    else:
        result['git_info'] = {}
    
    return result

@app.route('/')
def index():
    """Home page with check button"""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_all_webapps():
    """Perform health checks on all webapps"""
    webapps = read_csv_data()
    
    if not webapps:
        return jsonify({
            'success': False,
            'error': 'No webapp data found',
            'results': []
        })
    
    results = []
    
    # Use ThreadPoolExecutor for concurrent health checks
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_webapp = {executor.submit(check_single_webapp, webapp): webapp for webapp in webapps}
        
        for future in as_completed(future_to_webapp):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                webapp = future_to_webapp[future]
                error_result = webapp.copy()
                error_result.update({
                    'health_status': False,
                    'health_error': f"Check failed: {str(e)}",
                    'info_status': False,
                    'info_error': f"Check failed: {str(e)}",
                    'git_info': {}
                })
                results.append(error_result)
    
    return jsonify({
        'success': True,
        'results': results,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)