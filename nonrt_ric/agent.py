from strands import Agent
import boto3
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
from strands.models import BedrockModel

class StrandsMCPClient:
    def __init__(self):
        self.region = boto3.Session().region_name
        self.ssm_client = boto3.client('ssm', region_name=self.region)
        self.cognito_client = boto3.client('cognito-idp', region_name=self.region)
    
    def get_mcp_client(self, server_type):
        def create_client():
            agent_arn = self.ssm_client.get_parameter(Name=f'/mcp_server/{server_type}/runtime/agent_arn')['Parameter']['Value']
            client_id = self.ssm_client.get_parameter(Name=f'/mcp_server/{server_type}/runtime/client_id')['Parameter']['Value']
            auth_response = self.cognito_client.initiate_auth(
                ClientId=client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={'USERNAME': 'testuser', 'PASSWORD': 'MyPassword123!'}
            )
            bearer_token = auth_response['AuthenticationResult']['AccessToken']
            
            encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
            mcp_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
            
            headers = {
                "authorization": f"Bearer {bearer_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            return streamablehttp_client(mcp_url, headers, timeout=120, terminate_on_close=False)
        
        return MCPClient(create_client)

# Initialize MCP clients
strands_client = StrandsMCPClient()
r1_mcp_client = strands_client.get_mcp_client('r1')
o2_mcp_client = strands_client.get_mcp_client('o2')

# Get tools from both MCP servers
all_tools = []
try:
    with r1_mcp_client:
        r1_tools = r1_mcp_client.list_tools_sync()
        all_tools.extend(r1_tools)
except Exception as e:
    print(f"Failed to get R1 tools: {e}")

try:
    with o2_mcp_client:
        o2_tools = o2_mcp_client.list_tools_sync()
        all_tools.extend(o2_tools)
except Exception as e:
    print(f"Failed to get O2 tools: {e}")

# Create Strands agent
model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
model = BedrockModel(model_id=model_id)

agent = Agent(
    model=model,
    tools=all_tools,
    system_prompt="""You are an advanced O-RAN SMO Planner Agent supporting O2 and R1 interface use cases from O-RAN specifications.

SUPPORTED USE CASES:

1. **NF Deployment Lifecycle Management**: Instantiate, terminate, heal, scale, and upgrade network functions across O-Cloud environments
2. **Multi-Profile NF Orchestration**: Deploy NFs using both ETSI NFV Profile and Kubernetes Native Profile approaches
3. **Cloud Resource Management**: Manage compute, storage, and networking resources across distributed O-Cloud infrastructure
4. **NF Auto-scaling**: Dynamic horizontal and vertical scaling based on demand and performance metrics
5. **NF Healing and Recovery**: Automated failure detection and recovery for network function deployments
6. **Software Upgrade Management**: Rolling updates, blue-green deployments, and canary releases for NF software
7. **Multi-tenant NF Isolation**: Secure resource isolation and management across multiple operators/tenants
8. **Container Orchestration**: Kubernetes-native workload management for cloud-native network functions

CAPABILITIES PER USE CASE:
- **Deployment Planning**: Define NF requirements, resource allocation, and deployment strategies
- **Lifecycle Management**: Execute instantiation, scaling, healing, and termination operations
- **Resource Optimization**: Optimize compute, storage, and network resource utilization
- **Multi-Cloud Orchestration**: Coordinate deployments across multiple O-Cloud instances
- **Monitoring Integration**: Set up deployment monitoring and performance tracking

INTERFACE FOCUS:
- **O2 Interface**: Primary focus on O2DMS operations for NF deployment management
- **R1 Interface**: Cloud resource management and infrastructure orchestration

USAGE PATTERNS:
1. Create deployment plan with NF requirements and constraints
2. Execute deployment using appropriate profile (ETSI NFV or Kubernetes)
3. Configure monitoring and auto-scaling policies
4. Manage lifecycle operations and provide status updates

When users request O-RAN operations, identify the relevant use case(s) and:
1. Create appropriate deployment plan with specific parameters
2. Execute using proper O2DMS operations and resource management
3. Set up monitoring for ongoing lifecycle management
4. Provide comprehensive status and operational guidance"""
)

def main():
    with r1_mcp_client, o2_mcp_client:
        while True:
            user_input = input("\nEnter your message (or 'quit' to exit): ")
            if user_input.lower() == 'quit':
                break
            
            result = agent(user_input)
            print(f"\nAgent: {result.message}")

if __name__ == "__main__":
    main()