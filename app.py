# New API Endpoint

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Endpoint to get a list of accounts."""
    accounts = fetch_accounts()
    return jsonify(accounts)