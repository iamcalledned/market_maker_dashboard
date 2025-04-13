import os
from openai import OpenAI
from dotenv import load_dotenv

# Load your API key
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

def run_news_sniffer(query):
    print(f"🔍 Searching for: {query}\n")

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a web intelligence agent named NewsSniffer. "
                    "Search the web for the most relevant recent headlines about the query. "
                    "Summarize each result in 1–2 sentences. Focus on macro, markets, policy, and global risk. "
                    "Respond in markdown format: a bulleted list with source, summary, and link."
                )
            },
            {
                "role": "user",
                "content": f"Find the latest news for: {query}"
            }
        ],
        tools=[{"type": "web_search"}],  # OpenAI plugin-style tool call
        tool_choice="auto"
    )

    reply = response.choices[0].message.content
    print("🧠 NewsSniffer Report:\n")
    print(reply)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python news_sniffer.py \"your search query here\"")
    else:
        query = " ".join(sys.argv[1:])
        run_news_sniffer(query)
