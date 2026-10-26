"""Distill development server."""
from distill import config
from distill.app_base import create_app


def main():
    app = create_app()
    app.config['IS_DEVELOPMENT'] = True
    app.run(host=config.HOST, port=config.PORT, debug=False)


if __name__ == '__main__':
    main()
