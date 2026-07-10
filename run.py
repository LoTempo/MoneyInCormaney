from app import create_app


app = create_app()


if __name__ == "__main__":
    if app.config["DEBUG"]:
        app.run(
            host=app.config["SERVER_HOST"],
            port=app.config["SERVER_PORT"],
            debug=True,
        )
    else:
        from waitress import serve

        serve(
            app,
            host=app.config["SERVER_HOST"],
            port=app.config["SERVER_PORT"],
        )
