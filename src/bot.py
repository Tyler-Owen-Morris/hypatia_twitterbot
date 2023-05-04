from tweepy import OAuthHandler, Cursor, API
import openai
import os
import json
from pathlib import Path
from dotenv import load_dotenv
import twitter_credentials as tc
from time import sleep
from datetime import datetime
import random
import pandas as pd


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


def run_bot():
    client_info = api.verify_credentials()
    client_id = client_info.__getattribute__('id')
    print("my ID is:", client_id)
    while True:
        try:
            reply_to_mentions(client_info)
            vocal_sleeper(1, "sleeping after replying")
        except Exception as e:
            print("error'd out:", e)
            # wait 30 seconds and try again
            vocal_sleeper(1, "Waiting to resume after error")
            continue


def reply_to_mentions(client_info):
    # load info about who I am
    my_id = client_info.__getattribute__('id')
    # load historical conversations from disk
    data_ref = load_primed_data()
    # fetch reply history
    response = api.mentions_timeline(count=100, tweet_mode="extended")
    for tweet in response:
        # we do this each loop so we can write at the end of the loop
        data = load_mentions_history()
        # Load data about this tweet from the Status object in the array returned
        tid = tweet.__getattribute__('id')
        ttext = tweet.__getattribute__('full_text')
        reply_user = tweet.__getattribute__('in_reply_to_user_id')
        send_user = tweet.__getattribute__('user')
        send_screenname = send_user.__getattribute__('screen_name')
        print(send_screenname)
        print("mention:", ttext)
        at_person = "@"+send_screenname+" "
        if str(tid) not in data:
            # determine subject of tweet
            subj = determine_tweet_subject(ttext, list(data_ref.keys()))
            mysubj = determine_subject(subj)
            # reply to the person
            reply = make_reply_tweet(ttext, mysubj)  # "@"+send_screenname+" "
            print("reply tweet:", reply)
            # if len(reply) > (280 - len(at_person)):
            #     replies = split_tweet(reply, max_length=(280 - len(at_person)))
            #     last_id = None
            #     for repl in replies:
            #         if last_id == None:
            #             status = api.update_status(
            #                 at_person+repl, in_reply_to_status_id=tid)
            #             last_id = status.__getattribute__('id')
            #         else:
            #             status = api.update_status(
            #                 at_person+repl, in_reply_to_status_id=last_id)
            #             last_id = status.__getattribute__('id')
            # else:
            #     api.update_status(at_person+repl, in_reply_to_status_id=tid)
            data[tid] = {"sender": send_screenname,
                         "subject": mysubj, "tweet_text": ttext, 'reply': at_person+reply}
        else:
            print("we have already replied to this according to history")
            pass
        # save the conversation
        write_mentions_history(data)


def determine_subject(subj):
    loaded = load_primed_data()
    for subject in list(loaded.keys()):
        if subj in subject:
            return subject
    return None


def make_reply_tweet(tweet, subj):
    if subj != None:
        loaded_data = load_primed_data()[subj]
    else:
        loaded_data = ""
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": "You are a twitter bot. You will be fed all the relevant data you need on a subject, and a user tweet. you will reply with the most informative and helpful response possible. reply with 'OK' if you understand."},
                  {"role": "assistant", "content": "OK"},
                  {"role": "system", "content": f"Data: {loaded_data}"},
                  {"role": "user", "content": tweet}]
    )
    resp = completion.choices[0].message.content
    print("attempting to reply with primers:", loaded_data)
    print("response is: ", resp)
    return resp


def load_mentions_history():
    file_name = "data/mentions.json"
    # Write the empty file if it doesn't exist
    if not os.path.exists(file_name):
        with open(file_name, "w") as json_file:
            json.dump({}, json_file)
    # Read the file data
    with open(file_name, "r") as json_file:
        data = json.load(json_file)
    # returns a dictionary of the historical tweets
    return data


def load_primed_data():
    file_name = "data/primed_data.json"
    try:
        # Read the file data
        with open(file_name, "r") as json_file:
            data = json.load(json_file)
        # returns a dictionary of the historical tweets
        return data
    except:
        return {}


def write_mentions_history(data):
    file_name = "data/mentions.json"
    with open(file_name, "w") as json_file:
        json.dump(data, json_file)


def split_tweet(text, max_length=280):
    words = text.split()
    tweets = []
    current_tweet = ""

    for word in words:
        # If adding the word to the current tweet would exceed the max_length
        if len(current_tweet) + len(word) + 1 > max_length:
            # If the current tweet is not empty, add it to the tweets list
            if current_tweet:
                tweets.append(current_tweet.strip())

            # Start a new tweet with the current word
            current_tweet = word
        else:
            # Otherwise, add the word to the current tweet
            current_tweet += " " + word

    # Add the last tweet to the tweets list, if not empty
    if current_tweet:
        tweets.append(current_tweet.strip())

    return tweets


def determine_subject_eligibility(subj):
    min_between_subjet_repeats = 30
    file_name = f"data/history.json"
    utc_now = datetime.utcnow()
    ret = False
    with open(file_name, "r") as json_file:
        data = json.load(json_file)
    if subj in data:
        # history exists
        last_time = datetime.strptime(data[subj], "%Y-%m-%d %H:%M:%S")
        timediff = utc_now - last_time
        minutes = timediff.total_seconds() / 60
        if minutes > min_between_subjet_repeats:
            ret = True
            data[subj] = utc_now.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ret = False
    else:
        data[subj] = utc_now.strftime("%Y-%m-%d %H:%M:%S")
        ret = True
    # Write the updated data object back to disk
    with open(file_name, "w") as json_file:
        json.dump(data, json_file)
    return ret


def determine_tweet_subject(tweet, subjects):
    subjs = ",".join(subjects)
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": f"You are a classification bot. The user will feed you a tweet and you will return which subject it belongs to with ONLY the name of the subject. The only eligible subjects are: {subjs}. you will not elaborate. you will not add extra words. You will JUST reply with the single subject. Reply with 'ok' if you understand."},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": tweet}]
    )
    resp = completion.choices[0].message.content
    print("bot thinks this tweet is to do with this subject:", resp)
    return resp


def vocal_sleeper(sleeptime, wait_reason):
    for remaining in range(sleeptime, 0, -1):
        print(f"{remaining} minute(s) remaining before resuming - {wait_reason}")
        sleep(60)
    print(f"Resuming behavior.")


if __name__ == "__main__":
    run_bot()
