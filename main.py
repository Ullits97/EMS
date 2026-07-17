import argparse

from ems.heating_library import list_heating_sources
from ems.web_gui import run_web_gui


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run EMS web GUI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--list-heating-sources", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.list_heating_sources:
        for spec in list_heating_sources():
            print(f"{spec.key}: {spec.display_name} (max {spec.max_heat_output_kw:.1f} kW, eff {spec.efficiency:.2f})")
    else:
        run_web_gui(host=args.host, port=args.port, open_browser=not args.no_browser)
