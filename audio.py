import numpy as np
import sounddevice as sd
import noisereduce as rn
from queue import Queue
import webrtcvad


# ==========================================
# Settings
# ==========================================

SAMPLE_RATE = 16000
BLOCK_SIZE = 320

# First 3 seconds = calibration
CALIBRATION_TIME = 3

audio_queue = Queue()


# ==========================================
# Microphone callback
# ==========================================

def callback(indata, frames, time_info, status):

    if status:
        print(status)

    chunk = indata[:, 0]

    audio_queue.put(chunk)

# Start microphone


stream = sd.InputStream(
    callback=callback,
    samplerate=SAMPLE_RATE,
    channels=1,
    blocksize=BLOCK_SIZE
)

stream.start()


# VAD


vad = webrtcvad.Vad(3)


try:

    # Calibration - First 3 seconds


    print("Calibration started...")
    print("Please keep the environment quiet.")
    print("No baby cry should be present during calibration.")

    noise_chunks = []

    total_samples = 0

    required_samples = SAMPLE_RATE * CALIBRATION_TIME

    while total_samples < required_samples:

        chunk = audio_queue.get()

        noise_chunks.append(chunk)

        total_samples += len(chunk)


    # Create noise profile
    noise_profile = np.concatenate(noise_chunks)

    noise_profile = noise_profile[:required_samples]

    print("Calibration finished.")
    print("Starting VAD...")

    # Continuous processing
    while True:

        # Get audio chunk
        chunk = audio_queue.get()

        # Noise Reduction

        clean = rn.reduce_noise(
            y=chunk,
            sr=SAMPLE_RATE,
            y_noise=noise_profile
        )


        # ==================================
        # Convert audio to PCM
        # ==================================

        pcm = (clean * 32767).astype(np.int16)

        frame_bytes = pcm.tobytes()


        # ==================================
        # VAD
        # ==================================

        is_speech = vad.is_speech(
            frame_bytes,
            SAMPLE_RATE
        )


        # ==================================
        # Result
        # ==================================

        if is_speech:

            print("Speech detected")

        
            # Later:
            # Send clean audio to ML
           

        else:

            continue


except KeyboardInterrupt:

    print("\nStopping the stream...")


finally:

    stream.stop()
    stream.close()
    print("Stream closed.")