"""CLI entry point for the trader scraper."""
import argparse
import sys
from typing import List, Optional

from .item_parser import validate_html_structure, validate_price, deduplicate_items
from .exceptions import ValidationError


def run_health_check() -> int:
    """
    Run health check to validate environment configuration.
    
    Checks:
    - Python version >= 3.8
    - beautifulsoup4 is importable
    - lxml is importable
    
    Returns:
        Exit code (0 for healthy, 1 for unhealthy)
    """
    errors = []
    
    # Check Python version >= 3.8
    if sys.version_info < (3, 8):
        major = sys.version_info[0] if isinstance(sys.version_info, tuple) else sys.version_info.major
        minor = sys.version_info[1] if isinstance(sys.version_info, tuple) else sys.version_info.minor
        errors.append(f"Python version {major}.{minor} < 3.8")
    
    # Check beautifulsoup4 is importable
    try:
        import bs4  # noqa: F401
    except ImportError:
        errors.append("beautifulsoup4 not importable")
    
    # Check lxml is importable
    try:
        import lxml  # noqa: F401  # type: ignore[import-untyped]
    except ImportError:
        errors.append("lxml not importable")
    
    if errors:
        print(f"unhealthy: {', '.join(errors)}")
        return 1
    
    print("healthy")
    return 0


def scrape_command(args: argparse.Namespace) -> int:
    """
    Run the scraper to parse items from HTML.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # If HTML file is provided, validate it
        if args.html_file:
            # Validate selectors are provided first
            if not args.selectors:
                print("Error: --selectors required when using --html-file")
                return 1
            
            with open(args.html_file, 'r', encoding='utf-8') as f:
                html = f.read()
            
            # Validate HTML structure with provided selectors
            selectors_list = [s.strip() for s in args.selectors.split(',')]
            validate_html_structure(html, selectors_list)
            print(f"HTML validation passed for {len(selectors_list)} selector(s)")
        else:
            # Default scraper behavior
            print("Scraper running...")
            
        return 0
    except ValidationError as e:
        print(f"Validation error: {e}")
        return 1
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def health_check_command(args: argparse.Namespace) -> int:
    """
    Run health check to verify the CLI is working.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code (0 for healthy, non-zero for unhealthy)
    """
    try:
        # Basic health check - verify imports work
        _ = validate_html_structure
        _ = validate_price
        _ = deduplicate_items
        print("Health check: OK")
        return 0
    except Exception as e:
        print(f"Health check failed: {e}")
        return 1


def create_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for the CLI.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog='trader',
        description='CLI for the D2IA bot scraper'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run health check to validate environment configuration'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scrape command (default)
    scrape_parser = subparsers.add_parser(
        'scrape',
        help='Run the item scraper'
    )
    scrape_parser.add_argument(
        '--html-file',
        type=str,
        help='Path to HTML file to parse'
    )
    scrape_parser.add_argument(
        '--selectors',
        type=str,
        help='CSS selectors as comma-separated list (e.g., ".title,.cost")'
    )
    scrape_parser.set_defaults(func=scrape_command)
    
    # Health check command
    health_parser = subparsers.add_parser(
        'health',
        help='Run health check'
    )
    health_parser.add_argument(
        '--health-check',
        action='store_true',
        dest='health_check_flag',
        help='Flag to indicate health check mode'
    )
    health_parser.set_defaults(func=health_check_command)
    
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """
    Main entry point for the CLI.
    
    Args:
        argv: Command line arguments (defaults to sys.argv[1:])
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    
    # Handle --health-check flag first (takes priority)
    if args.health_check:
        return run_health_check()
    
    if args.command is None:
        # Default to scrape command if no subcommand specified
        result: int = scrape_command(argparse.Namespace(html_file=None, selectors=None))
        return result
    
    result = args.func(args)
    return int(result)


if __name__ == '__main__':
    sys.exit(main())
