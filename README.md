# Vosk-STT-Custom-Component-for-HA
<br/>
Vosk is a fully local Speech-To-Text service which you can run even on a CPU-only PC.
<br/>
In comparison to Faster-Whisper I found Vosk to be more reliable and in most cases more accurate.<br/>
Since there was no direct integeration to Home Assistant, I decided to create a custom component.<br/>
Now I'm sharing my code hoping it helps somebody else.
<br/>
<br/>
<b>Steps to get this integration up and running</b> <br/>
1. Please visit https://github.com/alphacep/vosk-server to learn how to get the Vosk Server installed on your server PC. I personally use docker compose so feel free to use the following code in your docker-compose.yaml.
   <br/><b>NOTE:</b> Prior to running the Vosk Server your should visit https://alphacephei.com/vosk/models and download the desired model into /path/to/your/models/ folder. In my setup I use "vosk-model-en-us-0.22" model.<br/>
   
```
services:
  vosk:
    image: alphacep/kaldi-en:latest
    container_name: vosk
    volumes:
      - /path/to/your/models/vosk-model-en-us-0.22:/opt/vosk-model-en/model  
    ports:
      - 2700:2700
    restart: unless-stopped
```

<br/>
2. Run 

```
sudo docker compose up -d 
```

After this command is successfully executed, your server should now be accessible on http://your-server-ip:2700.<br/>
3. Navigate to your home assistant custom_components folder and create a new folder called 'vosk_stt'. The copy all the files located in the custom components from this repository and paste it inside the newly created folder.<br/>
4. Add the following in your configuration.yaml of your home assistant:<br/>
```
stt:
  - platform: vosk_stt
    vosk_url: "ws://your-server-ip-address:2700"
    vol_inc: 25 #Int Value of Volume to be increased
```
<br/>
5. Restart your home assistant and enjoy this new fully local STT service.
<br/><br/>
<b>NOTE:</b> if you notice, I've also added a noise cancelling and volume increase feature in this integration. This greatly helps in improving the accuracy of the Speech-to-Text.
<br/><br/>
<b>Important Note:</b>
<br/>
Please keep in mind that this method of STT integration within home assistant for some reason is not fully supported hence the reason you should expect to received similar error message in your home assistant log as below:
<br/><br/>

```
The stt integration does not support any configuration parameters, got [{'platform': 'vosk_stt', 'vosk_url': 'ws://x.x.x.x:2700', 'vol_inc': 25}]. Please remove the configuration parameters from your configuration.
```

<br/><br/>
There's a chance that Home Assistant will eventually remove the option of adding stt as custom component and my component, like few other custom components out there (ie Google, OpenAI) will stop working.
<br/><br/>
<b>Acknowledgement</b>
<br/>
I was inspired by the great work done by @shiipou for the OpenAI STT integration (https://github.com/shiipou/openai_stt).
