"""CLI entry point for the trader package.

Provides command-line interface with health check functionality.
"""

import argparse
import json
import os
import sys
from typing import Dict, Any, Literal

from trader.health_check import check_database_connection, check_scraper_status, check_recent_failures


def get_db_path() -> str:
    """Get database path from environment or use default.
    
    Returns:
        Database path string, defaults to ':memory:' if not set.
    """
    return os.environ.get("TRADER_DB_PATH", ":memory:")


def run_health_checks(db_path: str = ":memory:") -> Dict[str, Any]:
    """Run all health checks and return consolidated results.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A dictionary containing:
            - 'database': Database connection check results
            - 'scraper': Scraper status check results
            - 'recent_failures': Recent failures check results
            - 'overall_status': 'healthy', 'degraded', or 'unhealthy'
    """
    # Run individual checks
    database_result = check_database_connection(db_path)
    scraper_result = check_scraper_status(db_path)
    failures_result = check_recent_failures(db_path)

    # Determine overall status
    overall_status = _determine_overall_status(
        database_result, scraper_result, failures_result
    )

    return {
        "database": database_result,
        "scraper": scraper_result,
        "recent_failures": failures_result,
        "overall_status": overall_status,
    }


def _determine_overall_status(
    database: Dict[str, Any],
    scraper: Dict[str, Any],
    failures: Dict[str, Any],
) -> Literal["healthy", "degraded", "unhealthy"]:
    """Determine overall health status from individual check results.

    Status rules:
        - 'healthy': All checks pass, no warnings
        - 'degraded': Minor issues (warnings, idle scraper, some failures)
        - 'unhealthy': Errors (db connection failed, scraper has errors, critical failures)

    Args:
        database: Database check result
        scraper: Scraper status check result
        failures: Recent failures check result

    Returns:
        Overall status string: 'healthy', 'degraded', or 'unhealthy'
    """
    has_error = False
    has_warning = False

    # Check database status
    if database.get("status") == "error":
        has_error = True

    # Check scraper status
    scraper_status = scraper.get("status")
    if scraper_status == "error":
        has_error = True
    elif scraper_status == "idle":
        has_warning = True

    # Check for critical failures
    if failures:
        critical_count = failures.get("critical_24h", 0)
        total_count = failures.get("total_24h", 0)

        if critical_count > 0:
            has_error = True
        elif total_count > 5:  # More than 5 failures is concerning
            has_warning = True

    # Determine overall status based on findings
    if has_error:
        return "unhealthy"
    elif has_warning:
        return "degraded"
    else:
        return "healthy"


def main(argv: Any = None) -> int:
    """Main CLI entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 for healthy, 1 for degraded/unhealthy
    """
    parser = argparse.ArgumentParser(
        prog="trader",
        description="Trader CLI - Item parser with health monitoring",
    )

    parser.add_argument(
        "--health-check",
        action="store_true",
        dest="health_check",
        help="Run health checks and output JSON status",
    )

    args = parser.parse_args(args=argv)

    if args.health_check:
        db_path = get_db_path()
        results = run_health_checks(db_path)
        print(json.dumps(results, indent=2))

        # Return appropriate exit code
        if results["overall_status"] == "healthy":
            return 0
        else:
            return 1

    # No arguments provided - print help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
