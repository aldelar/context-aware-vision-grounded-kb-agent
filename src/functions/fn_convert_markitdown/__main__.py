"""Allow ``python -m fn_convert_markitdown article_dir output_dir``."""

import logging
import sys

from fn_convert_markitdown import run


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    )

    if len(sys.argv) != 3:
        print("Usage: python -m fn_convert_markitdown <article_dir> <output_dir>", file=sys.stderr)
        sys.exit(1)

    run(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
