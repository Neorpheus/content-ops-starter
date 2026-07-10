import webview
from app import app

if __name__ == '__main__':
    # Create the native desktop window and bind it directly to the Flask app
    # pywebview starts the Flask server locally and opens it in a native window
    webview.create_window(
        title='ImplantSafe - AI MRI Safety Verification Agent',
        url=app,
        width=1350,
        height=850,
        resizable=True,
        min_size=(1024, 768)
    )
    webview.start()
