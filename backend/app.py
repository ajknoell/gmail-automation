#!/usr/bin/env python3
"""Gmail Automation Backend Server"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Starting Gmail Automation Backend...")
    print("API running at http://localhost:5001")
    print("Frontend should run at http://localhost:5173")
    app.run(host='127.0.0.1', port=5001, debug=True)
