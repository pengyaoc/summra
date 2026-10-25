"""Distill development server."""
from distill import config
from distill.app_base import create_app


def main():
    app = create_app()
    app.config['IS_DEVELOPMENT'] = True
    app.run(host='0.0.0.0', port=config.PORT, debug=False)


if __name__ == '__main__':
    main()
