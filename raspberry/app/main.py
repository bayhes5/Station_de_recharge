import requests

API_URL = "http://backend:8000"


def test_api():
    try:
        response = requests.get(API_URL, timeout=5)
        print("Reponse API:", response.text)
    except Exception as exc:
        print("Erreur:", exc)


if __name__ == "__main__":
    test_api()
