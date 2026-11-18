"""Start the Bookstore API locally:  python run.py   (docs at http://127.0.0.1:5055/docs)"""
from bookstore_api import create_app

if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5055)
