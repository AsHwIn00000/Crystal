from dotenv import load_dotenv
load_dotenv()

from app import create_app
import os

app = create_app(os.getenv('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=8080,
        debug=True,
        threaded=True,
    )
