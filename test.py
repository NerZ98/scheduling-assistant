import json
import requests
import time
import sys
from termcolor import colored

# Configuration
BASE_URL = "http://127.0.0.1:5000"
SESSION_COOKIE = None

# Names extracted from the image
database_names = [
    "Ankit Gupta", "Ashish Rangnekar", "Diya Sadekar", "Love Verma",
    "Manish Israni", "Mithil Kashid", "Monika Amrutkar", "Rupal Behere",
    "Sarthak Parihar", "Shashank Singh", "Swapnil Chavan", "Yash Mehrotra",
    "John Smith", "Jane Doe", "Michael Johnson", "Emily Davis",
    "Sarah Wilson", "David Brown", "Jennifer Miller", "Robert Jones",
    "Jessica Garcia", "Rutu Desai", "Mary Johnson"
]

# Generate 10x test cases dynamically
test_cases = []
for name in database_names:
    test_cases.extend([
        {"name": f"Schedule meeting with {name}",
         "message": f"schedule with {name}",
         "expected_contains": ["day would you like", "date for this"],
         "not_expected_contains": ["not in the organization's contact list"],
         "type": "attendee_single"},
        {"name": f"Add {name} to attendees",
         "message": f"add {name}",
         "expected_contains": ["day would you like", "date for this"],
         "not_expected_contains": ["not in the organization's contact list"],
         "type": "attendee_single"}
    ])

# Special test cases
test_cases.extend([
    {"name": "Ambiguous name selection", "message": "add John", "expected_contains": ["Multiple contacts found"], "type": "ambiguous_name"},
    {"name": "Unknown name", "message": "add UnknownPerson", "expected_contains": ["not in the organization's contact list"], "type": "attendee_not_found"},
])

# Function to send messages
def send_message(message):
    global SESSION_COOKIE
    headers = {"Content-Type": "application/json"}
    cookies = {"session": SESSION_COOKIE} if SESSION_COOKIE else {}
    data = {"message": message}
    response = requests.post(f"{BASE_URL}/message", headers=headers, cookies=cookies, json=data)
    if "session" in response.cookies:
        SESSION_COOKIE = response.cookies["session"]
    return response.json()

# Function to reset session
def reset_session():
    global SESSION_COOKIE
    response = requests.post(f"{BASE_URL}/reset", headers={"Content-Type": "application/json"}, cookies={"session": SESSION_COOKIE} if SESSION_COOKIE else {}, json={})
    if "session" in response.cookies:
        SESSION_COOKIE = response.cookies["session"]
    return response.json()

# Run test cases
def run_test(test_case):
    print(f"Running test: {colored(test_case['name'], 'cyan')}")
    response = send_message(test_case["message"])
    bot_response = response.get("response", "")
    passed = all(expected.lower() in bot_response.lower() for expected in test_case.get("expected_contains", []))
    if not passed:
        print(colored(f"  FAILED: Expected output not found in response: {bot_response}", "red"))
    else:
        print(colored("  PASSED", "green"))
    return passed

def main():
    print(colored("Starting Scheduling Assistant Test Suite", "yellow"))
    print("=" * 60)
    try:
        requests.get(BASE_URL)
    except requests.exceptions.ConnectionError:
        print(colored(f"ERROR: Could not connect to server at {BASE_URL}", "red"))
        sys.exit(1)
    total_tests = len(test_cases)
    passed_tests = sum(run_test(tc) for tc in test_cases)
    print("=" * 60)
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(colored("All tests passed!" if passed_tests == total_tests else "Some tests failed.", "green" if passed_tests == total_tests else "yellow"))

if __name__ == "__main__":
    main()
