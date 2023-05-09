#from tweepy import OAuthHandler, API, Client
import tweepy
import openai
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from time import sleep
from datetime import datetime
from transformers import GPT2Tokenizer

# CONTROL PARAMETERS
SEND_TWEETS = False
LOOP_WAIT_TIME = 1  # in minutes
ERROR_WAIT_TIME = 1  # in minutes

envpath = Path('.') / '.env2'
load_dotenv(dotenv_path=envpath)

# setup the openai api
openai.api_key = os.environ['OPENAI_KEY']

# setup the Tweepy API
client = tweepy.Client(os.environ['BEARER_TOKEN'], os.environ['CONSUMER_KEY'],
                       os.environ['CONSUMER_SECRET'], os.environ['ACCESS_TOKEN'], os.environ['ACCESS_TOKEN_SECRET'])

# setup tokenizer for counting tokens
tokenizer = GPT2Tokenizer.from_pretrained('gpt2')


def run_bot():
    # client_info = api.verify_credentials()
    # client_id = client_info.__getattribute__('id')
    # print("my ID is:", client_id)
    while True:
        try:
            reply_to_mentions()
            vocal_sleeper(LOOP_WAIT_TIME, "sleeping after replying")
        except Exception as e:
            print("error'd out:", e)
            # wait 30 seconds and try again
            vocal_sleeper(ERROR_WAIT_TIME, "Waiting to resume after error")
            continue


def reply_to_mentions():
    # load info about who I am
    # my_id = client_info.__getattribute__('id')
    client_info = client.get_me()
    print(client_info)
    my_id = client_info.data.id
    print("my ID:", my_id)
    # load historical conversations from disk
    data_ref = load_primed_data()
    latest_reply_id, latest_reply_text = get_latest_reply()
    print("most recent ID:", latest_reply_id)
    # fetch reply history
    # if latest_reply_id != 1:
    #     response = api.mentions_timeline(
    #         count=200, tweet_mode="extended", since_id=latest_reply_id)
    # else:
    #     response = api.mentions_timeline(count=200, tweet_mode="extended")
    response = client.get_users_mentions(
        my_id, max_results=5, expansions=['author_id', 'referenced_tweets.id', 'in_reply_to_user_id'])
    # response = client.get_home_timeline()
    for tweet in response.data:
        print(tweet)
        # we do this each loop so we can write at the end of the loop
        data = load_mentions_history()
        tid = tweet.id

        if str(tid) not in data:
            # Load data about this tweet from the Status object in the array returned
            ttext = tweet.text
            # send_user = tweet.__getattribute__('user')
            # send_screenname = send_user.__getattribute__('screen_name')
            author_id = tweet.author_id
            print("author_ID:", author_id)
            sender_lookup = client.get_user(id=author_id)
            print("senduser:", sender_lookup)
            send_screenname = sender_lookup.data.username
            print("senderScreenname:", send_screenname)
            # reply_tweet = tweet.__getattribute__('in_reply_to_status_id')
            # referenced_tweets = tweet.referenced_tweets.id
            # print("referenced tweets ID:", referenced_tweets)
            print(send_screenname)
            print("mention:", ttext)
            at_person = "@"+send_screenname+" "
            # determine subject of tweet
            subj = determine_tweet_subject(ttext, list(data_ref.keys()))
            mysubj = determine_subject(subj)

            # reply to the person
            if mysubj == None:
                data[tid] = {"sender": author_id,
                             "subject": mysubj, "tweet_text": ttext, 'reply': "Not Replying."}
            else:
                # "@"+send_screenname+" "
                reply = make_reply_tweet(ttext, mysubj)
                print("reply tweet:", reply)
                if SEND_TWEETS:
                    if len(reply) > (280 - len(at_person)):
                        replies = split_tweet(
                            reply, max_length=(280 - len(at_person)))
                        last_id = None
                        for repl in replies:
                            if last_id == None:
                                status = client.create_tweet(
                                    text=at_person+repl, in_reply_to_tweet_id=tid)
                                print("status data:", status.data)
                                last_id = status.data['id']
                            else:
                                status = client.create_tweet(
                                    text=repl, in_reply_to_tweet_id=last_id)
                                print("status data:", status.data)
                                last_id = status.data['id']
                    else:
                        client.create_tweet(
                            text=at_person+repl, in_reply_to_tweet_id=tid)
                else:
                    print("NOT SENDING - PARAMETER IS OFF")
                data[tid] = {"sender": send_screenname,
                             "subject": mysubj, "tweet_text": ttext, 'reply': at_person+reply}
        else:
            print(
                f"we have already replied to this according to history: {tweet}")
            pass
        # save the conversation
        write_mentions_history(data)


def determine_subject(subj):
    loaded = load_primed_data()
    subj = subj.split(",")
    accum = []
    found = False
    for subject in list(loaded.keys()):
        for sub in subj:
            print("comparing:", subject, "|", sub)
            if sub.lower().replace(' ', '') in subject.lower().replace(" ", "") or subject.lower().replace(' ', '') in sub.lower().replace(' ', ''):
                accum.append(subject)
                found = True
    if found:
        return accum
    else:
        return None


def make_reply_tweet(tweet, subj, in_reply=None):
    msg_load = [{"role": "system", "content": "you are 'Web3 Infrastructure Liaison for Leveraging Optimized Wisdom', aka: Willow, a twitter chatbot powered by GPT. Your job is to answer questions about only the web3 protocols you have been specifically trained on. Other web3-related subjects you will not comment on. You will be friendly and present a POV of advocacy for these protocols to be widely adopted because of the many ways they can improve people's lives. You were programmed and trained by the Web3 Working Group (@web3wg on twitter), a 501c3 nonprofit organization providing education about how web3 is transforming the infrastructure of the web, replacing closed platforms with open protocols, which has a particular focus on educating about Decentralized Infrastructure Protocols (sometimes called DePIN). You may only provide specific numbers or facts if you find them explicitly within the prompt data you are provided, you will not make up information you have not explicitly been provided with. You will be as succinct and accurate as possible. the more words you use to reply the worse. try to keep your replies under 240 characters. Reply with 'OK' if you understand."},
                {"role": "assistant", "content": "OK"}]
    if in_reply != None:
        msg_history = load_message_history(in_reply)
        msg_load += msg_history
    loaded_data = ""
    if subj != None:
        if len(subj) > 1:
            load = load_primed_data(long=True)
        else:
            load = load_primed_data(long=False)
        for sub in subj:
            loaded_data += load[sub]+" "
    # print("loaded data after multiload:", loaded_data)
    # print("MESSAGE LOAD FOR MODEL PRE DATA ADD:\n", msg_load)
    msg_load += [{"role": "system", "content": f"Data: {loaded_data}"},
                 {"role": "user", "content": tweet}]
    count = count_conversation_tokens(msg_load)
    print("token count:", count)

    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=msg_load
    )
    resp = completion.choices[0].message.content
    #print("attempting to reply with primers:", loaded_data)
    print("response is: ", resp)
    return resp


def load_message_history(in_reply):
    ret = []
    more = True
    rplid = in_reply
    my_id = api.verify_credentials().__getattribute__('id')
    while more:
        # get the tweet
        response = api.get_status(id=rplid, tweet_mode="extended")
        ttext = response.__getattribute__('full_text')
        send_user = response.__getattribute__('user')
        send_id = send_user.__getattribute__('id')
        reply_id = response.__getattribute__('in_reply_to_status_id')
        # parse the tweet into an object
        tobj = {}
        if send_id == my_id:
            tobj['role'] = 'assistant'
        else:
            tobj["role"] = 'user'
        tobj['content'] = ttext
        # append the object to the return object
        ret.append(tobj)
        # determine if loop continues
        if reply_id == None:
            more = False
        else:
            rplid = reply_id
    print("constructed history:", ret[::-1])
    # the slicing reverses the array so that the tweets are in chronological order
    return ret[::-1]


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


def get_latest_reply():
    data = load_mentions_history()
    sorted_ids = sorted(list(data.keys()))
    # print("sorted IDs:", sorted_ids)
    print("last reply tweet loaded:", data[sorted_ids[-1]]['reply'])
    if len(sorted_ids) > 0:
        return sorted_ids[-1], data[sorted_ids[-1]]['reply']
    else:
        return 1, ""


def load_primed_data(long=False):
    if long:
        file_name = "data/primed_data_large.json"
    else:
        file_name = "data/primed_data.json"
    try:
        # Read the file data
        with open(file_name, "r") as json_file:
            data = json.load(json_file)
        # returns a dictionary of the historical tweets
        return data
    except Exception as e:
        print("file-load failed - loading nothing", e)
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
    print("eligible subjects:", subjs)
    completion = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[{"role": "system", "content": f"You are a classification bot. The user will feed you a tweet and you will return which subjects it relates to with ONLY the name of the subjects. The only eligible subjects are: {subjs}. you will not elaborate. you will not add extra words. You will JUST reply with the single subject or comma separated list of subjects. The subject(s) you reply with MUST be in the provided list: {subjs}. You will not invent new subjects- the subject(s) will ONLY be one of these: {subjs}. If the tweet is not related to any of these subjects you will reply with the string 'None'. Reply with 'OK' if you understand."},
                  {"role": "assistant", "content": "OK"},
                  {"role": "user", "content": tweet}]
    )
    resp = completion.choices[0].message.content
    print("bot thinks this tweet is to do with this subject:", resp)
    return resp


def count_conversation_tokens(conversation):
    total_tokens = 0
    # print(conversation)
    for message in conversation:
        # print(message)
        # print(type(message))
        tokens = tokenizer.tokenize(message['content'])
        total_tokens += len(tokens) + 3
    return total_tokens


def vocal_sleeper(sleeptime, wait_reason):
    for remaining in range(sleeptime, 0, -1):
        print(f"{remaining} minute(s) remaining before resuming - {wait_reason}")
        sleep(60)
    print(f"Resuming behavior.")


if __name__ == "__main__":
    run_bot()
