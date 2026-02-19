"""Allow running the trader package as a module: python -m trader"""
import sys
from .cli import main

if __name__ == '__main__':
    sys.exit(main())
