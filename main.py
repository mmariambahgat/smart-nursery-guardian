import tkinter as tk
import threading
from queue import Queue
import numpy as np
import sounddevice as sd
import noisereduce as rn
import webrtcvad
import librosa
import joblib
import soundfile as sf

from communication import ESP32Bluetooth
from gui import SmartNurseryGUI
from telegrambot import gas_alert


SAMPLE_RATE = 16000
BLOCK_SIZE = 320
CALIBRATION_TIME = 3
RECORD_SECONDS = 5

audio_queue = Queue()

rf_model = joblib.load("cry_reason_rf_model.pkl")


root = tk.Tk()
app = SmartNurseryGUI(root)


try:

    esp = ESP32Bluetooth(
        port="COM4",
        baudrate=115200
    )

    app.update_esp_status("Connected")
    app.update_message("ESP32 connected successfully")

except Exception as e:

    esp = None
    app.update_esp_status("Disconnected")
    app.show_alert("ESP32 connection failed")

    print("ESP32 Error:", e)
def extract_features(audio_path,n_mfcc = 13,sr = 16000):
    features = {}
    audio, sr = librosa.load(audio_path, sr=sr)
    rms = np.mean(librosa.feature.rms(y=audio))
    mfccs = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=n_mfcc)
    zcr = np.mean(librosa.feature.zero_crossing_rate(y=audio))
    cent = np.mean(librosa.feature.spectral_centroid(y=audio, sr=sr))
    delta_mfccs = librosa.feature.delta(mfccs)
    mfccs_mean = np.mean(mfccs, axis=1)
    delta_mean = np.mean(delta_mfccs, axis=1)
    mfccs_std = np.std(mfccs, axis=1)

    for i in range(13):
                        features[f'MFCC_mean_{i+1}'] = mfccs_mean[i]
                        features[f'MFCC_std_{i+1}'] = mfccs_std[i]
                        features[f'DELTA_mean_{i+1}'] = delta_mean[i]
   
    features['RMS'] = rms
    features['ZCR'] = zcr
    features['Centroid'] = cent
    return features
SAMPLE_RATE = 16000
BLOCK_SIZE = 320
CALIBRATION_TIME = 3
RECORD_SECONDS = 5  

audio_queue =  Queue()
vad = webrtcvad.Vad(3) 

def callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_queue.put(indata[:, 0])

stream = sd.InputStream(
    callback=callback,
    samplerate=SAMPLE_RATE,
    channels=1,
    blocksize=BLOCK_SIZE
)
stream.start()

try:
    print("\nCalibration started... Keep the room quiet.")
    noise_chunks = []
    total_samples = 0
    required_samples = SAMPLE_RATE * CALIBRATION_TIME

    while total_samples < required_samples:
        chunk = audio_queue.get()
        noise_chunks.append(chunk)
        total_samples += len(chunk)

    noise_profile = np.concatenate(noise_chunks)[:required_samples]
    print("Calibration finished. Listening for sounds...\n")
    is_recording = False
    buffer = []
    frames_recorded = 0
    target_frames = int((SAMPLE_RATE / BLOCK_SIZE) * RECORD_SECONDS)

    while True:
        chunk = audio_queue.get()
        clean = rn.reduce_noise(y=chunk, sr=SAMPLE_RATE, y_noise=noise_profile)
        
        if is_recording:
            
            buffer.append(clean)
            frames_recorded += 1
            if frames_recorded >= target_frames:
                print("5 seconds captured! Analyzing...")
                full_audio = np.concatenate(buffer)
                temp_file = "live_cry.wav"
                sf.write(temp_file, full_audio, SAMPLE_RATE)
                features_dict = extract_features(temp_file)
                features_array = np.array([list(features_dict.values())])
                probabilities = rf_model.predict_proba(features_array)[0]
                class_probs = dict(zip(rf_model.classes_, probabilities))
                prob_discomfort = class_probs.get(2, 0.0) 
                prob_hungry = class_probs.get(3, 0.0)     
                prob_tired = class_probs.get(4, 0.0)
                TIRED_THRESHOLD = 0.30
                DISCOMFORT_THRESHOLD = 0.35
                HUNGRY_THRESHOLD = 0.60
                reason =''
                if prob_tired >= TIRED_THRESHOLD:
                    reason = 'TIRED'                    
                    try:
                        if esp is not None:
                            esp.send_command("I")
                        else:
                            esp.send_command("C")
                    except Exception as e:
                         print("ESP command error:",e)
                         
                         
                elif prob_discomfort >= DISCOMFORT_THRESHOLD:
                    reason = 'DISCOMFORT'
                else:
                    reason = 'HUNGRY'
                app.update_cry_status(reason)
                print(reason)
                is_recording = False
                buffer = []
                frames_recorded = 0
                print("Listening for sounds...")
                
        else:
            pcm = (clean * 32767).astype(np.int16)
            is_speech = vad.is_speech(pcm.tobytes(), SAMPLE_RATE)
            
            if is_speech:
                print("Voice detected! Recording started...")
                esp.send_command("C")
                is_recording = True
                buffer.append(clean)
                frames_recorded = 1

except KeyboardInterrupt:
    print("\nStopping the stream...")
finally:
    stream.stop()
    stream.close()
    print("Stream closed.")
if esp is not None:
    try:
        esp.send_command("S")
    except Exception as e:
         print("ESP cry end error:",e)

gas_alert_sent= False
def update_system():
    global gas_alert_sent
    if esp is not None:
        try:
            data = esp.request_all_sensors()
            if data["gas"] is not None:
                app.update_gas_status("Detected")
                gas_alert()
                gas_alert_sent = True
                app.show_alert("Gas detected")
            else:
                  app.update_gas_status("Normal")
            if data["temperature"] is not None:
                app.update_temperature(data["temperature"])

            if data["baby_awake"] == '0':
                app.update_baby_status("Sleeping")
            else:
                app.update_baby_status("Awake")

            message = esp.read_message()

            if message is not None:

                app.update_message(
                    message
                )

        except Exception as e:

            print(
                "Communication error:",
                e
            )

    root.after(
        500,
        update_system
    )


def close_system():

    print(
        "Closing Smart Nursery Guardian..."
    )

    if esp is not None:

        try:

            esp.close()

        except Exception:

            pass

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    close_system
)



update_system()
root.mainloop()