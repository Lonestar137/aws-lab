#!/usr/bin/env python3

from dotenv import load_dotenv
from pywebio.input import *
from pywebio.output import *
import requests
import json

config = dotenv_values()

def send_api_request():
    put_markdown("# AWS API Gateway Request Sender")

    ## Get user input
    # api_url = input("Enter API Gateway URL:", type=TEXT, required=True)
    method = select("Select HTTP method:", ['GET', 'POST', 'PUT', 'DELETE'])
    
    headers = {}
    while True:
        header_key = input("Enter header key (or leave blank to finish):", type=TEXT)
        if not header_key:
            break
        header_value = input(f"Enter value for {header_key}:", type=TEXT)
        headers[header_key] = header_value

    body = textarea("Enter request body (JSON format):", rows=5)

    ## Send request
    try:
        if method == 'GET':
            response = requests.get(api_url, headers=headers)
        elif method == 'POST':
            response = requests.post(api_url, headers=headers, json=json.loads(body) if body else None)
        elif method == 'PUT':
            response = requests.put(api_url, headers=headers, json=json.loads(body) if body else None)
        elif method == 'DELETE':
            response = requests.delete(api_url, headers=headers)

        ## Display response
        put_text("Response Status Code:", response.status_code)
        put_text("Response Headers:")
        put_code(json.dumps(dict(response.headers), indent=2))
        put_text("Response Body:")
        put_code(response.text)

    except Exception as e:
        put_error(f"An error occurred: {str(e)}")

    ## Ask if user wants to send another request
    if actions("Send another request?", ["Yes", "No"]) == "Yes":
        clear()
        send_api_request()

if __name__ == '__main__':
    send_api_request()

