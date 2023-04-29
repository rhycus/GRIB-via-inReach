print('Starting import', flush=True)
import emailfunctions
from base64 import urlsafe_b64decode, urlsafe_b64encode
import time
from datetime import datetime
import pandas as pd
import xarray as xr
import cfgrib
import pandas as pd
import numpy as np
import time
print('Import finished', flush=True)

LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION = ""
YOUR_EMAIL = ""


def processGrib(path):
    grib = xr.open_dataset(path).to_dataframe() # Was easiest for me to process the grib as a pandas dataframe.

    timepoints = grib.index.get_level_values(0).unique()
    latmin = grib.index.get_level_values(1).unique().min()
    latmax = grib.index.get_level_values(1).unique().max()

    lonmin = grib.index.get_level_values(2).unique().min()
    lonmax = grib.index.get_level_values(2).unique().max()
    latdiff = pd.Series(grib.index.get_level_values(1).unique()).diff().dropna().round(6).unique() # This is the difference between each lat/lon point. It was mainly used for debugging.
    londiff = pd.Series(grib.index.get_level_values(2).unique()).diff().dropna().round(6).unique()

    if len(latdiff) > 1 or len(londiff) > 1:
        print('Irregular point separations!', flush=True)

    gribtime = grib['time'].iloc[0]

    mag = (np.sqrt(grib['u10']**2 + grib['v10']**2)*1.94384/5).round().astype('int').clip(upper=15).apply(lambda x: "{0:04b}".format(x)).str.cat()
    # This grabs the U-component and V-component of wind speed, calculates the magnitude in kts, rounds to the nearest 5kt speed, and converts to binary.
    dirs = (((round(np.arctan2(grib['v10'],grib['u10']) / (2 * np.pi / 16))) + 16) % 16).astype('int').apply(lambda x: "{0:04b}".format(x)).str.cat()
    # This encodes the wind direction into 16 cardinal directions and converts to vinary.

    import os
    os.remove(path)
    return mag + dirs, timepoints, latmin, latmax, lonmin, lonmax, latdiff, londiff, gribtime

def messageCreator(bin_data, timepoints, latmin, latmax, lonmin, lonmax, latdiff, londiff, gribtime, shift):
    # This function encodes the grib binary data into characters that can be sent over the inReach.
    chars = """!"#$%\'()*+,-./:;<=>?_¡£¥¿&¤0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzÄÅÆÇÉÑØøÜßÖàäåæèéìñòöùüΔΦΓΛΩΠΨΣΘΞ""" # Allowed inReach characters.
    extrachars = {122:'@!',
    123:'@@',
    124:'@#',
    125:'@$',
    126:'@%',
    127:'@?'} # To get a full range of 128 code possibilities, these are extra two character codes.

    def encoder(x, shift): # This encodes the binary 8-bit chunks into the coding scheme based on the SHIFT.
        if len(x) < 7:
            x = x + '0'*(7-len(x))
        new_chars = chars[shift:] + chars[:shift]
        dec = int(x,2)
        if dec < 122:
            return new_chars[dec]
        else:
            return extrachars[dec]

    encoded = ''
    for piece in [bin_data[i:i+7] for i in range(0, len(bin_data), 7)]: # This sends the binary chunks to the encoder.
        encoded = encoded + encoder(piece,shift)

    # This forms the message that will be sent. I wanted times and lat/long to be explicitly written for debugging purposes but these could improved.
    gribmessage = """{times}
{iss}
{minmax}
{diff}
{shift}
{data}
END""".format(times=",".join((timepoints/ np.timedelta64(1, 'h')).astype('int').astype('str').to_list()),
                    iss=str(gribtime),
                    minmax=','.join(str(x) for x in [latmin,latmax,lonmin,lonmax]),
                    diff=str(latdiff[0])+","+str(londiff[0]),
                    shift = shift,
                    data=encoded)
    msg_len = 120 # Had problems with the messages being cutoff, even though they shouldn't have been according to Garmin's specifications. 120 character messages seemed like a safe bet.
    message_parts = [gribmessage[i:i+msg_len] for i in range(0, len(gribmessage), msg_len)] # Breaks up the big message into individual parts to send.
    return [str(i) + '\n' + message_parts[i] + '\n' + str(i) if i > 0 else message_parts[i] + '\n' + str(i) for i in range(len(message_parts))]

def inreachReply(url,message_str):
    # This uses the requests module to send a spoofed response to Garmin. I found no trouble reusing the MessageId over and over again but I do not know if there are risks with this.
    # I tried to use the same GUID from the specific incoming garmin email.
    import requests

    cookies = {
        'BrowsingMode': 'Desktop',
    }

    headers = {
        'authority': 'explore.garmin.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        # 'cookie': 'BrowsingMode=Desktop',
        'origin': 'https://explore.garmin.com',
        'referer': url,
        'sec-ch-ua': '"Chromium";v="106", "Not;A=Brand";v="99", "Google Chrome";v="106.0.5249.119"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36',
        'x-requested-with': 'XMLHttpRequest',
    }

    data = {
        'ReplyAddress': YOUR_EMAIL,
        'ReplyMessage': message_str,
        'MessageId': '479947347',
        'Guid': url.split('extId=')[1].split('&adr')[0],
    }

    response = requests.post('https://explore.garmin.com/TextMessage/TxtMsg', cookies=cookies, headers=headers, data=data)
    if response.status_code != 200:
        print('Could not send!', flush=True)
    else:
        print('Sent', flush=True)
    return response

def answerService(message_id):
    msg = service.users().messages().get(userId='me', id=message_id).execute()
    msg_text = urlsafe_b64decode(msg['payload']['body']['data']).decode().split('\r')[0].lower()
    url = [x.replace('\r','') for x in urlsafe_b64decode(msg['payload']['body']['data']).decode().split('\n') if 'https://explore.garmin.com' in x][0] # Grabs the unique Garmin URL for answering.

    if msg_text[:5] == 'ecmwf' or msg_text[:3] == 'gfs': # Only allows for ECMWF or GFS model
        emailfunctions.send_message(service, "query@saildocs.com", "", "send " + msg_text) # Sends message to saildocs according to their formatting.
        time_sent = datetime.utcnow()
        valid_response = False

        for i in range(60): # Waits for reply and makes sure reply received aligns with request (there's probably a better way to do this).
            time.sleep(10)
            last_response = emailfunctions.search_messages(service,"query-reply@saildocs.com")[0]
            time_received = pd.to_datetime(service.users().messages().get(userId='me', id=last_response['id']).execute()['payload']['headers'][-1]['value'].split('(UTC)')[0])
            if time_received > time_sent:
                valid_response = True
                break

        if valid_response:
            try:
                grib_path = emailfunctions.GetAttachments(service, last_response['id'])
            except:
                inreachReply(url, "Could not download attachment")
                return
            bin_data, timepoints, latmin, latmax, lonmin, lonmax, latdiff, londiff, gribtime = processGrib(grib_path)

            for shift in range(1,10): # Due to Garmin's inability to send certain character combinations (such as ">f" if I recall), this shift attempts to try different encoding schemes.
                # If the message fails to send, the characters are shifted over by one and it's attempted again.
                message_parts = messageCreator(bin_data, timepoints, latmin, latmax, lonmin, lonmax, latdiff, londiff, gribtime, shift)
                for i in message_parts:
                    print(i, flush=True)
                for part in message_parts:
                    res = inreachReply(url, part) # Attempt to send each part of the message.
                    if res.status_code != 200:
                        time.sleep(10)
                        if part == message_parts[0]:
                            break
                        else:
                            inreachReply(url, 'Message failed attempting shift') # If it couldn't be sent, entire process is restarted.
                            # This could be improved, by maybe not restarting the entire process and indicating that the shift has changed.
                            break
                    time.sleep(10)
                if res.status_code == 200:
                    break
        else:
            inreachReply(url, "Saildocs timeout")
            return False
    else:
        inreachReply(url, "Invalid model")
        return False

def checkMail():
    ### This function checks the email inbox for Garmin inReach messages. I tried to account for multiple messages.
    global service
    service = emailfunctions.gmail_authenticate()
    results = emailfunctions.search_messages(service,"no.reply.inreach@garmin.com")

    inreach_msgs = []
    for result in results:
        inreach_msgs.append(result['id'])

    with open(LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION) as f: # This is a running list of previous inReach messages that have already been responded to.
        previous = f.read()

    unanswered = [message for message in inreach_msgs if message not in previous.split('\n')]
    for message_id in unanswered:
        try:
            answerService(message_id)
        except Exception as e:
            print(e, flush=True)
        with open(LIST_OF_PREVIOUS_MESSAGES_FILE_LOCATION, 'a') as file: # Whether answering was a success or failure, add message to list.
            file.write('\n'+message_id)

print('Starting loop')
while(True):
    time.sleep(60)
    print('Checking...', flush=True)
    checkMail()
    time.sleep(240)
