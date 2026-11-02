from app import create_app
from seed import seed_demo_data

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        if app.config["DEMO_SEED"]:
            seed_demo_data()
    app.run(host="127.0.0.1", port=5000, debug=app.config["DEMO_OTP_ENABLED"])
