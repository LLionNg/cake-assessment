import sys
from pathlib import Path

from streamlit.web import cli

APP = Path(__file__).parent / "src" / "ui" / "streamlit_app.py"

if __name__ == "__main__":
    sys.argv = ["streamlit", "run", str(APP), *sys.argv[1:]]
    sys.exit(cli.main())
