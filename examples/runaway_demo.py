import os

import agentops
from openai import OpenAI


def main() -> None:
    server = os.environ.get("AGENTOPS_URL", "http://localhost:8000")
    
    #init the agentops client
    agentops.init(server_url=server, project="demo", max_llm_calls=5)

    client = OpenAI()
    try:
        for i in range(10):
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": f"Hello {i}"}],
            )
    except Exception as e:
        print(f"Agent terminated: {e}")


if __name__ == "__main__":
    main()


