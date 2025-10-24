"""
Demo script showing HTTP A2A monitoring.
"""
import os
import time

import agentops
import requests
import httpx


def main() -> None:
    server = os.environ.get("AGENTOPS_URL", "http://localhost:8000")
    
    # Initialize AgentOps with HTTP monitoring enabled
    agentops.init(
        server_url=server, 
        project="http-a2a-demo", 
        max_llm_calls=10,
        monitor_http=True  # Enable HTTP A2A monitoring
    )

    print("🚀 Starting HTTP A2A monitoring demo...")
    
    # Use run context to properly track the session
    with agentops.start_run():
        try:
            # Test requests library
            print("📡 Making requests to external APIs...")
            
            # GitHub API
            response = requests.get("https://api.github.com/users/octocat")
            print(f"GitHub API: {response.status_code}")
            
            # JSONPlaceholder API
            response = requests.post("https://jsonplaceholder.typicode.com/posts", 
                                   json={"title": "Test Post", "body": "Test content"})
            print(f"JSONPlaceholder API: {response.status_code}")
            
            # Test httpx library
            print("📡 Making requests with httpx...")
            
            with httpx.Client() as client:
                # HTTPBin API
                response = client.get("https://httpbin.org/json")
                print(f"HTTPBin API: {response.status_code}")
                
                # Test POST with data
                response = client.post("https://httpbin.org/post", 
                                     json={"agent": "test", "data": "sample"})
                print(f"HTTPBin POST: {response.status_code}")
            
            # Test error handling
            print("📡 Testing error handling...")
            try:
                requests.get("https://httpbin.org/status/404")
            except Exception as e:
                print(f"Expected error: {e}")
            
            # Test timeout
            try:
                requests.get("https://httpbin.org/delay/2", timeout=1)
            except Exception as e:
                print(f"Timeout error: {e}")
            
            print("✅ HTTP A2A monitoring demo completed!")
            print("🌐 Check the dashboard at http://localhost:5173 to see the HTTP calls")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")


if __name__ == "__main__":
    main()