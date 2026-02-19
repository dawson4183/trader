"""Tests for the CLI module."""
import pytest
from unittest.mock import patch, mock_open
from trader.cli import main, create_parser, scrape_command, health_check_command
from trader.exceptions import ValidationError


class TestCreateParser:
    """Tests for the create_parser function."""
    
    def test_parser_creation(self):
        """Test that the parser can be created."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == 'trader'
    
    def test_scrape_subcommand_exists(self):
        """Test that the scrape subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(['scrape'])
        assert args.command == 'scrape'
        assert hasattr(args, 'func')
    
    def test_health_subcommand_exists(self):
        """Test that the health subcommand exists."""
        parser = create_parser()
        args = parser.parse_args(['health'])
        assert args.command == 'health'
        assert hasattr(args, 'func')
    
    def test_scrape_args_parsing(self):
        """Test that scrape command arguments are parsed correctly."""
        parser = create_parser()
        args = parser.parse_args([
            'scrape',
            '--html-file', 'test.html',
            '--selectors', '.title,.price'
        ])
        assert args.html_file == 'test.html'
        assert args.selectors == '.title,.price'


class TestScrapeCommand:
    """Tests for the scrape_command function."""
    
    def test_scrape_no_args(self):
        """Test scrape command with no arguments prints message."""
        parser = create_parser()
        args = parser.parse_args(['scrape'])
        
        with patch('builtins.print') as mock_print:
            result = scrape_command(args)
        
        assert result == 0
        mock_print.assert_called_once()
        assert 'Scraper running' in mock_print.call_args[0][0]
    
    def test_scrape_with_html_file_missing_selectors(self):
        """Test scrape command with html-file but no selectors."""
        parser = create_parser()
        args = parser.parse_args(['scrape', '--html-file', 'test.html'])
        
        with patch('builtins.print') as mock_print:
            result = scrape_command(args)
        
        assert result == 1
        mock_print.assert_called_once()
        assert 'selectors required' in mock_print.call_args[0][0]
    
    def test_scrape_with_html_file_success(self):
        """Test scrape command with valid html file and selectors."""
        parser = create_parser()
        args = parser.parse_args([
            'scrape',
            '--html-file', 'test.html',
            '--selectors', 'div.title,span.price'
        ])
        
        html_content = '<html><body><div class="title">Test Item</div><span class="price">$10</span></body></html>'
        with patch('builtins.open', mock_open(read_data=html_content)):
            with patch('builtins.print') as mock_print:
                result = scrape_command(args)
        
        assert result == 0
        mock_print.assert_called_once()
        assert 'HTML validation passed' in mock_print.call_args[0][0]
    
    def test_scrape_file_not_found(self):
        """Test scrape command with non-existent file."""
        parser = create_parser()
        args = parser.parse_args([
            'scrape',
            '--html-file', 'nonexistent.html',
            '--selectors', '.title'
        ])
        
        with patch('builtins.print') as mock_print:
            result = scrape_command(args)
        
        assert result == 1
        mock_print.assert_called_once()
        assert 'File not found' in mock_print.call_args[0][0]
    
    def test_scrape_validation_error(self):
        """Test scrape command handles ValidationError."""
        parser = create_parser()
        args = parser.parse_args([
            'scrape',
            '--html-file', 'test.html',
            '--selectors', '.missing,.notfound'
        ])
        
        html_content = '<html><body><div class="title">Test Item</div></body></html>'
        with patch('builtins.open', mock_open(read_data=html_content)):
            with patch('builtins.print') as mock_print:
                result = scrape_command(args)
        
        assert result == 1
        mock_print.assert_called_once()
        assert 'Validation error' in mock_print.call_args[0][0]


class TestHealthCheckCommand:
    """Tests for the health_check_command function."""
    
    def test_health_check_success(self):
        """Test health check passes when imports work."""
        parser = create_parser()
        args = parser.parse_args(['health'])
        
        with patch('builtins.print') as mock_print:
            result = health_check_command(args)
        
        assert result == 0
        mock_print.assert_called_once_with('Health check: OK')


class TestMain:
    """Tests for the main function."""
    
    def test_main_scrape_success(self):
        """Test main with scrape command returns 0 on success."""
        with patch('builtins.print'):
            result = main(['scrape'])
        assert result == 0
    
    def test_main_health_success(self):
        """Test main with health command returns 0 on success."""
        with patch('builtins.print'):
            result = main(['health'])
        assert result == 0
    
    def test_main_with_help(self):
        """Test main with help exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            main(['--help'])
        assert exc_info.value.code == 0
    
    def test_main_scrape_subcommand_help(self):
        """Test main with scrape --help exits cleanly."""
        with pytest.raises(SystemExit) as exc_info:
            main(['scrape', '--help'])
        assert exc_info.value.code == 0
    
    def test_main_returns_nonzero_on_error(self):
        """Test main returns non-zero on validation error."""
        with patch('builtins.open', mock_open(read_data='<html></html>')):
            with patch('builtins.print'):
                result = main([
                    'scrape',
                    '--html-file', 'test.html',
                    '--selectors', '.missing'
                ])
        assert result == 1
    
    def test_main_no_args_defaults_to_scrape(self):
        """Test main with no args defaults to scrape command."""
        with patch('builtins.print') as mock_print:
            result = main([])
        
        assert result == 0
        mock_print.assert_called_once()
        assert 'Scraper running' in mock_print.call_args[0][0]
