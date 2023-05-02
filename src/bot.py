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
last_sub = ''


def run_bot():
    client_info = api.verify_credentials()
    client_id = client_info.__getattribute__('id')
    print("my ID is:", client_id)
    while True:
        try:
            reply_to_mentions(client_info)
            # Query Twitter for trending topics
            trending = get_trending()
            # print(trending)
            # Determine if a tweet can be made
            determined = determine_tweetability(trending)
            # print(determined)
            # If so, generate a tweet on the corresponding topic, and make that tweet
            det = determined.split(" - ")[0]
            subj_str = determined.split(" - ")[-1]
            subject = determine_subject(trending, subj_str)
            print("determined:", det, " | subject:", subject)
            if subject != None and det == 'YES':
                eligible = determine_subject_eligibility(subject)
                if eligible:
                    tweet = make_tweet(subject)
                    print("tweet this:", tweet)
                    if len(tweet) > (280):
                        tweets = split_tweet(tweet, max_length=(280))
                        last_id = None
                        for message in tweets:
                            if last_id == None:
                                status = api.update_status(message)
                                last_id = status.__getattribute__('id')
                            else:
                                status = api.update_status(
                                    message, in_reply_to_status_id=last_id)
                                last_id = status.__getattribute__('id')
                    else:
                        api.update_status(tweet)
                else:
                    print("tweeted about this subject too recently")
                    sleep(60*5)
                    continue
            else:
                print("Bot could not find a subject to Tweet about")
            sleep(60*(random.randint(18, 35)))
        except Exception as e:
            print("error'd out:", e)
            sleep(60*2)  # wait 30 seconds and try again
            continue


def reply_to_mentions(client_info):
    # load info about who I am
    my_id = client_info.__getattribute__('id')
    # load historical conversations from disk
    response = api.mentions_timeline(count=20)
    for tweet in response:
        # we do this each loop so we can write at the end of the loop
        data = load_mentions_history()
        # Load data about this tweet from the Status object in the array returned
        tid = tweet.__getattribute__('id')
        ttext = tweet.__getattribute__('text')
        reply_user = tweet.__getattribute__('in_reply_to_user_id')
        send_user = tweet.__getattribute__('user')
        send_screenname = send_user.__getattribute__('screen_name')
        # print(send_screenname)
        #print("mention:", ttext)
        at_person = "@"+send_screenname+" "
        if str(tid) not in data:
            # reply to the person
            reply = make_reply_tweet(ttext)  # "@"+send_screenname+" "
            print("reply tweet:", reply)
            if len(reply) > (280 - len(at_person)):
                replies = split_tweet(reply, max_length=(280 - len(at_person)))
                last_id = None
                for repl in replies:
                    if last_id == None:
                        status = api.update_status(
                            at_person+repl, in_reply_to_status_id=tid)
                        last_id = status.__getattribute__('id')
                    else:
                        status = api.update_status(
                            at_person+repl, in_reply_to_status_id=last_id)
                        last_id = status.__getattribute__('id')
            else:
                api.update_status(reply, in_reply_to_status_id=tid)
            data[tid] = [{"them": ttext, 'us': reply}]
        else:
            # print("we have already replied to this according to history")
            pass
        # save the conversation
        write_mentions_history(data)


def get_trending():
    trends = api.get_place_trends(id=23424977)
    trending = []
    for trend in trends[0]["trends"]:
        trending.append(trend["name"])
    return trending


def determine_tweetability(topics):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": "You are a classification bot. You will take in a comma separated list of trending twitter topics, and determine if you can make a tweet about any of those subjects and relate the subject to web3. If you can make the tweet reply 'YES' followed by the subject you have selected separated by the strin ' - '. If you cannot make the tweet, you will reply ONLY with the string 'NO '. All responses must start with the characters 'YES' or 'NO '. You will only answer 'YES' followed by ' - ' and the subject, or 'NO ' - you will not categorize all of the subjects. Reply 'OK' if you understand."},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": ", ".join(topics)}]
    )
    resp = completion.choices[0].message.content
    return resp


def make_tweet(topic):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": "You are a twitter bot. I will give you a popular subject, and you will generate a tweet relating that subject to web3 with the goal of generating as much traffic as possible. Ensure your tweets are within the character limit, and inspire users to reply. do not include quotes around your tweets. Reply with 'OK' if you understand"},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": topic}]
    )
    resp = completion.choices[0].message.content
    return resp


def make_reply_tweet(topic):
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": "You are a twitter bot. I will give you the text of someone tweeting at you, and you will generate a reply. Your goal is to answer questions around web3 technologies, support community developers, and encourage new interest in web3. You will do your best to be nice to others, and carry on a respectful conversation. your character limit is 250 - you must never use more characters than 250. Reply with 'OK' if you understand"},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": topic}]
    )
    resp = completion.choices[0].message.content
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


def write_mentions_history(data):
    file_name = "data/mentions.json"
    with open(file_name, "w") as json_file:
        json.dump(data, json_file)


def load_subject_history():
    file_name = f"data/history.json"
    # Write the empty file if it doesn't exist
    if not os.path.exists(file_name):
        with open(file_name, "w") as json_file:
            json.dump({}, json_file)
    # Read the file data
    with open(file_name, "r") as json_file:
        data = json.load(json_file)
    # returns a dictionary of the historical tweets
    return data


def determine_subject(trending, subj_str):
    for trend in trending:
        if trend in subj_str:
            return trend
    return None


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


if __name__ == "__main__":
    run_bot()
