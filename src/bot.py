from tweepy import OAuthHandler, Cursor, API
import openai
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import twitter_credentials as tc
from time import sleep


envpath = Path('.') / '.env'
load_dotenv(dotenv_path=envpath)

# setup the openapi auth
openai.api_key = tc.OPENAI_KEY

# auth = OAuthHandler(os.environ['CONSUMER_KEY'], os.environ['CONSUMER_SECRET'])
# auth.set_access_token(os.environ['ACCESS_TOKEN'],
#                       os.environ['ACCESS_TOKEN_SECRET'])
auth = OAuthHandler(tc.CONSUMER_KEY, tc.CONSUMER_SECRET)
auth.set_access_token(tc.ACCESS_TOKEN, tc.ACCESS_TOKEN_SECRET)
api = API(auth, wait_on_rate_limit=True)
last_sub = 'Liverpool'


def run_bot():
    while True:
        # Query Twitter for trending topics
        trending = get_trending()
        print(trending)
        # Determine if a tweet can be made
        determined = determine_tweetability(trending)
        print(determined)
        # If so, generate a tweet on the corresponding topic, and make that tweet
        det = determined[:3]
        tweet = determined[3:]
        subject = determine_subject(trending, tweet)
        print("subject:", subject)
        global last_sub
        if last_sub != subject:
            print(det)
            last_sub = subject
            if det == 'YES':
                print("tweet this:", tweet)
                api.update_status(tweet)
        else:
            print("already tweeted about", subject)
        sleep(60*10)  # 60 seconds times n minuts


def get_trending():
    trends = api.get_place_trends(id=23424977)
    trending = []
    for trend in trends[0]["trends"]:
        trending.append(trend["name"])
    return trending


def determine_tweetability(topics):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": "You are a classification bot. You will take in a comma separated list of trending twitter topics, and determine if you can make a tweet about any of those subjects and relate the subject to web3. If you can make the tweet reply 'YES' followed by the subject you have selected. If you cannot make the tweet, you will reply with 'NO'. All responses will start with 'YES' or 'NO '. You will only answer 'YES' or 'NO ' - you will not categorize all of the subjects. Reply 'OK' if you understand."},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": ", ".join(topics)}]
    )
    resp = completion.choices[0].message.content
    return resp


def determine_subject(trending, tweet):
    for trend in trending:
        if trend in tweet:
            return trend
    return None


if __name__ == "__main__":
    run_bot()
