## Introduction
Input: a song, output: karaoke video for that song GG

## Install dependencies

```
pip install -U demucs
pip install git+https://github.com/openai/whisper.git
pip install blobfile
pip install noisereduce soundfile
apt-get update && apt-get install -y fonts-dejavu-core
```

# How to run
```
python main.py /path/to/your/audiofile.mp3
```