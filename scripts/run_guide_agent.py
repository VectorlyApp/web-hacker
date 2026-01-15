"""
scripts/run

Run the guide agent on the terminal.
"""

import argparse

from web_hacker.agents.guide_agent.guide_agent import GuideAgent


def main() -> None:
    """Run the guide agent."""
    guide_agent = GuideAgent()
    guide_agent.run()


if __name__ == "__main__":
    main()
