import logging
import webview
from app import app

# Configure logging to write to debug_log.txt
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('pywebview')
file_handler = logging.FileHandler('debug_log.txt', mode='w')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

if __name__ == '__main__':
    logger.info("Starting debug app...")
    try:
        webview.create_window('Debug Window', app)
        logger.info("Window created successfully. Starting event loop...")
        webview.start(debug=True)
        logger.info("Event loop terminated.")
    except Exception as e:
        logger.exception(f"Unhandled exception in desktop app: {e}")
