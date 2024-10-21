import logging
import async_timeout
import voluptuous as vol
import json
from websocket import create_connection
import wave, io 
import noisereduce as nr
import numpy as np
from pydub import AudioSegment
from scipy.io import wavfile

from homeassistant.components.stt import (
    AudioBitRates,
    AudioChannels,
    AudioCodecs,
    AudioFormats,
    AudioSampleRates,
    Provider,
    SpeechMetadata,
    SpeechResult,
    SpeechResultState,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

# URL for the Vosk Web Socket server
VOSK_URL = 'vosk_url'
VOL_INC = 'vol_inc'
DEFAULT_VOL = 5

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(VOSK_URL): cv.string,
    vol.Optional(VOL_INC, default=DEFAULT_VOL): cv.positive_int
})

async def async_get_engine(hass, config, discovery_info=None):
    vosk_url = config[VOSK_URL]
    vol_inc = config.get(VOL_INC, DEFAULT_VOL)
    return VoskSTTServer(hass, vosk_url, vol_inc)


### Noise removal and volume increase ####
def process_audio(audio_bytes, sample_rate=16000, channels=1, sampwidth=1, volume_increase_db=5):
    """
    Convert PCM binary data to WAV file format.
    :param audio_bytes: The raw PCM binary audio data.
    :param sample_rate: The sample rate (e.g., 16000 Hz).
    :param channels: Number of audio channels (1 for mono, 2 for stereo).
    :param sampwidth: Sample width in bytes (e.g., 2 bytes for 16-bit audio).
    :return: A BytesIO object containing the WAV data.
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(channels)  # 1 for mono, 2 for stereo
        wav_file.setsampwidth(sampwidth) # 2 bytes = 16 bits per sample
        wav_file.setframerate(sample_rate) # Set the sample rate (e.g., 16000 Hz)
        wav_file.writeframes(audio_bytes)
    wav_buffer.seek(0)
    sample_rate, data = wavfile.read(wav_buffer)
    # Apply noise reduction
    reduced_noise = nr.reduce_noise(y=data, sr=sample_rate)
    # Convert the processed numpy array back to AudioSegment
    processed_audio = AudioSegment(
        reduced_noise.tobytes(),
        frame_rate=sample_rate,
        sample_width=reduced_noise.dtype.itemsize,
        channels=1  # Adjust this if your audio has multiple channels
    )
    # Increase volume
    louder_audio = processed_audio + volume_increase_db  # Increase volume by specified dB
    # Export the modified audio to bytes
    output_wav_io = io.BytesIO()
    louder_audio.export(output_wav_io, format="wav")
    output_wav_io.seek(0)
    return output_wav_io


class VoskSTTServer(Provider):
    """The Vosk STT API provider."""

    def __init__(self, hass, vosk_url, vol_inc):
        """Initialize Vosk STT Server."""
        self.hass = hass
        self._vosk_url=vosk_url
        self._vol_inc=vol_inc
        self._language = "en-US"  # Set default language

    @property
    def default_language(self) -> str:
        """Return the default language."""
        return self._language

    @property
    def supported_languages(self) -> list[str]:
        """Return the list of supported languages."""
        return [self._language]

    @property
    def supported_formats(self) -> list[AudioFormats]:
        """Return a list of supported formats."""
        return [AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[AudioCodecs]:
        """Return a list of supported codecs."""
        return [AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[AudioBitRates]:
        """Return a list of supported bitrates."""
        return [AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[AudioChannels]:
        """Return a list of supported channels."""
        return [AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: SpeechMetadata, stream
    ) -> SpeechResult:
        # Collect data
        audio_data = b""
        async for chunk in stream:
            audio_data += chunk

        def job():
            try:
                ws = create_connection(self._vosk_url)
                processed_audio_bytes = process_audio(audio_data, volume_increase_db=self._vol_inc)
                wf = wave.open(processed_audio_bytes, "rb")
                ws.send('{ "config" : { "sample_rate" : %d } }' % (wf.getframerate()))
                buffer_size = int(wf.getframerate() * 0.2)  # 0.2 seconds of audio
                while True:
                    data = wf.readframes(buffer_size)
                    if len(data) == 0:
                        break
                    ws.send_binary(data)
                    #ws.recv()
                    try:
                        vosk_response = json.loads(ws.recv())
                        if len(vosk_response["text"])>0:
                            break
                    except:
                        continue
                ws.send('{"eof" : 1}')
                final_response = json.loads(ws.recv())
                final_text='STT Error'
                try:
                    if len(final_response["text"])>0:
                        final_text = final_response["text"]
                    else:
                        final_text = vosk_response["text"]
                except:
                    final_text = vosk_response["text"]
                ws.close()
            except Exception as e:
                _LOGGER.error(f"Error occurred: {str(e)}")
                return 'STT Error'
            return final_text

        async with async_timeout.timeout(10):
            assert self.hass
            response = await self.hass.async_add_executor_job(job)
            if len(response) > 0:
                return SpeechResult(
                    response,
                    SpeechResultState.SUCCESS,
                )
            return SpeechResult("", SpeechResultState.ERROR)
