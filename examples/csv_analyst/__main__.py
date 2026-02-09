"""
Run the CSV Analyst example:

    python -m examples.csv_analyst          # CLI mode
    python -m examples.csv_analyst --web    # Web UI mode
"""

import sys

from .agent import create_agent, CSVAnalyst
from .config import CSV_CONFIG


def main():
    if "--web" in sys.argv:
        try:
            from sciagent.web.app import create_app
            app = create_app(create_agent, CSV_CONFIG)
            app.run(port=5000)
        except ImportError:
            print("Install web extras:  pip install sciagent[web]")
            sys.exit(1)
    else:
        try:
            from sciagent.cli import run_cli
            run_cli(create_agent, CSV_CONFIG)
        except ImportError:
            print("Install CLI extras:  pip install sciagent[cli]")
            sys.exit(1)


if __name__ == "__main__":
    main()
