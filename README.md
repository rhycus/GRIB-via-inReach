# GRIB-via-inReach
I wrote this code to send GRIB wind data over a Garmin inReach during a 14-day passage at sea. It worked great, and I had a comfortable 1600 mile passage from Norfolk to St. Martin. While there are definitely advantages to WeatherFax and IridiumGo, this method for receiving weather data was effective and relatively cheap.

I have received a lot of interest in this, so I am hoping to share my code so that it may be used by fellow sailors and improved by more skilled programmers!

If you'd like to buy me a beer, my venmo is @FinbarC.

### DISCLAIMER

I tested and wrote this code within a matter of a few days, thus there may be BUGS and INEFFICIENCIES which I have not resolved. I do not have a software engineering background, so consider this hodgepodge coding! If you use this software, there are some quirks which you need to be aware of. Please read this entire document and walk through the code. I haven't tested this since November 2022.

OFFSHORE SAILING IS A SERIOUS AND DANGEROUS UNDERTAKING AND ACCURATE WEATHER DATA IS CRITICALLY IMPORTANT. YOU USE THIS SOFTWARE ARE YOUR OWN RISK.

## OVERVIEW

This system allows users of the Garmin inReach satellite SMS device to receive on-demand geospatial wind forecasts. Over the inReach, the user sends a request to their email address and specifies the desired location, times, and weather model. This is done according to the Sail Docs GRIB format. The code of main.py is constantly checking the aforementioned email for GRIB requests, using the Gmail API. This could be done on a local computer or a cloud-based python service (I used Python Anywhere). When a request is received, it is forwarded to the Sail Docs service, which replies with a GRIB file. The GRIB file is parsed, compressed, and encoded so that it may be sent over multiple SMS messages. These messages are sent over Garmin's online reply service. When they arrive on the inReach, the user copies the texts to their computer or phone, and uses the Decoder iPython notebook to render the geospatial wind data on a map.

## REQUESTING GRIB

To request a GRIB, the inReach user sends a properly formatted string to the email address associated with the service. This string is formatted according to the Sail Docs specification (http://www.saildocs.com/gribinfo). Here is an example string:

```
gfs:24n,34n,72w,60w|2,2|12,24,36,48|wind
```

This would request data according to the GFS model (the ECWMF model can also be used, but I found Sail Docs responded cleaner with GFS), lattitudes 24N - 34N, longitudes 72W - 60W, each at 2 degree intervals, with points in time 12, 24, 36, and 48 hours, and only wind data (all this is designed for).

It is important to not request too big of an area or too many time points. The above string (4 points in time, 5 x 6 grid) was sent over 3 texts. Thus, to be practical, this system needs to be used with the unlimited Garmin inReach subscription.

### RECEIVING SERVICE

I used Python Anywhere (http://www.pythonanywhere.com) to run main.py. Unfortunately, I lost information about how I created the Python environment, but I believe it used the following dependencies, which can be installed via pip.

- xarray (0.20.2)
- cfgrib (0.9.10.2)
- Gmail API according to: https://developers.google.com/people/quickstart/python

The Gmail API needs to be setup and a credentials.json file downloaded. This file location must be specified in emailfunctions.py. The path to save the token file and any attachments needs to be specified there as well, in addition to the email address.

In main.py, the email also needs to be specified as well as the filepath for tracking message IDs.

With main.py running constantly on a local or cloud-based service, when a properly formatted request is received, it is forwarded to Sail Docs. Sail Docs should respond promptly with the appropriate GRIB file. Occassionally, it will respond with slightly different lattitude/longitudes (35N - 30N instead of 34N - 30N, or 24.999999N instead of 25N). This is why the lattitude and longitude of the RECEIVED GRIB (not what was requested) needs to be sent back to the user, as a contingency for it being wildly different.

The GRIB file is processed and compressed. The wind speed magnitude is compressed to 5kt intervals, and maxes out at 75kts. The wind direction is compressed to 16 directions. In my opinion, this is granular enough to make accurate route planning decisions. This data is then converted to binary and encoded according to allowed SMS characters.

**NOTE:** For some reason, which I was unable to figure out, Garmin has trouble sending certain (seemingly random) character combinations. For example, I could not send ">f" (if I recall correctly) anywhere in the message. I did not determine all of the forbidden combinations. As a work around, if a message fails to send, the encoding scheme is shifted by one character and the entire process is restarted. This is the SHIFT parameter. Occassionally, it would fail a few times. Thus, if the GRIB is sent over 4 texts, 3 may be received before the last one fails. Then, the process is restarted and another 4 messages are sent with the encoding shifted. Once the message with "END" is received, the user knows the sending process was completed successfully.

**NOTE:** There was an additional unresolved problem where Garmin would cut out the messages randomly around the 130-140 character mark. As a work around, I've limited each message to 120 characters and marked each message with a beginning signifyer and end signifyer (both are the message number), to indicate to the user that the entire message was sent and not cut off.

To send the data, the Python requests module is used with Garmin's web based replying service. I had no trouble reusing the same messageID over and over. Maybe some Garmin data engineer will be cursing my name in a few months. I do not know if they've updated their website or replying service since then.

Here is an example of what would be sent from the aforementioned request (explanatory comments denoted with <---):

**Message 1**
```
12,24,36,48   <--- Time points
2022-11-17 12:00:00   <--- Model run time
24.0,36.0,-72.0,-58.0   <--- Latitude and longitude
2.0,2.0   <--- Lat/lon intervals
1   <--- The encoding shift
>+g9&g8>>'6>"'ä7>+CP¤oäP¤t+Q8>-x>+æO&gA8>'8>+gæ>,+g8&gi8  <--- Data
0   <--- Indicates end of the first message
```

**Message 2**
```
1   <--- Indicates beginning of second message
>'eO>+8?>+æP7+A8¤g8>,+æ6+gA7=gA8+g6_¤oe#>/æg¤+gP¤gA8>,)7+gg8>"A>+ke8>+æ8g8>¤pÑΔ+o@@AOQ54">>1o"kèØΣcgZΘ@@É8XÑΓ+fÑöΘgFñhH0
1   <--- Indicates end of second message
```

**Message 3**
```
2
zΛ>:¤ÑøgjÑΣSØ5ΘbÇÑg8>¤o7ΦΞoC?ΘY8xM>:zXågjüèLaM+"'Sg8>¤g4>*gåüΘfØP&8¤xHÑ'èoæP0<@?c5@?
END   <--- Indicates end of the transmission
2
```

## DECODER

There is no easy way to access recieved inReach texts from a computer. What I did was I connected my Android phone to the inReach via the EarthMate app. Then, I accessed my Android screen from my computer with Scrcpy (https://github.com/Genymobile/scrcpy). The text in the EarthMate app is not copyable, but if you attempt to "Forward" each text, it is then copyable in the text box (a ridiculous work around, I hope there is a better way to do it!). I copied each message into a .txt file, which might then look like:

```
12,24,36,48
2022-11-17 12:00:00
24.0,36.0,-72.0,-58.0
2.0,2.0
1
>+g9&g8>>'6>"'ä7>+CP¤oäP¤t+Q8>-x>+æO&gA8>'8>+gæ>,+g8&gi8
0
FW: 1
>'eO>+8?>+æP7+A8¤g8>,+æ6+gA7=gA8+g6_¤oe#>/æg¤+gP¤gA8>,)7+gg8>"A>+ke8>+æ8g8>¤pÑΔ+o@@AOQ54">>1o"kèØΣcgZΘ@@É8XÑΓ+fÑöΘgFñhH0
1
FW: 2
zΛ>:¤ÑøgjÑΣSØ5ΘbÇÑg8>¤o7ΦΞoC?ΘY8xM>:zXågjüèLaM+"'Sg8>¤g4>*gåüΘfØP&8¤xHÑ'èoæP0<@?c5@?
END
2
```

This .txt file is specified and processed through the Decoder.ipynb notebook and the wind data is rendered on a map. The user's current location can be marked. Higher resolution maps can also be downloaded and used. For each point in time, a map will be displayed as follows:

![image](https://user-images.githubusercontent.com/41167102/235323713-8fc52550-401d-4bbf-b5bd-ec1af6ec1059.png)
