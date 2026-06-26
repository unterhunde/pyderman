# PiBot Setup Instructions

## Environment Setup

The application requires a Python virtual environment to avoid system-wide dependency conflicts.

### Create Virtual Environment

```bash
cd /home/jorg/pibot
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install --upgrade pip
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Running the Application

#### PC Application (Operator Console)

```bash
cd /home/jorg/pibot
source venv/bin/activate
python3 pc/client.py
```

#### Pi Application (Microphone Streamer)

```bash
cd /home/jorg/pibot
source venv/bin/activate
python3 pi/mic_udp_streamer.py
```

#### Pi Application (Video Streamer)

```bash
cd /home/jorg/pibot
source venv/bin/activate
python3 pi/video_udp_streamer.py
```

## Configuration

Edit `pibot.env` to configure:
- UDP ports
- IP addresses (PC and Pi)
- Sample rates
- Model paths
- Ollama server URL

## System Requirements

### PC Requirements
- Python 3.9+
- ~2GB disk space for models
- Tkinter (usually pre-installed with Python)
- ffmpeg (for Whisper)

### Pi Requirements
- Python 3.9+
- PyAudio dependencies: `sudo apt-get install portaudio19-dev`
- Camera enabled and working
- Microphone access
- Network connectivity to PC

## Troubleshooting

### Missing Modules
If you see "ModuleNotFoundError", ensure virtual environment is activated and requirements installed.

### Audio Issues
- Check microphone permissions: `sudo usermod -aG audio $USER`
- Verify audio device: `python3 -m pip install sounddevice && python3 -c "import sounddevice; sounddevice.query_devices()"`

### Network Issues
- Verify Pi and PC are on same network
- Check firewall rules for UDP ports 5000, 5001
- Test connectivity: `ping <pi_host>` and `ping <pc_host>`

### Camera Issues
- Test camera access: `libcamera-hello --qt` (on Pi with bookworm)
- Check permissions and device node access
