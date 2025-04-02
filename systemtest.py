import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get variables from environment
account = os.getenv("ACCOUNT")
project = os.getenv("AZURE_ORG")
work_item_id = int(os.getenv("ADO_ITEM"))
personal_access_token = os.getenv("PAT")

# API endpoint
url = f"https://{account}.visualstudio.com/{project}/_apis/wit/workitems/{work_item_id}?api-version=7.2-preview.3"

# Basic Auth using PAT (username is blank)
response = requests.get(
    url,
    auth=("", personal_access_token)
)

if response.status_code == 200:
    work_item = response.json()
    fields = work_item.get("fields", {})

    # Filter and clean up System fields
    system_fields = {
        key.replace("System.", ""): value
        for key, value in fields.items()
        if key.startswith("System.")
    }

    # Print in a clean list
    print("\nSystem Fields:")
    for field_name, field_value in system_fields.items():
        print(f"- {field_name}: {field_value}")
else:
    print(f"Failed to fetch work item: {response.status_code}")
    print(response.text)

