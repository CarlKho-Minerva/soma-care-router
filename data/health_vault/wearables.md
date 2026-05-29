# Wearables and HUD Notes

## Meta Ray-Ban Display Web Apps
- Fixed 600x600 additive display
- Input arrives as Arrow keys and Enter via Neural Band / cap-touch gestures
- Good fit for HUD, glanceable guidance, food logging, and ambient state
- Web Apps do not expose camera or microphone APIs

## Meta Device Access Toolkit (DAT)
- Native iOS / Android integration path
- Exposes video streaming, photo capture, open-ear audio, and microphones
- Best route if Soma later needs direct glasses media access instead of phone-mediated capture

## Current Soma architecture
- Phone handles OpenAI voice + vision today
- Glasses act as the display and gesture surface today
- DAT is the path to true glasses-camera / glasses-mic integration later