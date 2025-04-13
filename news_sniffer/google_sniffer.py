import os
import json
import requests
import re
from dotenv import load_dotenv
from openai import OpenAI

# Load credentials
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Load assistant config
with open("news_sniffer_config.json", "r") as f:
    assistant_config = json.load(f)

ASSISTANT_ID = assistant_config["id"]

def fetch_google_results(query, num_results=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CSE_ID,
        "q": query,
        "num": num_results
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    data = res.json()

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title"),
            "link": item.get("link"),
            "snippet": item.get("snippet")
        })

    return results


def build_prompt(query, results):
    prompt = f"Topic: {query}\n\n"
    prompt += "Here are the most relevant news headlines from today:\n\n"

    for i, item in enumerate(results, 1):
        prompt += (
            f"{i}. {item['title']}\n"
            f"URL: {item['link']}\n"
            f"Summary: {item['snippet']}\n\n"
        )

    prompt += (
        "\nYou are a macro-financial news analysis agent supporting a market risk intelligence system. "
        "You will receive a list of news articles pulled from a Google News API search. Your job is to analyze each article's content "
        "to determine its potential impact on financial markets, particularly regarding systemic stress, liquidity, credit spreads, volatility, "
        "rates, inflation, unemployment, macro indicators, and flight-to-safety behavior.\n\n"
        "For each article, return a structured JSON object containing the following fields:\n"
        "- headline: The article title\n"
        "- source: The news outlet or publication\n"
        "- url: Direct link to the article\n"
        "- timestamp: Date/time of publication (if available)\n"
        "- summary: 1–3 short bullet points highlighting the market-relevant insights\n"
        "- category: One or more relevant tags such as 'Rates & Curve', 'Credit & Volatility', 'Macro Indicators', 'Flight to Safety', 'Policy', or 'Geopolitics'\n"
        "- sentiment: One of ['Risk-On', 'Neutral', 'Risk-Off'], based on the tone and market implications\n\n"
        "Focus only on macro-relevant or market-moving insights. Ignore fluff, human interest, or irrelevant items. "
        "You are not summarizing for general interest — you are generating inputs for a market bottom detection system."
    )


    return prompt


def run_news_sniffer(query):
    print(f"🔍 Searching for: {query}")
    results = fetch_google_results(query)

    print(f"📡 Found {len(results)} articles. Passing to NewsSniffer...")

    thread = client.beta.threads.create()

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=build_prompt(query, results)
    )

    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )

    # Wait for completion
    while True:
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status == "completed":
            break

    messages = client.beta.threads.messages.list(thread_id=thread.id)
    for msg in reversed(messages.data):
        response = msg.content[0].text.value.strip()
        print("\n🧠 NewsSniffer Output:\n")
        print(response)

        # Attempt to extract valid JSON from assistant response
        try:
            match = re.search(r"```json(.*?)```", response, re.DOTALL)
            if match:
                json_str = match.group(1).strip()
                parsed = json.loads(json_str)
                with open("sniffer_output.json", "w") as f:
                    json.dump(parsed, f, indent=2)
                print("\n✅ Output saved to sniffer_output.json")
            else:
                raise ValueError("No JSON block found in response.")
        except Exception as e:
            print(f"\n⚠️ Could not parse output as JSON. Reason: {e}")
            with open("sniffer_output_raw.txt", "w") as f:
                f.write(response)
            print("📝 Raw response saved to sniffer_output_raw.txt")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python google_sniffer.py \"your search query here\"")
    else:
        query = " ".join(sys.argv[1:])
        run_news_sniffer(query)
