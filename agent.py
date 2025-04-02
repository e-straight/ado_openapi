import requests
import base64
from dotenv import load_dotenv
load_dotenv()
import os
import json
import jsonref
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.projects.models import FunctionTool, FunctionToolDefinition, AuthenticationType, OpenApiTool


api_version = os.getenv('API_VERSION')
pat = os.getenv('PAT')
organization = os.getenv('AZURE_ORG')
project_connection_string = os.getenv('PROJECT_CONNECTION_STRING')

# Create an Azure AI Client from a connection string, copied from your Azure AI Foundry project.
# At the moment, it should be in the format "<HostName>;<AzureSubscriptionId>;<ResourceGroup>;<HubName>"
# Customer needs to login to Azure subscription via Azure CLI and set the environment variables

project_client = AIProjectClient.from_connection_string(
    credential=DefaultAzureCredential(),
    conn_str=project_connection_string,
)

auth_str = f":{pat}"  # Format is "username:password" where username is empty
base64_auth = base64.b64encode(auth_str.encode()).decode()

# Create Auth object for the OpenApiTool using PAT
auth = {
    "type": "basic",
    "username": "",  # Azure DevOps uses empty username with PAT
    "password": pat,
    "headers": {
        "Authorization": f"Basic {base64_auth}"
    }
}

# Initialize agent OpenAPI tool using the read in OpenAPI spec
with open("./wit_openapi_trimmed.json", "r") as f:
    openapi_wit = jsonref.loads(f.read())

# Initialize agent OpenApi tool using the read in OpenAPI spec
openapi_tool = OpenApiTool(
    name="work_item_tracking",
    spec=openapi_wit,
    description="Retrieve and manage Azure DevOps work items. Can query work items assigned to specific users in the Vienna project.",
    auth=auth
)

# Create agent with OpenApi tool and process assistant run
with project_client:
    agent = project_client.agents.create_agent(
        model="gpt-4o",
        name="my-assistant",
        instructions="""You are a helpful assistant that can query Azure DevOps work items. 
        When asked about work items, use the WIQL query endpoint to find work items assigned to Elijah Straight in the Vienna project.
        Format your responses clearly and include relevant work item details like ID, title, state, and assigned to.""",
        tools=[openapi_tool],
    )

    # [END create_agent_with_openapi]

    print(f"Created agent, ID: {agent.id}")

    # Create thread for communication
    thread = project_client.agents.create_thread()
    print(f"Created thread, ID: {thread.id}")

    # Create message to thread
    message = project_client.agents.create_message(
        thread_id=thread.id,
        role="user",
        content="Show me all work items assigned to Elijah Straight in the Vienna project",
    )
    print(f"Created message, ID: {message.id}")

    # Create and process agent run in thread with tools
    run = project_client.agents.create_and_process_run(thread_id=thread.id, agent_id=agent.id)
    print(f"Run finished with status: {run.status}")

    if run.status == "failed":
        print(f"Run failed: {run.last_error}")

    run_steps = project_client.agents.list_run_steps(thread_id=thread.id, run_id=run.id)

    # Loop through each step
    for step in run_steps.data:
        print(f"Step {step['id']} status: {step['status']}")

        # Check if there are tool calls in the step details
        step_details = step.get("step_details", {})
        tool_calls = step_details.get("tool_calls", [])

        if tool_calls:
            print("  Tool calls:")
            for call in tool_calls:
                print(f"    Tool Call ID: {call.get('id')}")
                print(f"    Type: {call.get('type')}")

                function_details = call.get("function", {})
                if function_details:
                    print(f"    Function name: {function_details.get('name')}")
        print()  # add an extra newline between steps

    # Delete the assistant when done
    project_client.agents.delete_agent(agent.id)
    print("Deleted agent")

    # Fetch and log all messages
    messages = project_client.agents.list_messages(thread_id=thread.id)
    print(f"Messages: {messages}")