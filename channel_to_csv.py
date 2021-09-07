import configparser
import os 
import csv
from datetime import date


# Telethon imports
from telethon import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest

# --------- FUNCTIONS  -----------------
# handle Media Poll objects --> Take Message & Return formatted Poll Data
def handle_media_poll(message):
    # Extract options (possible answers) for a poll & save as line in string
    options = ""
    for i in range(len(message.media.poll.answers)):
        options += "{}: {}\n".format(message.media.poll.answers[i].option, message.media.poll.answers[i].text)
    # Extract votes for option, calculate percentage & save as line in string 
    extracted_results = ""
    if message.media.results.results is not None:
        for result in message.media.results.results:
            vote_percent = round(float(result.voters/message.media.results.total_voters)*100, 3)
            extracted_results += "{}: {} Votes ({}%)\n".format(result.option, result.voters, vote_percent)
    else:
        extracted_results = "Not visible/accessible."

    media_context = "Question: {}\nOptions:\n{}Total Votes: {}\nResults:\n{}".format(
        message.media.poll.question, options, message.media.results.total_voters, extracted_results
    )
    return media_context

# handle media web page object --> Extract url of object, Format message context & return
def handle_media_web(message):
    try:
        # get type of media
        try:
            t = message.media.webpage.type
        except:
            t = "not known"
        media_context = "Type: {}\nURL: {}\n\nDescription:\n\n{}".format(
            t, str(message.media.webpage.url), str(message.media.webpage.description)
            )
    except AttributeError as err:
        print("Threw Attribute error when trying to extract url from message with id {}.".format(message.id))
        media_context = "Failed to extract link.\n(Error: {})".format(err)   
    return media_context

# check the Media type; if necessary call above funcs; then return media_context
def set_media_context(message):
    # extract the message media type
    message_type = str(message.media).split('(')[0]
    # check for special cases
    if message_type == 'None':
        message_type = "No Media"
        media_context = "None"

    # If poll set media context to options and results (if visible)
    elif message_type == "MessageMediaPoll":
        media_context = handle_media_poll(message)
     
    # if MediaDocument download media
    elif message_type == "MessageMediaDocument":
        # save file name in media_context
        media_context = "Media Document"
    elif message_type == "MessageMediaPhoto":
        # save file name in media_context
        media_context = "Media Photo to be downloaded"
        # Download photo
    # check MediaPage = Link | extract link
    elif message_type == "MessageMediaWebPage":
        media_context = handle_media_web(message)
    else:
        media_context = ""
    
    return media_context

# Convert each message into a row (dict)
def message_to_row(message):
    media_context = set_media_context(message)    
    # convert date to more readable format
    date = message.date.strftime("%d.%m.%Y - %H:%M:%S")
    # Write values to row
    row = {
            "ID": message.id, 
            "DATE": date, 
            "MESSAGE": message.message, 
            "VIEWS": message.views,
            "FORWARDED": message.fwd_from,
            "TYPE": str(message.media).split('(')[0], 
            "MEDIA-Context": media_context,
            "MESSAGE-OBJECT" : str(message),
            }
    return row

# write messages to csv file (from list of dicts)
# each dict has keys of cols and represents one message 
def write_messages_to_csv(outFile, messages_dict):
    # Set fields (columns for csv file) | must match instance of message_to_row(message)
    fields = ["ID", "DATE", "MESSAGE", "VIEWS", "FORWARDED", "TYPE", "MEDIA-Context", "MESSAGE-OBJECT"]
    # Open File & write header + rows
    with open(outFile, 'w') as csvFile:
        writer = csv.DictWriter(csvFile, fieldnames = fields)
        writer.writeheader()
        writer.writerows(messages_dict)

# --------- Config & Init & Set variables ----------------
# Reading Configs & get vars (stored in external file for security) 
config = configparser.ConfigParser()
config.read("config.ini")

# Setting configuration values
api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
api_hash = str(api_hash)

phone = config['Telegram']['phone']
username = config['Telegram']['username']

# Create the client and connect
client = TelegramClient(username, api_id, api_hash)

#set empyt list to store each message as a dict
messages_dict = []
#set list to store all saved ID's in to skip duplicates
used_ids = []

# select file to save the messages in
today = date.today()
output_file = '[{}] laut_gedacht_pull.csv'.format(today.strftime("%d.%m.%Y"))
if os.path.isfile(output_file):
    os.remove(output_file)


# --------- Main Script ----------------
async def main(phone):
    await client.start()
    print("Client Created")
    # Ensure authorization
    if await client.is_user_authorized() == False:
        await client.send_code_request(phone)
        try:
            await client.sign_in(phone, input('Enter the code: '))
        except SessionPasswordNeededError:
            await client.sign_in(password=input('Password: '))

    me = await client.get_me()

    # Request input on channel 
    user_input_channel = input('Enter entity(telegram URL or entity id):')
    # If nothing is entered pull data from laut_gedacht
    if user_input_channel == "":
        user_input_channel = "t.me/laut_gedacht"

    if user_input_channel.isdigit():
        entity = PeerChannel(int(user_input_channel))
    else:
        entity = user_input_channel
    # Check wether user wants to download the files, if yes request a path or 'default' (defaults to '/downloads/')
    user_input_download = input('Do you want to download the WebDocs? y/n')
    if user_input_download.lower() != 'y' and user_input_download.lower() != 'n':
        print("What you entered is invalid. Setting 'False'.")
        want_download = False
    elif user_input_download.lower() == 'n':
        want_download = False
    else:
        want_download = True
        print("Enter the path for the file downloads. Type 'default' to use '/downloads/'.")
        while True:
            dir = input("Path name or 'default': ")
            if dir.lower() == 'default':
                download_dir = '/downloads/'
            elif os.path.isdir(dir):
                download_dir = dir
                break    
            elif os.path.isdir((str(os.getcwd()) + "/" + str(dir))):
                download_dir = dir
                break
            else:
                print("Please enter a valid path. It can be relative or absolute.")
        print("The files will be downloaded into {}".format(download_dir))
            

    
    # Use entity from above and await the client
    my_channel = await client.get_entity(entity)

    # Got channel, setting variables, offset_id is exclusive (see below)
    limit = 100
    all_messages = []
    total_messages = 0
    total_count_limit = 0

    # **** Start to pull data ****
    # The amount of messages that can be pulled in one go is limited by the API; r is set to a value high enough to fetch all messages 
    # Simplified equation for fetching all messages --> (r*20) > count(messages_in_channel)
    r = 25
    for i in range(r):   
        offset_id = 20 * (i+1) - 1
        mini_id = offset_id - 21
        print("\n[Cycle {}/{}] Trying to fetch messages from ID {} to {}.".format(i+1, r, mini_id, offset_id))

        #get selected chat history
        while True:
            history = await client(GetHistoryRequest(
                peer=my_channel,
                offset_id=offset_id,
                offset_date=None,
                add_offset=0,
                limit=limit,
                max_id=0,
                min_id=mini_id,
                hash=0
            ))
            if not history.messages:
                break
            messages = history.messages
            for message in messages:
                # check if download necessary for Document
                if want_download == True:
                    s_media_type = str(message.media).split('(')[0]
                    if s_media_type == "MessageMediaDocument" or s_media_type == "MessageMediaPhoto":
                        # set download name & update progress in terminal
                        download_to = "{}/{}-ID-{}".format(download_dir, s_media_type, str(message.id))
                        await client.download_media(message, download_to)
                        print("[Message-{}]Starting Download: {}.".format(str(message.id), download_to))

            # add messages as dict & update variables
            all_messages.append(message.to_dict())
            offset_id = messages[len(messages) - 1].id
            total_messages = len(all_messages)
            if total_count_limit != 0 and total_messages >= total_count_limit:
                break
        
        # selected history is saved. go through it & extract wanted data
        # save it as a dict and append to list  while skipping duplicates
        # NOTE: duplicates are possible because of the offset id and the 'r'-var (see above)
        for message in messages: 
            if message.id not in used_ids: 
                row = message_to_row(message)
                messages_dict.append(row)
                used_ids.append(message.id)

    # When done with fetching data and downloading media objects, Write messages to a csv file using the above function
    print("\nWriting messages.")    
    write_messages_to_csv(output_file, messages_dict)

# Keep client active; script is using asynchronous methods
with client:
    client.loop.run_until_complete(main(phone))