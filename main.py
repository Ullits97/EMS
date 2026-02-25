import argparse

from ems.web_gui import run_web_gui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EMS web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_web_gui(host=args.host, port=args.port, open_browser=not args.no_browser)
