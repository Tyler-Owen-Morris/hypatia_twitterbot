from tweepy import OAuthHandler, Cursor, API
import openai
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import twitter_credentials as tc


envpath = Path('.') / '.env'
load_dotenv(dotenv_path=envpath)

# setup the openapi auth
openai.api_key = os.environ['OPENAI_KEY']

# auth = OAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
# auth.set_access_token(os.environ['ACCESS_TOKEN'],
#                       os.environ['ACCESS_TOKEN_SECRET'])
auth = OAuthHandler(tc.CONSUMER_KEY, tc.CONSUMER_SECRET)
auth.set_access_token(tc.ACCESS_TOKEN, tc.ACCESS_TOKEN_SECRET)
api = API(auth, wait_on_rate_limit=True)


def run_bot():
    # Query Twitter for trending topics
    trending = get_trending()
    print(trending)
    # Determine if a tweet can be made

    # If so, generate a tweet on the corresponding topic, and make that tweet

    pass


def get_trending():
    trends = api.get_place_trends(id=23424977)
    trending = []
    for trend in trends[0]["trends"]:
        trending.append(trend["name"])
    return trending


def determine_tweetability(topics):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": ""},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": ", ".join(topics)}]
    )
    resp = completion.choices[0].message.content


if __name__ == "__main__":
    run_bot()
