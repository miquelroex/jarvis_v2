import traceback
try:
    import speech_recognition as sr
    print('SR OK')
    from langchain_ollama import ChatOllama
    print('ChatOllama OK')
    from tools.time import get_time
    print('Tools OK')
    mic = sr.Microphone(device_index=19)
    print('Mic creado OK')
except Exception as e:
    traceback.print_exc()