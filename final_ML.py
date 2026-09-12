import joblib
import numpy as np
import pandas as pd
import librosa
import os
import soundfile as sf
from collections import Counter
from sklearn.model_selection import train_test_split
import random
from sklearn.ensemble import RandomForestClassifier  
from sklearn.metrics import classification_report, confusion_matrix
import shutil  
import warnings
warnings.filterwarnings('ignore')
if os.path.exists('augmented'):
    shutil.rmtree('augmented')
os.makedirs('augmented', exist_ok=True)
random.seed(42)
np.random.seed(42)
pd.set_option('display.max_columns', None)  
pd.set_option('display.max_colwidth', None)  
pd.set_option('display.width', None)  

AUDIO_ROOT = r'D:\Program Files\donateacry_corpus_cleaned_and_updated_data'
OUTPUT_CSV = 'my_mfcc_features.csv'
def get_label(Path):
    if 'hungry' in Path:
        return 3
    elif 'tired' in Path:

        return 4

    elif 'discomfort' in Path:

        return 2

    else:

        return -1



all_data = []

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
    mfccs_data = np.concatenate([mfccs_mean, delta_mean])
   
    for i in range(13):
                        features[f'MFCC_mean_{i+1}'] = mfccs_mean[i]
                        features[f'DELTA_mean_{i+1}'] = delta_mean[i]
                        features[f'MFCC_std_{i+1}'] = mfccs_std[i]
   
    features['RMS'] = rms
    features['ZCR'] = zcr
    features['Centroid'] = cent
    return features

audio_files = []

for root, dirs, files in os.walk(AUDIO_ROOT):

    for file in files:

        if file.endswith('.wav'):

            full_path = os.path.join(root, file)

            audio_files.append(full_path)

for file in audio_files:

    label = get_label(file)

    if label == -1:

        print(f"Warning: Could not determine label for file {file}")

    features = extract_features(file)

    features['Cry_Audio_File'] = file

    features['Cry_Reason'] = label

    all_data.append(features)

df = pd.DataFrame(all_data)


X = df.drop(columns=['Cry_Audio_File', 'Cry_Reason']).values
y = df['Cry_Reason'].values

indices = np.arange(len(df))

X_train, X_test, y_train, y_test, train_idx , test_idx = train_test_split(

    X, y, indices , test_size=0.2, random_state=42, stratify=y

)

def augment_audio(audio_path, output_path , aug_type):

    audio, sr = librosa.load(audio_path, sr=16000)

    if aug_type == 'time':

        rate = random.uniform(0.9, 1.1)

        audio = librosa.effects.time_stretch(audio, rate=rate)

    elif aug_type == 'pitch':

        n_steps = random.uniform(-2, 2)

        while n_steps == 0:

            n_steps = random.uniform(-2, 2)

        audio = librosa.effects.pitch_shift(y=audio,sr = sr,n_steps = n_steps)

    elif aug_type == 'noise':

        noise_level = random.uniform(0.001, 0.015)

        noise = np.random.normal(0, noise_level, audio.shape)

        audio = audio + noise

    elif aug_type == 'combined':

        n_steps = random.uniform(-2, 2)

        while n_steps == 0:

            n_steps = random.uniform(-2, 2)

        audio = librosa.effects.pitch_shift(y=audio,sr = sr,n_steps = n_steps)

        rate = random.uniform(0.9, 1.1)

        audio = librosa.effects.time_stretch(audio, rate=rate)

        noise_level = random.uniform(0.002, 0.012)

        noise = np.random.normal(0, noise_level, audio.shape)

        audio = audio + noise

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    sf.write(output_path, audio, sr)


    return output_path

counts = Counter(y_train)

hungry_count = Counter(y_train)[3]

tired_count = Counter(y_train)[4]

discomfort_count = Counter(y_train)[2]

discomfort_needed = hungry_count - discomfort_count

tired_needed = hungry_count - tired_count

discomfort_df = df[df['Cry_Reason'] == 2]

tired_df = df[df['Cry_Reason'] == 4]

train_df = df.iloc[train_idx].copy()

test_df = df.iloc[test_idx].copy()

discomfort_train_files = train_df[train_df['Cry_Reason'] == 2]['Cry_Audio_File'].values

tired_train_files = train_df[train_df['Cry_Reason'] == 4]['Cry_Audio_File'].values

num_discomfort_to_augment = max(1, len(discomfort_train_files) // 2)

discomfort_files_to_augment = discomfort_train_files[:num_discomfort_to_augment]

num_tired_to_augment = max(1, len(tired_train_files) // 2)

tired_files_to_augment = tired_train_files[:num_tired_to_augment]

def calculate_copies_per_file(needed, num_files):

    if num_files == 0:

        return 0

    copies = needed // num_files

    copies = max(3, copies)

    return copies

discomfort_copies_per_file = calculate_copies_per_file(

    discomfort_needed,

    len(discomfort_files_to_augment)

)

tired_copies_per_file = calculate_copies_per_file(

    tired_needed,

    len(tired_files_to_augment)

)

augmentation_types = ['pitch', 'time', 'noise', 'combined']

def augment_files(files_to_augment,copies_per_file, label , class_name):

    files_Created = 0

    created_files = []

    local_mfccs = []

    local_labels = []
    local_features = []

    for file in files_to_augment:

        base_name = os.path.basename(file).replace('.wav', '')

        for i in range(copies_per_file):

            aug_type = augmentation_types[i % len(augmentation_types)]

            output_path = f"augmented/{base_name}_{aug_type}_{i}_{random.randint(1, 999)}.wav"

            try:

                augment_audio(file, output_path, aug_type)

                if not os.path.exists(output_path):

                    print(f"❌ File not found: {output_path}")

                    continue

                file_size = os.path.getsize(output_path)

                if file_size < 1000:  

                    print(f"❌ File too small: {output_path} ({file_size} bytes)")

                    continue                

                features = extract_features(output_path)

                mfccs_list = [  features[f'MFCC_mean_{i+1}' ] for i in range(13)] + [features[f'MFCC_std_{i+1}'] for i in range(13)]

                local_mfccs.append(mfccs_list)
                local_features.append(list(features.values()))
                local_labels.append(label)

                created_files.append(output_path)

                files_Created += 1
            except Exception as e:

                print(f"❌ Error processing {file}: {e}")

                print(f"   Output path: {output_path}")

                import traceback

                traceback.print_exc()  


       

    return files_Created , local_mfccs, local_labels , created_files , local_features 


discomfort_created, discomfort_mfccs, discomfort_labels , discomfort_files , discomfort_features = augment_files(discomfort_files_to_augment, discomfort_copies_per_file, 2, 'discomfort')

tired_created , tired_mfccs, tired_labels , tired_files , tired_features = augment_files(tired_files_to_augment, tired_copies_per_file, 4, 'tired')

discomfort_features = np.array(discomfort_features)
tired_features = np.array(tired_features)
discomfort_labels = np.array(discomfort_labels)
tired_labels = np.array(tired_labels)
augmented_features = np.concatenate((discomfort_features, tired_features), axis=0)
augmented_labels = np.concatenate((discomfort_labels, tired_labels), axis=0)
X_train_augmented = np.vstack([X_train, augmented_features])
y_train_augmented = np.concatenate([y_train, augmented_labels])
rf = RandomForestClassifier(n_estimators=300,  min_samples_split = 5 ,class_weight='balanced', max_depth = 8 , criterion='entropy' , random_state=42 ,n_jobs=-1)
rf.fit(X_train_augmented, y_train_augmented.ravel())
y_pred_default = rf.predict(X_test)

probs = rf.predict_proba(X_test)
y_pred_custom = []

class_map = {val: idx for idx, val in enumerate(rf.classes_)}
idx_discomfort = class_map.get(2)
idx_hungry = class_map.get(3)
idx_tired = class_map.get(4)
TIRED_THRESHOLD = 0.30
DISCOMFORT_THRESHOLD = 0.35

for row in probs:
    prob_discomfort = row[idx_discomfort]
    prob_tired = row[idx_tired]
    
    if prob_tired >= TIRED_THRESHOLD:
        y_pred_custom.append(4)
    elif prob_discomfort >= DISCOMFORT_THRESHOLD:
        y_pred_custom.append(2)
    else:
        y_pred_custom.append(3)

joblib.dump(rf, 'cry_reason_rf_model.pkl')
print('saved')            
